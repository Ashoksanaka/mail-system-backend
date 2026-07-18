# ──────────────────────────────────────────────────────────────
# Core — Shared Utility Functions
# Utility functions used across multiple apps
# ──────────────────────────────────────────────────────────────
import csv
import io
import logging
import re

logger = logging.getLogger(__name__)

# Captures placeholder names inside {{...}}; underscore-style identifiers only
# (letters, digits, underscores). Optional whitespace around the name is allowed.
PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def format_email_count(count):
    """Format large email counts for display (e.g., 1.2K, 3.5M)."""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    elif count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return str(count)


def extract_placeholders(template_body: str) -> list[str]:
    """
    Extract all unique placeholder names from a template body string.
    Placeholders are denoted by {{placeholder_name}} (underscore-style only).
    Returns a list of unique names in order of first appearance.

    Example:
        Input:  "Hello {{name}}, contact {{Your_Contact_Info}}."
        Output: ["name", "Your_Contact_Info"]
    """
    if not template_body:
        return []

    matches = PLACEHOLDER_PATTERN.findall(template_body)
    stripped = [m.strip() for m in matches if m and m.strip()]
    return list(dict.fromkeys(stripped))


def generate_csv_content(placeholders: list[str]) -> str:
    """
    Generate CSV content string with headers only.
    First two columns are always: receiver_email_ID, receiver_name
    Remaining columns are the extracted placeholder names.
    Returns CSV as a string (not a file).
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Build header row: fixed columns + dynamic placeholder columns
    headers = ["receiver_email_ID", "receiver_name"] + placeholders
    writer.writerow(headers)

    return output.getvalue()


def fill_template(body: str, replacements: dict) -> str:
    """
    Replace all {{placeholder}} occurrences in body with values from
    the replacements dict. Tolerates optional spaces around the key
    inside the braces (e.g. {{ order_id }}).

    Example:
        body: "Hi {{name}}, your code is {{code}}"
        replacements: {"name": "Alice", "code": "XYZ"}
        output: "Hi Alice, your code is XYZ"

    Preserves all other content in the template exactly as-is.
    If a placeholder exists in the template but not in the replacements dict,
    it is left unreplaced and a warning is logged.
    """
    result = body

    all_placeholders = extract_placeholders(body)

    for placeholder in all_placeholders:
        if placeholder not in replacements:
            logger.warning(
                f"Placeholder '{{{{{placeholder}}}}}' found in template "
                f"but not provided in replacements dict — leaving unreplaced."
            )

    for key, value in replacements.items():
        pattern = re.compile(
            r"\{\{\s*" + re.escape(str(key)) + r"\s*\}\}"
        )
        result = pattern.sub(str(value), result)

    return result
