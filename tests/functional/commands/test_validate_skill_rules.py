"""Functional tests for the skill rules in `agent-notes validate` (spec 008, Req 4).

Each rule has a failing fixture (the rule fires, naming the file, the rule and
the measured value) and a passing fixture (a valid skill produces no finding).
"""

import time

import pytest
from unittest.mock import patch

import agent_notes.config as config
from agent_notes.services.skill_validation import _relative_targets, check_skill_dir

SKILL = "my-skill"


def _frontmatter(extra="", description="A valid skill. Use when testing."):
    return f"---\nname: {SKILL}\ndescription: {description}\ngroup: process\n{extra}---\n"


def _toc(*anchors):
    return "## Contents\n\n" + "".join(f"- [{a}](#{a})\n" for a in anchors) + "\n"


def _filler(count):
    return "".join(f"line {i}\n" for i in range(count))


def _reference(*headings, toc=True, pad=100):
    """A reference file over 100 lines with one `##` heading per name."""
    anchors = [h.lower().replace(" ", "-") for h in headings]
    out = "# Reference\n\n" + (_toc(*anchors) if toc else "")
    for heading in headings:
        out += f"## {heading}\n\n"
    return out + _filler(pad)


@pytest.fixture
def run_validate(tmp_path, capsys):
    """Build a skill dir from `files` ({relative path: text}) and run validate()."""
    skills_src = tmp_path / "skills-src"

    def _run(files, name=SKILL):
        skill = skills_src / name
        for rel, text in files.items():
            path = skill / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(text, bytes):
                path.write_bytes(text)
            else:
                path.write_text(text)
        fake_dist = tmp_path / "dist"
        fake_dist.mkdir(exist_ok=True)
        with patch.object(config, "DIST_CLAUDE_DIR", fake_dist / "claude"), \
                patch.object(config, "DIST_OPENCODE_DIR", fake_dist / "opencode"), \
                patch.object(config, "DIST_GITHUB_DIR", fake_dist / "github"), \
                patch.object(config, "DIST_RULES_DIR", fake_dist / "rules"), \
                patch.object(config, "ROOT", tmp_path), \
                patch("agent_notes.config.find_skill_dirs", return_value=[skill]):
            with pytest.raises(SystemExit):
                from agent_notes.commands.validate import validate
                validate()
        out = capsys.readouterr().out
        _run.output = out
        return [line for line in out.splitlines()
                if (" FAIL " in line or " WARN " in line) and SKILL in line]

    return _run


def _fails(findings):
    return [line for line in findings if " FAIL " in line]


def _warns(findings):
    return [line for line in findings if " WARN " in line]


class TestSkillLineLimit:
    def test_skill_md_over_500_lines_fails(self, run_validate):
        findings = run_validate({"SKILL.md": _frontmatter() + _filler(500)})
        assert any("my-skill/SKILL.md" in f and "skill-lines" in f and "505 lines" in f
                   for f in _fails(findings)), findings

    def test_skill_md_at_500_lines_passes(self, run_validate):
        text = _frontmatter() + _filler(495)
        assert len(text.splitlines()) == 500
        assert run_validate({"SKILL.md": text}) == []


class TestSkillTokenLimit:
    def test_skill_md_over_5000_estimated_tokens_fails(self, run_validate):
        body = ("x" * 99 + "\n") * 180  # 18000 bytes of body, 180 lines
        findings = run_validate({"SKILL.md": _frontmatter() + body})
        assert any("my-skill/SKILL.md" in f and "skill-tokens" in f and "~5" in f
                   for f in _fails(findings)), findings

    def test_skill_md_under_5000_estimated_tokens_passes(self, run_validate):
        body = ("x" * 99 + "\n") * 170  # 17000 bytes of body, 170 lines
        assert run_validate({"SKILL.md": _frontmatter() + body}) == []


class TestDescriptionLength:
    def test_description_over_1024_chars_fails(self, run_validate):
        findings = run_validate({"SKILL.md": _frontmatter(description="a" * 1025)})
        assert any("my-skill/SKILL.md" in f and "description-length" in f and "1025" in f
                   for f in _fails(findings)), findings

    def test_description_of_exactly_1024_chars_is_not_an_error(self, run_validate):
        findings = run_validate({"SKILL.md": _frontmatter(description="a" * 1024)})
        assert _fails(findings) == []

    def test_description_over_250_chars_warns_but_does_not_fail(self, run_validate):
        findings = run_validate({"SKILL.md": _frontmatter(description="a" * 251)})
        assert _fails(findings) == []
        assert any("my-skill/SKILL.md" in f and "description-length" in f and "251" in f
                   for f in _warns(findings)), findings

    def test_description_of_250_chars_has_no_warning(self, run_validate):
        assert run_validate({"SKILL.md": _frontmatter(description="Use when " + "a" * 241)}) == []

    def test_length_is_measured_on_the_folded_value(self, run_validate):
        # Raw text is > 250 characters (long indentation), folded value is 29.
        folded = '"Use when first part\n' + " " * 300 + 'second part"'
        assert run_validate({"SKILL.md": _frontmatter(description=folded)}) == []

    def test_length_is_measured_on_a_block_scalar(self, run_validate):
        text = "---\nname: my-skill\ndescription: >-\n" + "".join(
            f"  {'w' * 99}\n" for _ in range(3)) + "group: process\n---\n"
        findings = run_validate({"SKILL.md": text})
        assert any("description-length" in f and "299" in f for f in _warns(findings)), findings


class TestDescriptionWhenClause:
    def test_description_without_use_when_warns(self, run_validate):
        findings = run_validate({"SKILL.md": _frontmatter(description="Does a thing.")})
        assert _fails(findings) == []
        assert len(_warns(findings)) == 1, findings
        assert "my-skill/SKILL.md" in findings[0] and "description-when" in findings[0] \
            and 'no "Use when" clause' in findings[0]

    def test_description_with_use_when_has_no_warning(self, run_validate):
        assert run_validate({"SKILL.md": _frontmatter(description="Does a thing. Use when asked.")}) == []

    def test_triggers_key_is_no_longer_allowed(self, run_validate):
        findings = run_validate({"SKILL.md": _frontmatter(extra="triggers:\n  - one\n")})
        assert any("frontmatter-key" in f and "'triggers'" in f for f in _fails(findings)), findings


class TestReferenceTableOfContents:
    def test_long_reference_without_a_toc_fails(self, run_validate):
        files = {"SKILL.md": _frontmatter(), "ref.md": _reference("Alpha", "Beta", toc=False)}
        findings = run_validate(files)
        assert any("my-skill/ref.md" in f and "toc" in f and "no" in f and "Contents" in f
                   for f in _fails(findings)), findings

    def test_long_reference_with_a_matching_toc_passes(self, run_validate):
        files = {"SKILL.md": _frontmatter(), "ref.md": _reference("Alpha", "Beta")}
        assert run_validate(files) == []

    def test_table_of_contents_heading_is_accepted(self, run_validate):
        ref = _reference("Alpha").replace("## Contents", "## Table of Contents")
        assert run_validate({"SKILL.md": _frontmatter(), "ref.md": ref}) == []

    def test_reference_of_100_lines_needs_no_toc(self, run_validate):
        ref = "## Alpha\n" + _filler(99)
        assert len(ref.splitlines()) == 100
        assert run_validate({"SKILL.md": _frontmatter(), "ref.md": ref}) == []

    def test_reference_of_101_lines_needs_a_toc(self, run_validate):
        ref = "## Alpha\n" + _filler(100)
        assert len(ref.splitlines()) == 101
        findings = run_validate({"SKILL.md": _frontmatter(), "ref.md": ref})
        assert any("my-skill/ref.md" in f and "toc" in f and "101 lines" in f
                   for f in _fails(findings)), findings

    def test_empty_toc_fails(self, run_validate):
        ref = "# R\n\n## Contents\n\n## Alpha\n\n" + _filler(100)
        findings = run_validate({"SKILL.md": _frontmatter(), "ref.md": ref})
        assert any("my-skill/ref.md" in f and "toc" in f and "empty" in f
                   for f in _fails(findings)), findings

    def test_stale_toc_missing_a_heading_fails(self, run_validate):
        ref = "# R\n\n" + _toc("alpha") + "## Alpha\n\n## Beta\n\n" + _filler(100)
        findings = run_validate({"SKILL.md": _frontmatter(), "ref.md": ref})
        assert any("my-skill/ref.md" in f and "toc" in f and "stale" in f and "beta" in f
                   for f in _fails(findings)), findings

    def test_stale_toc_with_an_extra_link_fails(self, run_validate):
        ref = "# R\n\n" + _toc("alpha", "gone") + "## Alpha\n\n" + _filler(100)
        findings = run_validate({"SKILL.md": _frontmatter(), "ref.md": ref})
        assert any("toc" in f and "stale" in f and "gone" in f for f in _fails(findings)), findings

    def test_toc_in_the_wrong_order_fails(self, run_validate):
        ref = "# R\n\n" + _toc("beta", "alpha") + "## Alpha\n\n## Beta\n\n" + _filler(100)
        findings = run_validate({"SKILL.md": _frontmatter(), "ref.md": ref})
        assert any("toc" in f and "stale" in f for f in _fails(findings)), findings

    def test_toc_heading_after_line_20_fails(self, run_validate):
        ref = "# R\n\n" + _filler(25) + _toc("alpha") + "## Alpha\n\n" + _filler(100)
        findings = run_validate({"SKILL.md": _frontmatter(), "ref.md": ref})
        assert any("toc" in f and "first 20 lines" in f for f in _fails(findings)), findings

    def test_headings_inside_code_fences_are_not_required_in_the_toc(self, run_validate):
        ref = ("# R\n\n" + _toc("alpha") + "## Alpha\n\n```md\n## Not a heading\n```\n\n"
               + _filler(100))
        assert run_validate({"SKILL.md": _frontmatter(), "ref.md": ref}) == []

    def test_anchors_follow_github_rules(self, run_validate):
        ref = ("# R\n\n"
               "## Contents\n\n"
               "- [A](#action-text-rich-text)\n"
               "- [B](#whats-current)\n"
               "- [C](#same)\n"
               "- [D](#same-1)\n\n"
               "## Action Text (Rich Text)\n\n## What's `Current`?\n\n## Same\n\n## Same\n\n"
               + _filler(100))
        assert run_validate({"SKILL.md": _frontmatter(), "ref.md": ref}) == []

    def test_skill_md_itself_needs_no_toc(self, run_validate):
        assert run_validate({"SKILL.md": _frontmatter() + "## Alpha\n" + _filler(150)}) == []


class TestReferenceNesting:
    def test_reference_linking_to_a_sibling_reference_fails(self, run_validate):
        files = {"SKILL.md": _frontmatter(), "a.md": "See [b](b.md).\n", "b.md": "text\n"}
        findings = run_validate(files)
        assert any("my-skill/a.md" in f and "reference-nesting" in f and "b.md" in f
                   for f in _fails(findings)), findings

    def test_reference_linking_to_a_sibling_with_a_fragment_fails(self, run_validate):
        files = {"SKILL.md": _frontmatter(), "a.md": "See [b](b.md#part).\n", "b.md": "text\n"}
        findings = run_validate(files)
        assert any("reference-nesting" in f for f in _fails(findings)), findings

    def test_reference_linking_to_another_skill_fails(self, run_validate, tmp_path):
        other = tmp_path / "skills-src" / "other-skill"
        other.mkdir(parents=True)
        (other / "file.md").write_text("text\n")
        files = {"SKILL.md": _frontmatter(), "a.md": "See [x](../other-skill/file.md).\n"}
        findings = run_validate(files)
        assert any("my-skill/a.md" in f and "reference-nesting" in f and "other-skill/file.md" in f
                   for f in _fails(findings)), findings

    def test_urls_anchors_and_code_fences_are_fine(self, run_validate):
        text = ("See [web](https://example.com/x.md), [here](#top), "
                "[mail](mailto:a@b.c).\n\n```md\n[b](b.md)\n```\n")
        files = {"SKILL.md": _frontmatter(), "a.md": text, "b.md": "text\n"}
        assert run_validate(files) == []

    def test_reference_may_link_back_to_skill_md(self, run_validate):
        files = {"SKILL.md": _frontmatter(), "a.md": "Vocabulary in [SKILL](SKILL.md).\n"}
        assert run_validate(files) == []

    def test_repeated_link_is_reported_once(self, run_validate):
        files = {"SKILL.md": _frontmatter(), "a.md": "[b](b.md) and [b again](b.md)\n", "b.md": "x\n"}
        assert len(_fails(run_validate(files))) == 1

    def test_skill_md_may_link_to_its_references(self, run_validate):
        files = {"SKILL.md": _frontmatter() + "Read [a](a.md).\n", "a.md": "text\n"}
        assert run_validate(files) == []


class TestBrokenLinks:
    def test_skill_md_link_to_a_missing_file_fails(self, run_validate):
        files = {"SKILL.md": _frontmatter() + "Read [a](missing.md).\n"}
        findings = run_validate(files)
        assert any("my-skill/SKILL.md" in f and "broken-link" in f and "missing.md" in f
                   for f in _fails(findings)), findings

    def test_reference_link_to_a_missing_file_fails(self, run_validate):
        files = {"SKILL.md": _frontmatter(), "a.md": "Image: ![x](img/none.png)\n"}
        findings = run_validate(files)
        assert any("my-skill/a.md" in f and "broken-link" in f and "img/none.png" in f
                   for f in _fails(findings)), findings

    def test_link_with_a_title_and_fragment_to_a_missing_file_fails(self, run_validate):
        files = {"SKILL.md": _frontmatter() + 'Read [a](gone.md#x "title").\n'}
        findings = run_validate(files)
        assert any("broken-link" in f and "gone.md" in f for f in _fails(findings)), findings

    def test_links_to_existing_files_pass(self, run_validate):
        files = {"SKILL.md": _frontmatter() + "Read [a](a.md#part) and ![i](img/x.png).\n",
                 "a.md": "text\n", "img/x.png": "png\n"}
        assert run_validate(files) == []

    def test_urls_anchors_and_code_fences_are_ignored(self, run_validate):
        body = ("See [w](https://example.com/none.md), [t](#top), [m](mailto:a@b.c).\n\n"
                "```md\n[x](missing.md)\n```\n\nInline `[y](missing.md)` too.\n")
        assert run_validate({"SKILL.md": _frontmatter() + body}) == []


class TestFrontmatterKeys:
    def test_unknown_top_level_key_fails(self, run_validate):
        findings = run_validate({"SKILL.md": _frontmatter(extra="colour: red\n")})
        assert any("my-skill/SKILL.md" in f and "frontmatter-key" in f and "'colour'" in f
                   and "allowed" in f for f in _fails(findings)), findings

    def test_every_allowed_key_passes(self, run_validate):
        extra = ("when_to_use: sometimes\nargument-hint: '[x]'\narguments: [a]\n"
                 "disable-model-invocation: true\nuser-invocable: true\nallowed-tools: Read\n"
                 "disallowed-tools: Bash\nmodel: sonnet\neffort: low\ncontext: fork\n"
                 "agent: explorer\nbackground: false\nhooks: {}\npaths: ['*.rb']\nshell: bash\n"
                 "license: MIT\ncompatibility: any\nrequires_memory: obsidian\n"
                 "metadata:\n  anything: goes\n")
        assert run_validate({"SKILL.md": _frontmatter(extra=extra)}) == []

    def test_only_top_level_keys_are_checked(self, run_validate):
        extra = "metadata:\n  nested-unknown: 1\n"
        assert run_validate({"SKILL.md": _frontmatter(extra=extra)}) == []


def _plain(findings):
    return [line for line in findings if "unclosed code block" not in line]


def _reference_with_contents_at(line_number):
    """A 100+ line reference whose `## Contents` heading sits on `line_number`."""
    head = "".join(f"line {i}\n" for i in range(line_number - 1))
    return head + "## Contents\n\n- [Alpha](#alpha)\n\n## Alpha\n\n" + _filler(100)


class TestHeadingParsingIsLinear:
    def test_a_heading_with_20000_inner_spaces_validates_quickly(self, run_validate):
        ref = "# R\n\n" + _toc("alpha") + "## Alpha" + " " * 20000 + "x\n\n" + _filler(100)
        started = time.perf_counter()
        run_validate({"SKILL.md": _frontmatter(), "ref.md": ref})
        assert time.perf_counter() - started < 1.0

    def test_a_heading_made_only_of_spaces_validates_quickly(self, run_validate):
        ref = "# R\n\n" + _toc("alpha") + "## Alpha\n\n##" + " " * 20000 + "\n\n" + _filler(100)
        started = time.perf_counter()
        run_validate({"SKILL.md": _frontmatter(), "ref.md": ref})
        assert time.perf_counter() - started < 1.0

    def test_closing_hashes_are_not_part_of_the_heading(self, run_validate):
        ref = "# R\n\n" + _toc("alpha") + "## Alpha ##\n\n" + _filler(100)
        assert run_validate({"SKILL.md": _frontmatter(), "ref.md": ref}) == []

    def test_a_trailing_hash_glued_to_a_word_stays_in_the_heading(self, run_validate):
        ref = "# R\n\n## Contents\n\n- [C#](#c)\n\n## C#\n\n" + _filler(100)
        assert run_validate({"SKILL.md": _frontmatter(), "ref.md": ref}) == []


class TestMalformedInputGivesFindings:
    def test_a_nul_byte_in_a_link_is_a_finding(self, run_validate):
        findings = run_validate({"SKILL.md": _frontmatter() + "Read [a](a%00b.md).\n"})
        assert any("my-skill/SKILL.md" in f and "broken-link" in f for f in _fails(findings)), findings

    def test_a_non_utf8_skill_md_is_unreadable(self, run_validate):
        findings = run_validate({"SKILL.md": b"---\nname: my-skill\n---\n\xff\xfe\n"})
        assert any("my-skill/SKILL.md" in f and "file-unreadable" in f and "UTF-8" in f
                   for f in _fails(findings)), findings

    def test_a_non_utf8_reference_is_unreadable(self, run_validate):
        findings = run_validate({"SKILL.md": _frontmatter(), "ref.md": b"text \xff\xfe\n"})
        assert any("my-skill/ref.md" in f and "file-unreadable" in f and "UTF-8" in f
                   for f in _fails(findings)), findings

    def test_deeply_nested_yaml_is_a_parse_finding(self, run_validate):
        text = "---\nname: my-skill\ndescription: x\nnest: " + "[" * 5000 + "]" * 5000 + "\n---\n"
        findings = run_validate({"SKILL.md": text})
        assert any("my-skill/SKILL.md" in f and "frontmatter-parse" in f and "deep" in f
                   for f in _fails(findings)), findings

    def test_invalid_yaml_is_a_parse_finding_with_the_cause(self, run_validate):
        findings = run_validate({"SKILL.md": "---\nname: my-skill\ndescription: [unclosed\n---\n"})
        assert any("frontmatter-parse" in f and "invalid YAML" in f for f in _fails(findings)), findings
        assert not any("frontmatter-key" in f for f in findings), findings

    def test_empty_frontmatter_is_a_parse_finding(self, run_validate):
        findings = run_validate({"SKILL.md": "---\n---\nbody\n"})
        assert any("frontmatter-parse" in f for f in _fails(findings)), findings
        assert not any("frontmatter-key" in f for f in findings), findings

    def test_a_frontmatter_that_is_not_a_mapping_is_a_parse_finding(self, run_validate):
        findings = run_validate({"SKILL.md": "---\n- a\n- b\n---\n"})
        assert any("frontmatter-parse" in f and "mapping" in f for f in _fails(findings)), findings

    def _errors(self, tmp_path, text):
        skill = tmp_path / "skills-src" / SKILL
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_bytes(text)
        errors, _ = check_skill_dir(skill)
        return [f"{e.file_path} {e.message}" for e in errors]

    def test_crlf_line_endings_are_a_parse_finding(self, tmp_path):
        errors = self._errors(tmp_path, b"---\r\nname: my-skill\r\ndescription: x\r\n---\r\nbody\r\n")
        assert any("frontmatter-parse" in e and "CRLF" in e for e in errors), errors
        assert not any("frontmatter-key" in e for e in errors), errors

    def test_a_byte_order_mark_is_a_parse_finding(self, tmp_path):
        errors = self._errors(tmp_path, b"\xef\xbb\xbf---\nname: my-skill\ndescription: x\n---\n")
        assert any("frontmatter-parse" in e and "byte-order mark" in e for e in errors), errors
        assert not any("frontmatter-key" in e for e in errors), errors


class TestLinkConfinement:
    def test_a_percent_encoded_absolute_path_is_not_a_relative_target(self):
        assert _relative_targets("[p](%2Fetc%2Fpasswd)\n") == []

    def test_a_percent_encoded_absolute_path_is_not_probed(self, run_validate):
        files = {"SKILL.md": _frontmatter() + "Read [p](%2Fno-such-dir-xyz%2Fa.md).\n"}
        assert run_validate(files) == []

    def test_a_percent_encoded_scheme_is_not_a_relative_target(self):
        assert _relative_targets("[p](javascript%3Aalert)\n") == []

    def test_a_link_that_leaves_the_skill_is_a_finding_even_when_the_target_exists(
            self, run_validate, tmp_path):
        (tmp_path / "x.md").write_text("exists\n")
        findings = run_validate({"SKILL.md": _frontmatter() + "Read [x](../../x.md).\n"})
        assert any("my-skill/SKILL.md" in f and "link-outside-skill" in f and "../../x.md" in f
                   for f in _fails(findings)), findings
        assert not any(str(tmp_path) in f for f in findings), findings

    def test_a_missing_target_outside_the_skill_is_not_reported_as_missing(self, run_validate):
        findings = run_validate({"SKILL.md": _frontmatter() + "Read [x](../../none.md).\n"})
        assert any("link-outside-skill" in f for f in _fails(findings)), findings
        assert not any("broken-link" in f for f in findings), findings

    def test_a_symlinked_reference_pointing_outside_is_neither_read_nor_reported(
            self, run_validate, tmp_path):
        outside = tmp_path / "outside.md"
        outside.write_text("[leak](nope-secret.md)\n" + _filler(150))
        skill = tmp_path / "skills-src" / SKILL
        skill.mkdir(parents=True)
        (skill / "linked.md").symlink_to(outside)
        findings = run_validate({"SKILL.md": _frontmatter()})
        assert findings == [], findings
        assert "nope-secret" not in run_validate.output

    def test_a_link_to_a_symlink_that_leaves_the_skill_is_a_finding(self, run_validate, tmp_path):
        outside = tmp_path / "outside.txt"
        outside.write_text("data\n")
        skill = tmp_path / "skills-src" / SKILL
        skill.mkdir(parents=True)
        (skill / "data.txt").symlink_to(outside)
        findings = run_validate({"SKILL.md": _frontmatter() + "Read [d](data.txt).\n"})
        assert any("link-outside-skill" in f for f in _fails(findings)), findings
        assert not any(str(tmp_path) in f for f in findings), findings

    def test_a_symlinked_skill_md_is_unreadable(self, run_validate, tmp_path):
        outside = tmp_path / "outside.md"
        outside.write_text(_frontmatter())
        skill = tmp_path / "skills-src" / SKILL
        skill.mkdir(parents=True)
        (skill / "SKILL.md").symlink_to(outside)
        findings = run_validate({})
        assert any("file-unreadable" in f and "symlink" in f for f in _fails(findings)), findings


class TestOutputEscaping:
    def test_an_escape_character_in_a_link_target_is_printed_escaped(self, run_validate):
        findings = run_validate({"SKILL.md": _frontmatter() + "Read [a](a\x1b[31mb.md).\n"})
        assert any("broken-link" in f for f in _fails(findings)), findings
        assert "a\x1b[31mb.md" not in run_validate.output
        assert "a\\x1b[31mb.md" in run_validate.output


class TestReferenceContentsList:
    def test_ordered_list_items_are_accepted(self, run_validate):
        ref = ("# R\n\n## Contents\n\n1. [Alpha](#alpha)\n2) [Beta](#beta)\n\n"
               "## Alpha\n\n## Beta\n\n" + _filler(100))
        assert run_validate({"SKILL.md": _frontmatter(), "ref.md": ref}) == []

    def test_an_indented_continuation_line_belongs_to_the_item(self, run_validate):
        ref = ("# R\n\n## Contents\n\n- [Alpha](#alpha) the first\n  part, continued here\n"
               "- [Beta](#beta)\n\n## Alpha\n\n## Beta\n\n" + _filler(100))
        assert run_validate({"SKILL.md": _frontmatter(), "ref.md": ref}) == []

    def test_a_link_on_a_continuation_line_counts(self, run_validate):
        ref = ("# R\n\n## Contents\n\n- [Alpha](#alpha)\n  [Beta](#beta)\n\n"
               "## Alpha\n\n## Beta\n\n" + _filler(100))
        assert run_validate({"SKILL.md": _frontmatter(), "ref.md": ref}) == []

    def test_unindented_text_ends_the_list(self, run_validate):
        ref = ("# R\n\n## Contents\n\n- [Alpha](#alpha)\nplain text\n- [Beta](#beta)\n\n"
               "## Alpha\n\n## Beta\n\n" + _filler(100))
        findings = run_validate({"SKILL.md": _frontmatter(), "ref.md": ref})
        assert any("toc" in f and "stale" in f and "beta" in f for f in _fails(findings)), findings

    def test_listing_h3_headings_says_to_list_only_h2(self, run_validate):
        ref = ("# R\n\n## Contents\n\n- [Alpha](#alpha)\n- [Sub](#sub)\n\n"
               "## Alpha\n\n### Sub\n\n" + _filler(100))
        findings = run_validate({"SKILL.md": _frontmatter(), "ref.md": ref})
        assert any("toc" in f and "list only `##` headings" in f and "sub" in f
                   for f in _fails(findings)), findings

    def test_contents_heading_on_line_20_is_accepted(self, run_validate):
        ref = _reference_with_contents_at(20)
        assert run_validate({"SKILL.md": _frontmatter(), "ref.md": ref}) == []

    def test_contents_heading_on_line_21_fails(self, run_validate):
        ref = _reference_with_contents_at(21)
        findings = run_validate({"SKILL.md": _frontmatter(), "ref.md": ref})
        assert any("toc" in f and "first 20 lines" in f for f in _fails(findings)), findings


class TestFences:
    def test_tilde_fences_hide_links(self, run_validate):
        body = "~~~md\n[x](missing.md)\n~~~\n"
        assert run_validate({"SKILL.md": _frontmatter() + body}) == []

    def test_a_tilde_fence_is_not_closed_by_a_shorter_tilde_run(self, run_validate):
        body = "~~~~\n~~~\n[x](missing.md)\n~~~~\n"
        assert run_validate({"SKILL.md": _frontmatter() + body}) == []

    def test_a_fence_is_not_closed_by_a_line_with_an_info_string(self, run_validate):
        body = "```md\n```ruby\n[x](missing.md)\n```\n```\n"
        assert run_validate({"SKILL.md": _frontmatter() + body}) == []

    def test_a_four_backtick_fence_holds_three_backtick_fences(self, run_validate):
        body = "````md\n```ruby\n[x](missing.md)\n```\n````\n\nSee [r](real-missing.md).\n"
        findings = _plain(run_validate({"SKILL.md": _frontmatter() + body}))
        assert any("'real-missing.md'" in f for f in _fails(findings)), findings
        assert not any("'missing.md'" in f for f in findings), findings

    def test_a_fence_may_be_indented_up_to_three_spaces(self, run_validate):
        body = "   ```\n[x](missing.md)\n   ```\n"
        assert run_validate({"SKILL.md": _frontmatter() + body}) == []

    def test_a_four_space_indented_fence_is_code_not_a_fence(self, run_validate):
        body = "para\n\n    ```\n\n[x](missing.md)\n"
        findings = _plain(run_validate({"SKILL.md": _frontmatter() + body}))
        assert any("'missing.md'" in f for f in _fails(findings)), findings

    def test_indented_code_hides_links(self, run_validate):
        body = "Example:\n\n    [x](missing.md)\n"
        assert run_validate({"SKILL.md": _frontmatter() + body}) == []

    def test_a_tab_indented_code_hides_links(self, run_validate):
        body = "Example:\n\n\t[x](missing.md)\n"
        assert run_validate({"SKILL.md": _frontmatter() + body}) == []

    def test_an_indented_line_continuing_a_paragraph_is_prose(self, run_validate):
        body = "A paragraph\n    [x](missing.md)\n"
        findings = run_validate({"SKILL.md": _frontmatter() + body})
        assert any("broken-link" in f for f in _fails(findings)), findings

    def test_an_indented_nested_list_item_is_prose(self, run_validate):
        body = "- item\n\n    - nested [x](missing.md)\n"
        findings = run_validate({"SKILL.md": _frontmatter() + body})
        assert any("broken-link" in f for f in _fails(findings)), findings


class TestLinkSyntax:
    def test_a_target_with_balanced_parentheses_parses_whole(self, run_validate):
        files = {"SKILL.md": _frontmatter() + "Read [x](a_(1).md).\n", "a_(1).md": "x\n"}
        assert run_validate(files) == []

    def test_a_missing_target_with_parentheses_is_named_whole(self, run_validate):
        findings = run_validate({"SKILL.md": _frontmatter() + "Read [x](a_(1).md).\n"})
        assert any("broken-link" in f and "'a_(1).md'" in f for f in _fails(findings)), findings

    def test_an_image_inside_a_link_yields_both_targets(self):
        assert _relative_targets("[![i](a.png)](b.md)\n") == ["a.png", "b.md"]

    def test_the_outer_target_of_an_image_link_is_checked(self, run_validate):
        files = {"SKILL.md": _frontmatter() + "[![i](a.png)](b.md)\n", "a.png": "png\n"}
        findings = run_validate(files)
        assert any("broken-link" in f and "'b.md'" in f for f in _fails(findings)), findings

    def test_a_reference_style_definition_is_a_link(self, run_validate):
        findings = run_validate({"SKILL.md": _frontmatter() + "See [one][1].\n\n[1]: gone.md\n"})
        assert any("broken-link" in f and "'gone.md'" in f for f in _fails(findings)), findings

    def test_a_reference_style_definition_to_a_sibling_reference_is_nesting(self, run_validate):
        files = {"SKILL.md": _frontmatter(), "a.md": "See [one][1].\n\n[1]: b.md\n", "b.md": "x\n"}
        findings = run_validate(files)
        assert any("my-skill/a.md" in f and "reference-nesting" in f for f in _fails(findings)), findings

    def test_a_footnote_definition_is_not_a_link(self, run_validate):
        files = {"SKILL.md": _frontmatter() + "Note[^1].\n\n[^1]: gone.md is mentioned\n"}
        assert run_validate(files) == []

    def test_a_reference_linking_to_itself_is_not_nesting(self, run_validate):
        files = {"SKILL.md": _frontmatter(), "ref.md": "Back to [top](ref.md#x).\n"}
        assert run_validate(files) == []

    def test_a_non_markdown_link_from_a_reference_is_not_nesting(self, run_validate):
        files = {"SKILL.md": _frontmatter(), "a.md": "![i](img/x.png) and [s](run.sh)\n",
                 "img/x.png": "png\n", "run.sh": "echo\n"}
        assert run_validate(files) == []

    def test_a_percent_encoded_link_that_resolves_passes(self, run_validate):
        files = {"SKILL.md": _frontmatter() + "Read [a](my%20file.md).\n", "my file.md": "x\n"}
        assert run_validate(files) == []

    def test_a_broken_percent_encoded_link_names_the_decoded_target(self, run_validate):
        findings = run_validate({"SKILL.md": _frontmatter() + "Read [a](my%20file.md).\n"})
        assert any("broken-link" in f and "'my file.md'" in f for f in _fails(findings)), findings


class TestReferencesInSubdirectories:
    def test_a_reference_in_a_subdirectory_is_checked(self, run_validate):
        ref = "## Alpha\n" + _filler(100)
        findings = run_validate({"SKILL.md": _frontmatter(), "sub/deep/ref.md": ref})
        assert any("my-skill/sub/deep/ref.md" in f and "toc" in f for f in _fails(findings)), findings

    def test_links_resolve_from_the_references_own_directory(self, run_validate):
        files = {"SKILL.md": _frontmatter(), "sub/ref.md": "![i](img.png)\n", "sub/img.png": "png\n"}
        assert run_validate(files) == []

    def test_a_reference_in_a_subdirectory_may_link_back_to_skill_md(self, run_validate):
        files = {"SKILL.md": _frontmatter(), "sub/ref.md": "See [SKILL](../SKILL.md).\n"}
        assert run_validate(files) == []


class TestExactBoundaries:
    @staticmethod
    def _skill_md_of(size_bytes):
        head = _frontmatter()
        return head + "x" * (size_bytes - len(head.encode()) - 1) + "\n"

    def test_exactly_5000_estimated_tokens_passes(self, run_validate):
        text = self._skill_md_of(17500)
        assert len(text.encode()) == 17500
        assert run_validate({"SKILL.md": text}) == []

    def test_5000_point_something_estimated_tokens_passes(self, run_validate):
        assert run_validate({"SKILL.md": self._skill_md_of(17503)}) == []

    def test_5001_estimated_tokens_fails(self, run_validate):
        findings = run_validate({"SKILL.md": self._skill_md_of(17504)})
        assert any("skill-tokens" in f and "~5001" in f for f in _fails(findings)), findings


class TestOutputOrderAndLineCount:
    def test_a_failing_skill_gets_no_ok_line(self, run_validate):
        findings = run_validate({"SKILL.md": _frontmatter(extra="colour: red\n")})
        assert _fails(findings)
        assert "OK    my-skill/SKILL.md" not in run_validate.output

    def test_a_passing_skill_gets_an_ok_line_with_the_rule_line_count(self, run_validate):
        text = _frontmatter() + "one\ntwo\n"
        run_validate({"SKILL.md": text})
        assert f"OK    my-skill/SKILL.md ({len(text.splitlines())} lines)" in run_validate.output

    def test_a_file_without_a_trailing_newline_counts_the_same(self, run_validate):
        text = _frontmatter() + "one\ntwo"
        run_validate({"SKILL.md": text})
        assert f"OK    my-skill/SKILL.md ({len(text.splitlines())} lines)" in run_validate.output

    def test_quotes_inside_a_description_count_toward_its_length(self, run_validate):
        description = "'\"" + "a" * 1023 + "\"'"
        findings = run_validate({"SKILL.md": _frontmatter(description=description)})
        assert any("description-length" in f and "1025" in f for f in _fails(findings)), findings
