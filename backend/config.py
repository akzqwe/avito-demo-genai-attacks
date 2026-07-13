"""Defense toggles — flip from the admin panel to demo mitigations live."""
from dataclasses import dataclass


@dataclass
class Defenses:
    # Strip obvious "system-looking" markers from tool outputs before they reach the LLM.
    sanitize_tool_output: bool = False
    # Sanitize note arguments before storing (strip HTML).
    sanitize_note_arg: bool = False
    # Escape notes when rendering in the admin panel.
    escape_admin_render: bool = False
    # Require human-in-the-loop confirmation for add_internal_note.
    require_confirmation: bool = False
    # Wrap untrusted description text in <untrusted_data> tags so detectors skip matches inside.
    segregate_data_instructions: bool = False
    # dump_diagnostic returns [REDACTED] instead of system prompt excerpt + admin secrets.
    redact_system_prompt: bool = False
    # search_knowledge_base penalizes UGC entries (-0.5 to overlap score).
    rerank_kb_by_provenance: bool = False


defenses = Defenses()
