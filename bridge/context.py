"""
Context validation and prompt assembly.
Takes structured context from the widget, serializes it into
natural language that gets injected into the system prompt.
"""

import json
import logging

logger = logging.getLogger("zgx-bridge.context")


def validate_context(context: dict | None, max_size_bytes: int) -> dict:
    """
    Validate and sanitize incoming context from the widget.
    Drops unknown/oversized fields, logs warnings.
    Returns cleaned context dict (may be empty).
    """
    if not context:
        return {}

    serialized = json.dumps(context)
    if len(serialized.encode("utf-8")) > max_size_bytes:
        logger.warning(
            "Context exceeds max size (%d bytes). Truncating.",
            len(serialized.encode("utf-8")),
        )
        # Drop visibleData first (usually the largest field)
        context = {k: v for k, v in context.items() if k != "visibleData"}
        serialized = json.dumps(context)
        if len(serialized.encode("utf-8")) > max_size_bytes:
            logger.warning("Context still too large after dropping visibleData. Using empty context.")
            return {}

    return context


def context_to_text(context: dict) -> str:
    """
    Convert structured context into a natural language block
    for injection into the system prompt.

    This is the core serialization layer. The quality of the AI's
    contextual answers depends on how well this renders the context.
    """
    if not context:
        return ""

    parts = []

    # Document/page level
    doc_name = context.get("documentName")
    page_type = context.get("pageType")
    page = context.get("page")
    url = context.get("url")

    if doc_name:
        parts.append(f"The user is viewing a document called \"{doc_name}\".")
    if page:
        parts.append(f"They are on the \"{page}\" page.")
    if page_type and page_type != "unknown":
        parts.append(f"Page type: {page_type}.")

    # Tab info (Onshape-specific: Part Studios, Assemblies, etc.)
    tab_info = context.get("tabInfo")
    if tab_info and isinstance(tab_info, list) and len(tab_info) > 0:
        tabs_str = ", ".join(tab_info)
        parts.append(f"Available workspace tabs: {tabs_str}.")

    # Feature tree (CAD-specific)
    feature_tree = context.get("featureTree")
    if feature_tree and isinstance(feature_tree, list) and len(feature_tree) > 0:
        features_str = ", ".join(feature_tree)
        parts.append(f"The feature tree contains: {features_str}.")

    # User role
    user_role = context.get("userRole")
    if user_role:
        parts.append(f"The user's role is: {user_role}.")

    # Record info
    record_id = context.get("recordId")
    if record_id:
        parts.append(f"Currently selected record: {record_id}.")

    # Visible data (the rich payload from the ISV)
    visible_data = context.get("visibleData")
    if visible_data and isinstance(visible_data, dict):
        parts.append("Currently visible data:")
        for key, value in visible_data.items():
            if isinstance(value, (list, dict)):
                parts.append(f"  - {key}: {json.dumps(value)}")
            else:
                parts.append(f"  - {key}: {value}")

    # Catch-all for any other fields we didn't explicitly handle
    known_keys = {
        "documentName", "pageType", "page", "url", "tabInfo",
        "featureTree", "userRole", "recordId", "visibleData",
        "documentId", "timestamp",
    }
    extra = {k: v for k, v in context.items() if k not in known_keys}
    if extra:
        parts.append("Additional context:")
        for key, value in extra.items():
            parts.append(f"  - {key}: {value}")

    return "\n".join(parts)


def build_system_prompt(base_prompt: str, context: dict) -> str:
    """
    Assemble the full system prompt from base + context.
    """
    context_text = context_to_text(context)
    if not context_text:
        return base_prompt

    return (
        f"{base_prompt}\n\n"
        f"--- Application Context ---\n"
        f"{context_text}\n"
        f"--- End Context ---"
    )
