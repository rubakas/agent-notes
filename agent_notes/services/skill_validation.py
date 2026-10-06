"""Skill rules for `agent-notes validate` (spec 008, Req 4).

Each `_check_*` helper returns a list of (rule, message) findings for one file.
`check_skill_dir` runs them all and splits the result into errors and warnings.

The `broken-link` rule applies to SKILL.md and to every reference file; the
`reference-nesting` rule applies to reference files only. A link that leaves the
skill directory is a `link-outside-skill` finding and is never looked up on disk.
"""

import re
from collections import Counter
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple
from urllib.parse import unquote

import yaml

from ..domain.diagnostics import ValidationError, ValidationWarning

MAX_SKILL_LINES = 500
MAX_SKILL_TOKENS = 5000
BYTES_PER_TOKEN = 3.5
MAX_DESCRIPTION_CHARS = 1024
WARN_DESCRIPTION_CHARS = 250
TOC_REQUIRED_OVER_LINES = 100
TOC_WINDOW_LINES = 20

ALLOWED_FRONTMATTER_KEYS = (
    "name", "description", "when_to_use", "argument-hint", "arguments",
    "disable-model-invocation", "user-invocable", "allowed-tools", "disallowed-tools",
    "model", "effort", "context", "agent", "background", "hooks", "paths", "shell",
    "metadata", "license", "compatibility",
    "group", "requires_memory", "triggers",
)

Finding = Tuple[str, str]

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---[ \t]*(?:\n|\Z)", re.DOTALL)
_LINK_RE = re.compile(
    r"\]\(\s*<?((?:[^()\s<>]|\([^()\s<>]*\))+)>?(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
_DEFINITION_RE = re.compile(r"^ {0,3}\[(?!\^)[^\]]+\]:[ \t]*<?([^\s>]+)>?")
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
_HEADING_RE = re.compile(r"^##\s+(.+)$")
_SUBHEADING_RE = re.compile(r"^###\s+(.+)$")
_CONTENTS_RE = re.compile(r"^##\s+(Contents|Table of Contents)\s*$", re.IGNORECASE)
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d{1,9}[.)])\s")
_LIST_START_RE = re.compile(r"^ {0,3}(?:[-*+]|\d{1,9}[.)])(?:\s|$)")
_TOC_LINK_RE = re.compile(r"\]\(#([^)\s]+)\)")
_FENCE_RE = re.compile(r"^( *)(`{3,}|~{3,})(.*)$")


def read_markdown(path: Path) -> Tuple[Optional[str], Optional[str]]:
    """(text, None), or (None, why the file cannot be read). Symlinks are never followed."""
    if path.is_symlink():
        return None, "is a symlink; symlinks are not read"
    if not path.is_file():
        return None, "is not a regular file"
    try:
        return path.read_bytes().decode("utf-8"), None  # bytes, so CRLF is seen rather than translated
    except UnicodeDecodeError as error:
        return None, f"is not valid UTF-8 ({error.reason} at byte {error.start})"
    except OSError as error:
        return None, f"cannot be read ({error.strerror})"


def _lines(text: str) -> List[str]:
    """Lines split on newlines only; a trailing newline does not add a line."""
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    return [line.rstrip("\r") for line in lines]


def count_lines(text: str) -> int:
    return len(_lines(text))


def _fence_opener(line: str, in_list: bool) -> Optional[Tuple[str, int]]:
    """(fence character, length) when `line` opens a fenced code block."""
    match = _FENCE_RE.match(line)
    if not match:
        return None
    indent, marks, info = match.groups()
    if len(indent) > 3 and not in_list:
        return None
    if marks[0] == "`" and "`" in info:
        return None
    return marks[0], len(marks)


def _closes_fence(line: str, fence: Tuple[str, int]) -> bool:
    """A closing fence repeats the opener's character, at least as long, with no info string."""
    match = _FENCE_RE.match(line)
    if not match:
        return False
    _, marks, info = match.groups()
    return marks[0] == fence[0] and len(marks) >= fence[1] and not info.strip()


def _prose_lines(text: str) -> List[Tuple[int, str]]:
    """(1-based line number, line) for every line outside fenced and indented code."""
    out: List[Tuple[int, str]] = []
    fence: Optional[Tuple[str, int]] = None
    in_list = False
    code_may_start = True  # an indented line starts code only after a blank line or other code
    for number, line in enumerate(_lines(text), start=1):
        if fence:
            if _closes_fence(line, fence):
                fence = None
            code_may_start = True
            continue
        fence = _fence_opener(line, in_list)
        if fence:
            continue
        blank = not line.strip()
        if _LIST_START_RE.match(line):
            in_list = True
        elif not blank and line[0] not in " \t":
            in_list = False
        indented_code = (not blank and line.startswith(("    ", "\t"))
                         and code_may_start and not in_list)
        code_may_start = blank or indented_code
        if not indented_code:
            out.append((number, line))
    return out


def _frontmatter(text: str) -> Tuple[Optional[Dict], Optional[str]]:
    """(mapping, None), or (None, the cause of the failure)."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None, _missing_block_cause(text)
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as error:
        problem = getattr(error, "problem", None) or type(error).__name__
        return None, f"invalid YAML ({problem})"
    except RecursionError:
        return None, "the YAML is nested too deeply to parse"
    if data is None:
        return None, "the frontmatter block is empty"
    if not isinstance(data, dict):
        return None, f"the frontmatter is a {type(data).__name__}, not a mapping of keys"
    return data, None


def _missing_block_cause(text: str) -> str:
    if text.startswith("﻿"):
        return "the file starts with a byte-order mark; save it without one"
    if text.startswith("---\r\n"):
        return "the file uses CRLF line endings; use LF"
    if text.startswith("---\n---"):
        return "the frontmatter block is empty"
    return "no frontmatter block (the first line must be '---' and a closing '---' must follow)"


def _github_anchors(headings: List[str]) -> List[str]:
    """GitHub-style anchors: lowercase, drop punctuation except '-', spaces to '-'."""
    seen: Counter = Counter()
    anchors = []
    for heading in headings:
        base = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        anchors.append(base if seen[base] == 0 else f"{base}-{seen[base]}")
        seen[base] += 1
    return anchors


def _heading_text(raw: str) -> str:
    """Heading text without surrounding spaces and without a closing run of '#'."""
    text = raw.strip()
    unclosed = text.rstrip("#")
    if unclosed != text and (not unclosed or unclosed[-1] in " \t"):
        return unclosed.rstrip()
    return text


def _headings(text: str, pattern: "re.Pattern[str]") -> List[str]:
    found = (pattern.match(line) for _, line in _prose_lines(text))
    return [heading for match in found if match and (heading := _heading_text(match.group(1)))]


def _check_skill_size(text: str) -> List[Finding]:
    findings = []
    lines = count_lines(text)
    if lines > MAX_SKILL_LINES:
        findings.append(("skill-lines", f"{lines} lines exceeds the {MAX_SKILL_LINES} line limit"))
    tokens = int(len(text.encode("utf-8")) / BYTES_PER_TOKEN)
    if tokens > MAX_SKILL_TOKENS:
        findings.append((
            "skill-tokens",
            f"~{tokens} estimated tokens (bytes / {BYTES_PER_TOKEN}) exceeds the {MAX_SKILL_TOKENS} token limit"))
    return findings


def _description_length(frontmatter: Dict) -> int:
    return len(" ".join(str(frontmatter.get("description") or "").split()))


def _check_description_length(frontmatter: Dict) -> List[Finding]:
    length = _description_length(frontmatter)
    if length <= MAX_DESCRIPTION_CHARS:
        return []
    return [("description-length", f"description is {length} characters, over the {MAX_DESCRIPTION_CHARS} limit")]


def _check_description_brevity(frontmatter: Dict) -> List[Finding]:
    length = _description_length(frontmatter)
    if not WARN_DESCRIPTION_CHARS < length <= MAX_DESCRIPTION_CHARS:
        return []
    return [("description-length", f"description is {length} characters, over the recommended {WARN_DESCRIPTION_CHARS}")]


def _check_frontmatter_keys(frontmatter: Dict) -> List[Finding]:
    return [
        ("frontmatter-key", f"key '{key}' is not allowed; allowed keys: {', '.join(ALLOWED_FRONTMATTER_KEYS)}")
        for key in frontmatter if key not in ALLOWED_FRONTMATTER_KEYS
    ]


def _listed_anchors(lines: List[str]) -> List[str]:
    """Anchors linked from the list that follows the contents heading."""
    listed: List[str] = []
    in_item = False
    for line in lines:
        if not line.strip():
            continue
        if _LIST_ITEM_RE.match(line):
            in_item = True
        elif not (in_item and line[0] in " \t"):  # an indented line continues the current item
            break
        listed.extend(_TOC_LINK_RE.findall(line))
    return listed


def _check_toc(text: str) -> List[Finding]:
    lines = _lines(text)
    if len(lines) <= TOC_REQUIRED_OVER_LINES:
        return []
    count = f"{len(lines)} lines"
    contents_at = next(
        (i for i, line in enumerate(lines[:TOC_WINDOW_LINES]) if _CONTENTS_RE.match(line)), None)
    if contents_at is None:
        return [("toc", f"{count} but no '## Contents' or '## Table of Contents' heading in the first {TOC_WINDOW_LINES} lines")]

    headings = _headings(text, _HEADING_RE)
    expected = _github_anchors([h for h in headings if not _CONTENTS_RE.match(f"## {h}")])
    listed = _listed_anchors(lines[contents_at + 1:])
    if not listed:
        return [("toc", f"{count} and the contents list is empty (expected {len(expected)} links)")]
    if listed != expected:
        missing = [a for a in expected if a not in listed]
        extra = [a for a in listed if a not in expected]
        detail = f"missing {missing}, unexpected {extra}" if (missing or extra) else "links are out of order"
        subheadings = [a for a in _github_anchors(_headings(text, _SUBHEADING_RE)) if a in extra]
        if subheadings:
            detail += f"; list only `##` headings, not `###` ({subheadings})"
        return [("toc", f"{count} and the contents list is stale: {detail}")]
    return []


def _link_destinations(line: str) -> List[str]:
    definition = _DEFINITION_RE.match(line)
    if definition:
        return [definition.group(1)]
    return _LINK_RE.findall(_INLINE_CODE_RE.sub("", line))


def _relative_targets(text: str) -> List[str]:
    """Relative link targets (fragment and query removed, percent-decoded), outside code."""
    targets: Dict[str, None] = {}
    for _, line in _prose_lines(text):
        for raw in _link_destinations(line):
            target = unquote(re.split(r"[#?]", raw, maxsplit=1)[0])
            if target and not target.startswith("/") and not _SCHEME_RE.match(target):
                targets[target] = None
    return list(targets)


def _check_links(path: Path, text: str, is_reference: bool, skill_path: Path) -> List[Finding]:
    findings = []
    skill_root = skill_path.resolve()
    own_path = path.resolve()
    for target in _relative_targets(text):
        try:
            resolved = (path.parent / target).resolve()
        except (ValueError, OSError):
            findings.append(("broken-link", f"links to '{target}' which is not a valid path; fix the path or remove the link"))
            continue
        if (is_reference and target.lower().endswith(".md")
                and resolved.name != "SKILL.md" and resolved != own_path):
            findings.append((
                "reference-nesting",
                f"links to another reference file '{target}' (resolves to {_display(resolved, skill_path.parent)}); "
                "link every reference from SKILL.md instead"))
        if not resolved.is_relative_to(skill_root):
            findings.append((
                "link-outside-skill",
                f"links to '{target}' which resolves outside this skill; keep links inside the skill directory"))
        elif not resolved.exists():
            findings.append((
                "broken-link",
                f"links to '{target}' which does not exist (resolves to {_display(resolved, skill_path.parent)}); "
                "fix the path or remove the link"))
    return findings


def _display(path: Path, skills_root: Path) -> str:
    try:
        return str(path.relative_to(skills_root.resolve()))
    except ValueError:
        return "a path outside the skills directory"


def _reference_files(skill_path: Path) -> Iterator[Path]:
    """Regular .md files under the skill, except SKILL.md; symlinks are skipped."""
    root = skill_path.resolve()
    for ref in sorted(skill_path.rglob("*.md")):
        if ref == skill_path / "SKILL.md" or ref.is_symlink() or not ref.is_file():
            continue
        if ref.resolve().is_relative_to(root):
            yield ref


def check_skill_dir(skill_path: Path) -> Tuple[List[ValidationError], List[ValidationWarning]]:
    """Apply every skill rule to SKILL.md and each reference file of one skill."""
    errors: List[ValidationError] = []
    warnings: List[ValidationWarning] = []

    def add(label: str, findings: List[Finding], target: list, kind) -> None:
        target.extend(kind(label, f"{rule}: {message}") for rule, message in findings)

    skill_md = skill_path / "SKILL.md"
    label = f"{skill_path.name}/SKILL.md"
    text, problem = read_markdown(skill_md)
    if text is None:
        add(label, [("file-unreadable", f"the file {problem}")], errors, ValidationError)
    else:
        frontmatter, cause = _frontmatter(text)
        if frontmatter is None:
            add(label, [("frontmatter-parse", cause)], errors, ValidationError)
        else:
            add(label, _check_frontmatter_keys(frontmatter), errors, ValidationError)
            add(label, _check_description_length(frontmatter), errors, ValidationError)
            add(label, _check_description_brevity(frontmatter), warnings, ValidationWarning)
        add(label, _check_skill_size(text), errors, ValidationError)
        add(label, _check_links(skill_md, text, False, skill_path), errors, ValidationError)

    for ref in _reference_files(skill_path):
        ref_label = f"{skill_path.name}/{ref.relative_to(skill_path).as_posix()}"
        ref_text, problem = read_markdown(ref)
        if ref_text is None:
            add(ref_label, [("file-unreadable", f"the file {problem}")], errors, ValidationError)
            continue
        add(ref_label, _check_toc(ref_text), errors, ValidationError)
        add(ref_label, _check_links(ref, ref_text, True, skill_path), errors, ValidationError)

    return errors, warnings
