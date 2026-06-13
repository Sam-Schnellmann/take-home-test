import anthropic
import streamlit as st
 
from config import PASS, REVIEW, FAIL, ANTHROPIC_MODEL, FIELD_LABELS
 
# Anthropic client
_client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
 
 
def _build_prompt(validation_result: dict, filename: str) -> str:
    # Build a concise prompt describing what went wrong on the label.
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
        lines.append("One or more fields require manual review:")
        for field in ["brand_name", "government_warning"]:
            r = validation_result.get(field, {})
            if r.get("status") == REVIEW:
                lines.append(f"  - {FIELD_LABELS[field]}: {r['message']}")
        lines.append("")
        lines.append(
            "You are a TTB compliance assistant. In 2-4 concise sentences, explain "
            "what needs to be manually verified and what the agent should look for. "
            "Be specific. Do not add pleasantries or preamble."
        )
 
    return "\n".join(lines)

def get_government_warning_analysis(extracted: str, canonical: str) -> str:
    """
    Ask Claude Haiku to identify specific differences between extracted and canonical
    government warning text. Returns a concise explanation like:
    - "I can't find the period after 'defects'"
    - "I see 'problems' spelled as 'problem'"
    - "These are bullet points (•) rather than numbered (1)(2)"
    """
    prompt = f"""You are comparing two versions of a government warning text.

EXTRACTED (what OCR read from the label):
{extracted}

CANONICAL (what should be on the label):
{canonical}

In 1-2 concise sentences, identify the specific differences. Be concrete:
- "I can't find the period after 'defects'"
- "I see 'impairs' spelled as 'impares'"
- "These use bullet points (•) rather than numbers (1)(2)"
- "Some words are capitalized differently"

Do not mention similarity scores or general image quality. Focus on the TEXT differences only."""

    try:
        response = _client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception:
        return ""
 
 
def get_explanation(validation_result: dict, filename: str = "label") -> str:
    """
    Returns a plain-text explanation string from Claude.
    Empty string for PASS results (no explanation needed).
    Fallback message if the API call fails.
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
            f"(AI explanation unavailable — check ANTHROPIC_API_KEY. Error: {e})\n\n"
            "Manual review required based on the field results above."
        )