import os
import re
import cv2
import numpy as np
import pytesseract
from PIL import Image

from config import TESSERACT_CMD

# Point pytesseract at windows binary if the path is set
if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# image processing and OCR functions
def preprocess_image(pil_image: Image.Image) -> np.ndarray:
    """
    Convert a PIL image to a cleaned-up grayscale numpy array ready for
    Tesseract. Applies: grayscale -> resize up -> denoise -> adaptive threshold.
    Returns the processed image as a numpy array.
    """
    img = np.array(pil_image.convert("RGB"))
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    # Scale up
    h, w = gray.shape
    if max(h, w) < 1200:
        scale = 1200 / max(h, w)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    
    # Denoise
    gray = cv2.fastNlMeansDenoising(gray, h=15)

    # Adaptive threshold
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11,
        2,
    )

    return binary

# OCR function
def extract_raw_text(pil_image: Image.Image) -> str:
    """
    Run tesseract on a PIL image and return the raw text string.
    The image is preprocessed first. Whitespace is normalized but
    line structure is kept so field extractors can search by line.
    """
    processed = preprocess_image(pil_image)
    config = "--oem 3 --psm 6" # uniform block of text
    raw = pytesseract.image_to_string(processed, config=config)
    return raw

# Field extraction helpers
def normalize_whitespace(text: str) -> str:
    """
    Collapse all whitespace / new lines into single spaces.
    """
    return " ".join(text.split())

def extract_brand_name(raw_text: str) -> str | None:
    """
    Attempt to find the brand name. Strategy: the brand name is usually the
    largest / first prominent text block, often on its own line near the top.
    We return the first non-empty, non-numeric line that is fewer than 60 chars.
    Callers compare this against the user-supplied expected value.
    Returns None if nothing plausible is found.
    """
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    for line in lines:
        # Skip lines that are purely numbers / symbols
        if re.fullmatch(r"[\d\W]+", line):
            continue
        # Skip lines longer than a reasonable brand name
        if len(line) > 60:
            continue
        return line
    return None
 
 
def extract_abv(raw_text: str) -> str | None:
    """
    Find an ABV percentage in the raw OCR text.
    Looks for patterns like: 13.5%, 13.5% ALC/VOL, ALC. 13.5% BY VOL, etc.
    Returns just the numeric string (e.g. "13.5") or None.
    """
    pattern = re.compile(
        r"(?:ALC(?:OHOL)?\.?\s*(?:BY\s*VOL(?:UME)?)?\.?\s*)?"
        r"(\d{1,2}(?:\.\d{1,2})?)\s*%",
        re.IGNORECASE,
    )
    match = pattern.search(raw_text)
    if match:
        return match.group(1)
    return None
 
 
def extract_government_warning(raw_text: str) -> str | None:
    """
    Find and return the full government warning block from the OCR text.
    Searches for 'GOVERNMENT WARNING' (case-insensitive for location only)
    then grabs everything from that point to the end of the warning block.
    Returns the extracted text normalized to single-spaced, or None.
    """
    # Find the start position — case-insensitive search for location
    upper = raw_text.upper()
    start = upper.find("GOVERNMENT WARNING")
    if start == -1:
        return None
 
    # Take text from that point onward, up to ~600 chars (warning is ~400 chars)
    candidate = raw_text[start : start + 650]
    return normalize_whitespace(candidate)
 
 
def extract_secondary_fields(raw_text: str) -> dict[str, str | None]:
    """
    Best-effort extraction of secondary label fields using pattern matching.
    Returns a dict of field_key → extracted string (or None if not found).
    These are used for REVIEW logic only — no exact-match required.
    """
    text_upper = raw_text.upper()
    results = {}
 
    # Bottler / producer line — look for keywords
    bottler_pattern = re.compile(
        r"((?:BOTTLED|PRODUCED|VINTED|IMPORTED)\s+(?:BY|FOR|AND\s+BOTTLED\s+BY)[^\n]{5,80})",
        re.IGNORECASE,
    )
    m = bottler_pattern.search(raw_text)
    results["bottler_name_address"] = normalize_whitespace(m.group(1)) if m else None
 
    # Varietal designation — common wine/spirit type words
    varietal_pattern = re.compile(
        r"\b(CABERNET|MERLOT|CHARDONNAY|PINOT|RIESLING|SAUVIGNON|ZINFANDEL|"
        r"MALBEC|SYRAH|SHIRAZ|BOURBON|WHISKEY|WHISKY|VODKA|RUM|GIN|TEQUILA|"
        r"BRANDY|COGNAC|SCOTCH|LAGER|ALE|STOUT|IPA|PORTER)\b",
        re.IGNORECASE,
    )
    m = varietal_pattern.search(raw_text)
    results["varietal_designation"] = m.group(0).title() if m else None
 
    # Appellation of origin — State / country / AVA patterns
    appellation_pattern = re.compile(
        r"\b(NAPA VALLEY|SONOMA|BURGUNDY|BORDEAUX|TUSCANY|RIOJA|CALIFORNIA|"
        r"OREGON|WASHINGTON|FRANCE|ITALY|SPAIN|AUSTRALIA|CHILE|ARGENTINA|"
        r"KENTUCKY|TENNESSEE|SCOTLAND|IRELAND|MEXICO)\b",
        re.IGNORECASE,
    )
    m = appellation_pattern.search(raw_text)
    results["appellation_of_origin"] = m.group(0).title() if m else None
 
    # Vintage date — 4-digit year between 1900 and 2099
    vintage_pattern = re.compile(r"\b(19\d{2}|20\d{2})\b")
    m = vintage_pattern.search(raw_text)
    results["vintage_date"] = m.group(1) if m else None
 
    # Net volume — e.g. 750 mL, 1.5L, 750ML
    volume_pattern = re.compile(
        r"(\d{1,4}(?:\.\d{1,2})?\s*(?:ML|mL|L|liters?|litres?))",
        re.IGNORECASE,
    )
    m = volume_pattern.search(raw_text)
    results["net_volume"] = normalize_whitespace(m.group(1)) if m else None
 
    # Sulfite declaration
    sulfite_pattern = re.compile(
        r"(CONTAINS?\s+SULFITES?|CONTAINS?\s+ADDED\s+SULFITES?)",
        re.IGNORECASE,
    )
    m = sulfite_pattern.search(raw_text)
    results["sulfite_declaration"] = m.group(0).title() if m else None
 
    return results
 
 
# Main
def process_image(pil_image: Image.Image) -> dict:
    """
    Full OCR pipeline for a single label image.
    Returns a dict with:
      - raw_text: everything Tesseract saw
      - brand_name, abv, government_warning: extracted Big 3 values (or None)
      - secondary: dict of secondary field extractions
    """
    raw = extract_raw_text(pil_image)
    return {
        "raw_text":          raw,
        "brand_name":        extract_brand_name(raw),
        "abv":               extract_abv(raw),
        "government_warning":extract_government_warning(raw),
        "secondary":         extract_secondary_fields(raw),
    }