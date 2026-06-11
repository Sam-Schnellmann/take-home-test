import anthropic
 
from config import PASS, REVIEW, FAIL, ANTHROPIC_MODEL, FIELD_LABELS
 
# Anthropic client — reads ANTHROPIC_API_KEY from environment automatically
_client = anthropic.Anthropic()
 
 
def _build_prompt(validation_result: dict, filename: str) -> str:
    """Build a concise prompt describing what went wrong on the label."""
    overall = validation_result["overall"]
    lines = [f'Label file: "{filename}"', f"Overall result: {overall}", ""]
 
    if overall == FAIL:
        lines.append("The following required fields FAILED:")
        for field in ["brand_name", "abv", "government_warning"]:
            r = validation_result.get(field, {})
            if r.get("status") == FAIL:
                lines.append(f"  - {FIELD_LABELS[field]}: {r['message']}")
        lines.append("")
        lines.append(
            "You are a TTB compliance assistant. In 2-4 concise sentences, explain "
            "what the failure(s) mean and what the applicant needs to correct to resubmit. "
            "Be specific. Do not add pleasantries or preamble."
        )
 
    elif overall == REVIEW:
        missing = validation_result.get("missing_secondary", [])
        lines.append("The required fields (Brand Name, ABV, Government Warning) all passed.")
        lines.append("However, the following optional fields were not detected on the label:")
        for f in missing:
            lines.append(f"  - {f}")
        lines.append("")
        lines.append(
            "You are a TTB compliance assistant. In 2-4 concise sentences, explain "
            "what each missing field is, whether it is typically required for the beverage "
            "class, and what the agent should look for when manually reviewing the label. "
            "Be specific. Do not add pleasantries or preamble."
        )
 
    return "\n".join(lines)
 
 
def get_explanation(validation_result: dict, filename: str = "label") -> str:
    """
    Returns a plain-text explanation string from Claude Haiku.
    Returns an empty string for PASS results (no explanation needed).
    Returns a fallback message if the API call fails.
    """
    if validation_result["overall"] == PASS:
        return ""
 
    prompt = _build_prompt(validation_result, filename)
 
    try:
        response = _client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
 
    except Exception as e:
        return (
            f"(AI explanation unavailable — check your ANTHROPIC_API_KEY. Error: {e})\n\n"
            "Manual review required based on the field results above."
        )