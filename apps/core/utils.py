# ──────────────────────────────────────────────────────────────
# Core — Shared Utility Functions
# Utility functions used across multiple apps
# ──────────────────────────────────────────────────────────────
import csv
import io
import logging
import re

logger = logging.getLogger(__name__)


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
    Placeholders are denoted by {{placeholder_name}}.
    Returns a list of unique names in order of first appearance.
    Strips whitespace from inside the braces.

    Example:
        Input:  "Hello {{name}}, your order {{order_id}} is ready."
        Output: ["name", "order_id"]
    """
    # Find all matches of {{...}} pattern
    matches = re.findall(r"\{\{(\s*\w+\s*)\}\}", template_body)

    # Strip whitespace from each match
    stripped = [m.strip() for m in matches]

    # Deduplicate while preserving order using dict.fromkeys()
    unique = list(dict.fromkeys(stripped))

    return unique


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
    the replacements dict.

    Example:
        body: "Hi {{name}}, your code is {{code}}"
        replacements: {"name": "Alice", "code": "XYZ"}
        output: "Hi Alice, your code is XYZ"

    Preserves all other content in the template exactly as-is.
    If a placeholder exists in the template but not in the replacements dict,
    it is left unreplaced and a warning is logged.
    """
    result = body

    # First, find all placeholders in the body to check for missing ones
    all_placeholders = extract_placeholders(body)

    for placeholder in all_placeholders:
        if placeholder not in replacements:
            logger.warning(
                f"Placeholder '{{{{{placeholder}}}}}' found in template "
                f"but not provided in replacements dict — leaving unreplaced."
            )

    # Replace each provided placeholder with its value
    for key, value in replacements.items():
        result = result.replace(f"{{{{{key}}}}}", str(value))

    return result
