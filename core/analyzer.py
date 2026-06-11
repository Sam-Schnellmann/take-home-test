import ollama
from config import PASS, REVIEW, FAIL, OLLAMA_MODEL, FIELD_LABELS
 
 
def _build_prompt(validation_result: dict, filename: str) -> str:
    overall = validation_result["overall"]
    lines = [f'Label file: "{filename}"', f"Overall result: {overall}", ""]
 
    if overall == FAIL:
        lines.append("The following required fields FAILED:")
        for field in ["brand_name", "abv", "government_warning"]:
            r = validation_result[field]
            if r["status"] == FAIL:
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
    Returns a plain-text explanation string from Ollama.
    Returns an empty string for PASS results (no explanation needed).
    Returns a fallback message if Ollama is unavailable.
    """
    if validation_result["overall"] == PASS:
        return ""
 
    prompt = _build_prompt(validation_result, filename)
 
    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return response["message"]["content"].strip()
    except Exception as e:
        # Ollama may not be running — degrade gracefully, don't crash the app
        return (
            f"(AI explanation unavailable — is Ollama running? Error: {e})\n\n"
            "Manual review required based on the field results above."
        )