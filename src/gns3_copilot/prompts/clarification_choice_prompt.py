"""
Global clarification-choice prompt for single-question multi-option interaction.
"""

from __future__ import annotations


def build_clarification_choice_prompt() -> str:
    """Build global prompt rules for structured clarification choices."""
    prompt = """
### Clarification Choice Protocol

When any required information is missing, switch to structured clarification mode:

1. Ask exactly ONE question per turn.
2. Provide selectable options in a fenced block named `clarify_options`.
3. Use this JSON schema inside the block:
   {
     "kind": "clarification_choice",
     "question_id": "string",
     "question": "string",
     "options": [
       {"id": "A", "label": "shown to user", "value": "canonical answer text"}
     ],
     "allow_free_text": true
   }
4. `options` must contain 2-5 choices.
5. Keep each option label concise and mutually exclusive.
6. Wait for the user's selected answer before asking the next question.
7. Do not proceed to final configuration or execution until required information is complete.
8. If information is already sufficient, do not output a `clarify_options` block.

Output format example:
```clarify_options
{
  "kind": "clarification_choice",
  "question_id": "wan_ip_mode",
  "question": "How should the WAN interface get its IP address?",
  "options": [
    {"id": "A", "label": "DHCP (auto)", "value": "WAN interface uses DHCP"},
    {"id": "B", "label": "Static IP", "value": "WAN interface uses static IP"},
    {"id": "C", "label": "PPPoE", "value": "WAN interface uses PPPoE"}
  ],
  "allow_free_text": true
}
```
"""
    return prompt.strip()


CLARIFICATION_CHOICE_PROMPT = build_clarification_choice_prompt()
