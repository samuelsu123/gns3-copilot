"""
Tests for clarification option parser helpers.
"""

from gns3_copilot.ui_model.utils.clarification_options import (
    parse_clarification_question_from_text,
    strip_clarification_blocks_from_text,
)


def test_parse_clarification_question_from_valid_block() -> None:
    text = """
Please choose one:
```clarify_options
{
  "kind": "clarification_choice",
  "question_id": "wan_ip_mode",
  "question": "WAN mode?",
  "options": [
    {"id": "A", "label": "DHCP", "value": "WAN uses DHCP"},
    {"id": "B", "label": "Static", "value": "WAN uses static IP"}
  ],
  "allow_free_text": true
}
```
"""
    parsed = parse_clarification_question_from_text(text)
    assert parsed is not None
    assert parsed["question_id"] == "wan_ip_mode"
    assert parsed["question"] == "WAN mode?"
    assert len(parsed["options"]) == 2
    assert parsed["allow_free_text"] is True


def test_parse_returns_none_when_options_count_out_of_range() -> None:
    text = """
```clarify_options
{
  "kind": "clarification_choice",
  "question_id": "dns_mode",
  "question": "DNS mode?",
  "options": [
    {"id": "A", "label": "Auto", "value": "DNS auto"}
  ],
  "allow_free_text": true
}
```
"""
    assert parse_clarification_question_from_text(text) is None


def test_parse_returns_first_valid_block_when_previous_block_invalid() -> None:
    text = """
```clarify_options
{
  "kind": "clarification_choice",
  "question_id": "invalid",
  "question": "Invalid options",
  "options": [
    {"id": "A", "label": "Only", "value": "only one"}
  ],
  "allow_free_text": true
}
```

```clarify_options
{
  "kind": "clarification_choice",
  "question_id": "wan_auth",
  "question": "WAN auth?",
  "options": [
    {"id": "A", "label": "None", "value": "No WAN auth"},
    {"id": "B", "label": "PPPoE", "value": "WAN uses PPPoE auth"}
  ],
  "allow_free_text": false
}
```
"""
    parsed = parse_clarification_question_from_text(text)
    assert parsed is not None
    assert parsed["question_id"] == "wan_auth"
    assert parsed["allow_free_text"] is False


def test_parse_returns_none_for_non_matching_kind() -> None:
    text = """
```clarify_options
{
  "kind": "other_kind",
  "question_id": "wan_auth",
  "question": "WAN auth?",
  "options": [
    {"id": "A", "label": "None", "value": "No WAN auth"},
    {"id": "B", "label": "PPPoE", "value": "WAN uses PPPoE auth"}
  ],
  "allow_free_text": true
}
```
"""
    assert parse_clarification_question_from_text(text) is None


def test_parse_supports_apostrophe_fence() -> None:
    text = """
'''clarify_options
{
  "kind": "clarification_choice",
  "question_id": "wan_mode",
  "question": "WAN mode?",
  "options": [
    {"id": "A", "label": "DHCP", "value": "WAN uses DHCP"},
    {"id": "B", "label": "Static", "value": "WAN uses static IP"}
  ],
  "allow_free_text": true
}
'''
"""
    parsed = parse_clarification_question_from_text(text)
    assert parsed is not None
    assert parsed["question_id"] == "wan_mode"


def test_parse_supports_bare_json_payload() -> None:
    text = """
{
  "kind": "clarification_choice",
  "question_id": "dns_mode",
  "question": "DNS mode?",
  "options": [
    {"id": "A", "label": "Auto", "value": "DNS auto"},
    {"id": "B", "label": "Manual", "value": "DNS manual"}
  ],
  "allow_free_text": false
}
"""
    parsed = parse_clarification_question_from_text(text)
    assert parsed is not None
    assert parsed["question_id"] == "dns_mode"


def test_strip_clarification_blocks_removes_protocol_block() -> None:
    text = """
我来帮您配置。

```clarify_options
{
  "kind": "clarification_choice",
  "question_id": "wan_mode",
  "question": "WAN mode?",
  "options": [
    {"id": "A", "label": "DHCP", "value": "WAN uses DHCP"},
    {"id": "B", "label": "Static", "value": "WAN uses static IP"}
  ],
  "allow_free_text": true
}
```
"""
    cleaned = strip_clarification_blocks_from_text(text)
    assert cleaned == "我来帮您配置。"
