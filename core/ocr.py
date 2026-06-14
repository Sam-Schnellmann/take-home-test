import io
import base64
import json

import anthropic
import streamlit as st
from PIL import Image

from config import ANTHROPIC_MODEL

# Anthropic client
_client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])


# ── Image prep ────────────────────────────────────────────────────────────────

def _pil_to_base64(pil_image: Image.Image) -> str:
    """
    Resize the image so its longest side is at most 1600px, then encode
    as JPEG (quality 92) for the API.

    Why JPEG instead of PNG?
      Large label photos saved as PNG can be 15–20 MB in base64, which
      causes the Anthropic API call to fail silently. JPEG at quality 92
      keeps the file small enough to send reliably while preserving enough
      detail for Haiku to read text accurately.
    """
    # Cap the longest side at 1600px — enough for text, not too big to send
    max_side = 1600
    w, h     = pil_image.size
    if max(w, h) > max_side:
        scale  = max_side / max(w, h)
        pil_image = pil_image.resize(
            (int(w * scale), int(h * scale)),
            Image.LANCZOS,
        )

    buf = io.BytesIO()
    pil_image.convert("RGB").save(buf, format="JPEG", quality=92)
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")


# ── Main pipeline ─────────────────────────────────────────────────────────────

def process_image(pil_image: Image.Image) -> dict:
    """
    Send a label image to Claude Haiku and get back structured field data.

    Returns a dict with:
      - raw_text:           everything Haiku read (for diagnostics)
      - brand_name:         extracted brand name, or None
      - abv:                numeric ABV string e.g. "13.5", or None
      - government_warning: full warning block, or None
      - secondary:          dict of secondary field extractions
    """
    img_b64 = _pil_to_base64(pil_image)

    prompt = """You are an alcohol label reader. Carefully examine this label image and extract the text fields listed below. The label may have two panels (front and back) — read both.

IMPORTANT: Some labels are photographed on curved bottles, in low lighting, or at an angle. Read as carefully as possible. For the government warning block, extract every word you can see — do not skip lines even if they are faint.

Return ONLY a valid JSON object with exactly these keys. Do not include any explanation, markdown, or code fences — just the raw JSON.

{
  "raw_text": "<all visible text on the label, exactly as printed>",
  "brand_name": "<the brand or product name, exactly as it appears — preserve capitalization>",
  "abv": "<the numeric ABV value only — e.g. 4.2 — no % sign, no units>",
  "government_warning": "<the full government warning block, exactly as printed including header>"
}

VERBATIM TEXT RULE:
All extracted text must be copied exactly as it appears on the label, including all punctuation (periods, commas, colons, apostrophes, quotation marks, parentheses) and line breaks. Do not normalize or remove punctuation.

NO EDITING RULE:
Do not correct spelling, grammar, spacing, or punctuation. Do not guess unclear characters.

CRITICAL EXTRACTION RULES:

For brand_name:
- Copy the brand/product name EXACTLY as it appears on the label.
- Preserve every capital and lowercase letter. "STONE'S THROW" and "Stone's Throw" are different.

For abv:
- TTB-compliant labels state ABV in one of these formats:
    "Alcohol X% by Volume" OR "X% Alc. by Vol." OR "X% Alc./Vol."
- Extract ONLY the number (e.g. 4.2, 13.5, 40). Do not include the % sign or any words.
- If you see a percentage on the label that looks like an alcohol content, that is the ABV.
- On cans the ABV is often printed on the side panel — look carefully

For government_warning:
- The header "GOVERNMENT WARNING:" must be in ALL CAPS and hold on the label.
- The body has two numbered statements: (1) the Surgeon General pregnancy warning and (2) the impairment warning.
- Copy the ENTIRE block exactly as it is printed. Do not summarize or paraphrase.
- Even if the text is small or partially obscured, extract every word you can see.

Use null (JSON null, not the string "null") for any field you cannot find."""

    try:
        response = _client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type":       "base64",
                                "media_type": "image/jpeg",
                                "data":       img_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        )

        raw_json = response.content[0].text.strip()

        # Strip accidental markdown fences if the model added them
        if raw_json.startswith("```"):
            raw_json = raw_json.split("```")[1]
            if raw_json.startswith("json"):
                raw_json = raw_json[4:]
            raw_json = raw_json.strip()

        data = json.loads(raw_json)

        return {
            "raw_text":           data.get("raw_text") or "",
            "brand_name":         data.get("brand_name") or None,
            "abv":                data.get("abv") or None,
            "government_warning": data.get("government_warning") or None,
        }

    except Exception as e:
        # Show the real error in the app so it's not silent
        st.error(f"OCR error on this image: {e}")
        return {
            "raw_text":           "",
            "brand_name":         None,
            "abv":                None,
            "government_warning": None,
            "_error":             str(e),
        }