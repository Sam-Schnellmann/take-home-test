import io
import base64
import json
 
import anthropic
from PIL import Image
 
from config import ANTHROPIC_MODEL

import streamlit as st
 
# using Claude because it's easier to just give someone a link to this app instead
# of them having to download Google's Tesseract OCR
_client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
 
 
def _pil_to_base64(pil_image: Image.Image) -> str:
    # Convert this PIL image to a base64-encoded PNG string for the API.
    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")
 
 
def process_image(pil_image: Image.Image) -> dict:
    """
    Full OCR pipeline for a single label image using Claude.
 
    Sends the image to the Anthropic API. Asks for structured JSON extraction
    of all label fields. No local Tesseract install required.
 
    Returns a dict with:
      - raw_text:           everything Claude read from the label (for diagnostics)
      - brand_name:         extracted brand name string, or None
      - abv:                numeric ABV string (e.g. "13.5"), or None
      - government_warning: full government warning text, or None
      - secondary:          dict of secondary field extractions
    """
    img_b64 = _pil_to_base64(pil_image)
 
    prompt = """You are an alcohol label reader. Carefully examine this label image and extract the text fields listed below. The label may have two panels (front and back) — read both.
 
Return ONLY a valid JSON object with exactly these keys. Do not include any explanation, markdown, or code fences — just the raw JSON.
 
{
  "raw_text": "<all visible text on the label, exactly as printed>",
  "brand_name": "<the brand or product name, exactly as it appears — preserve capitalization>",
  "abv": "<just the numeric ABV value, e.g. 13.5 — no % sign>",
  "government_warning": "<the full government warning block, exactly as printed including header>",
  "secondary": {
    "bottler_name_address": "<bottler or producer name and address, or null>",
    "varietal_designation": "<wine/spirit type e.g. Chardonnay, Bourbon, IPA, or null>",
    "appellation_of_origin": "<region/country of origin e.g. Napa Valley, Kentucky, or null>",
    "vintage_date": "<4-digit vintage year, or null>",
    "net_volume": "<volume with unit e.g. 750 mL, 1 PINT, or null>",
    "sulfite_declaration": "<sulfite statement if present, or null>"
  }
}
 
Use null (not the string "null") for any field you cannot find on the label.
For brand_name, preserve exact capitalization and punctuation as printed.
For abv, return only the number — no % sign, no units.
For government_warning, copy the full text exactly as it appears on the label."""
 
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
                                "media_type": "image/png",
                                "data":        img_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text":  prompt,
                        },
                    ],
                }
            ],
        )
 
        raw_json = response.content[0].text.strip()
 
        # Get rid of the markdown stuff
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
            "secondary":          data.get("secondary") or {},
        }
 
    except Exception as e:
        # return empty extraction rather than crash the app
        return {
            "raw_text":           "",
            "brand_name":         None,
            "abv":                None,
            "government_warning": None,
            "secondary":          {},
            "_error":             str(e),
        }