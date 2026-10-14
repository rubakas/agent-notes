"""Unit tests for the stream-json parser in runner.py. No live claude call."""
import json

from skill_evals.runner import judge, parse_stream, pick_entry

USAGE = {
    "input_tokens": 30,
    "cache_creation_input_tokens": 12268,
    "cache_read_input_tokens": 21098,
    "output_tokens": 462,
}


def _jsonl(*events):
    return [json.dumps(e) for e in events]


INIT = {"type": "system", "subtype": "init", "model": "claude-haiku-4-5"}
SKILL_CALL = {
    "type": "assistant",
    "message": {"content": [
        {"type": "text", "text": "I'll use the git skill."},
        {"type": "tool_use", "id": "t1", "name": "Skill", "input": {"skill": "git"}},
    ]},
}
TOOL_RESULT = {
    "type": "user",
    "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "Launching skill: git"}]},
}
RESULT = {"type": "result", "subtype": "success", "usage": USAGE, "total_cost_usd": 0.0289858}


def test_extracts_skill_usage_and_cost():
    parsed = parse_stream(_jsonl(INIT, SKILL_CALL, TOOL_RESULT, RESULT))
    assert parsed["skills"] == ["git"]
    assert parsed["usage"] == USAGE
    assert parsed["total_cost_usd"] == 0.0289858


def test_no_skill_call_gives_empty_list():
    text_only = {"type": "assistant", "message": {"content": [{"type": "text", "text": "Sure."}]}}
    parsed = parse_stream(_jsonl(INIT, text_only, RESULT))
    assert parsed["skills"] == []


def test_ignores_non_skill_tools():
    bash = {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "t2", "name": "Bash", "input": {"command": "git status"}},
    ]}}
    assert parse_stream(_jsonl(bash, RESULT))["skills"] == []


def test_repeated_skill_is_deduplicated_in_order():
    other = {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "t3", "name": "Skill", "input": {"skill": "code-review"}},
    ]}}
    parsed = parse_stream(_jsonl(SKILL_CALL, other, SKILL_CALL, RESULT))
    assert parsed["skills"] == ["git", "code-review"]


def test_slash_invocation_marker_counts_as_loaded():
    slash = {"type": "user", "message": {"content": [
        {"type": "text", "text": "<command-name>/to-tickets</command-name>\n<command-args>specs/012</command-args>"},
    ]}}
    assert parse_stream(_jsonl(slash, RESULT))["skills"] == ["to-tickets"]


def test_blank_and_malformed_lines_are_skipped():
    lines = ["", "not json at all", "[1, 2]"] + _jsonl(SKILL_CALL, RESULT)
    parsed = parse_stream(lines)
    assert parsed["skills"] == ["git"]
    assert parsed["usage"] == USAGE


def test_missing_result_event_gives_none():
    parsed = parse_stream(_jsonl(INIT, SKILL_CALL))
    assert parsed["usage"] is None
    assert parsed["total_cost_usd"] is None


def test_judge_by_category():
    assert judge("should_trigger", "git", ["git"])
    assert not judge("should_trigger", "git", [])
    assert not judge("should_trigger", "git", ["code-review"])
    assert judge("near_miss", "git", [])
    assert judge("near_miss", "git", ["code-review"])
    assert not judge("near_miss", "git", ["git"])


def test_pick_entry_indexes_within_skill():
    entries = [
        {"skill": "a", "prompt": "a0"},
        {"skill": "b", "prompt": "b0"},
        {"skill": "a", "prompt": "a1"},
    ]
    assert pick_entry(entries, "a", 1)["prompt"] == "a1"
