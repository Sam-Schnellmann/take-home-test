import re
from rapidfuzz import fuzz
 
from config import (
    PASS, REVIEW, FAIL,
    GOVERNMENT_WARNING, GOVERNMENT_WARNING_HEADER,
    SECONDARY_FIELDS, FIELD_LABELS,
)
 
 
def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())
 
 
# ── Brand Name ────────────────────────────────────────────────────────────────
 
def validate_brand_name(extracted: str | None, expected: str) -> dict:
    """
    Exact, case-sensitive match after whitespace normalization.
    extracted: what the API pulled off the label
    expected:  what the user entered as the correct value
    """
    if not extracted:
        return {
            "status":    FAIL,
            "extracted": None,
            "expected":  expected,
            "message":   "Brand name could not be read from the label.",
        }
 
    extracted_norm = normalize_whitespace(extracted)
    expected_norm  = normalize_whitespace(expected)
 
    if extracted_norm == expected_norm:
        return {
            "status":    PASS,
            "extracted": extracted_norm,
            "expected":  expected_norm,
            "message":   "Brand name matches expected value.",
        }
 
    # Give the agent a useful diff hint
    if extracted_norm.upper() == expected_norm.upper():
        hint = "Capitalization mismatch: check case on every word."
    else:
        hint = f'Label reads "{extracted_norm}", expected "{expected_norm}".'
 
    return {
        "status":    FAIL,
        "extracted": extracted_norm,
        "expected":  expected_norm,
        "message":   hint,
    }
 
 
# ── ABV ───────────────────────────────────────────────────────────────────────
 
def validate_abv(extracted: str | None, expected: str) -> dict:
    """
    Numeric comparison of ABV percentages.
    extracted : numeric string from the API (e.g. "13.5")
    expected  : what the user typed (e.g. "13.5" or "13.5%")
    """
    expected_clean = re.sub(r"[%\s]", "", expected).strip()
 
    if not extracted:
        return {
            "status":    FAIL,
            "extracted": None,
            "expected":  expected_clean,
            "message":   "ABV percentage could not be read from the label.",
        }
 
    try:
        extracted_f = float(extracted)
        expected_f  = float(expected_clean)
    except ValueError:
        return {
            "status":    FAIL,
            "extracted": extracted,
            "expected":  expected_clean,
            "message":   "ABV value is not a valid number.",
        }
 
    if abs(extracted_f - expected_f) < 0.01:   # floating-point tolerance
        return {
            "status":    PASS,
            "extracted": f"{extracted_f}%",
            "expected":  f"{expected_f}%",
            "message":   "ABV matches.",
        }
 
    return {
        "status":    FAIL,
        "extracted": f"{extracted_f}%",
        "expected":  f"{expected_f}%",
        "message":   f"ABV on label is {extracted_f}%, expected {expected_f}%.",
    }
 
 
# ── Government Warning ────────────────────────────────────────────────────────
 
def validate_government_warning(extracted: str | None) -> dict:
    """
    The government warning must match the canonical text EXACTLY
    (after whitespace normalization). No fuzzy auto-correction — a real
    spelling mistake on the label should be a real failure.
 
    We still report a fuzzy similarity score to help agents distinguish
    OCR noise from genuine label errors.
    """
    canonical = normalize_whitespace(GOVERNMENT_WARNING)
 
    if not extracted:
        return {
            "status":    FAIL,
            "extracted": None,
            "expected":  canonical,
            "message":   f'"{GOVERNMENT_WARNING_HEADER}" block not found on label.',
        }
 
    extracted_norm = normalize_whitespace(extracted)
 
    if extracted_norm == canonical:
        return {
            "status":    PASS,
            "extracted": extracted_norm,
            "expected":  canonical,
            "message":   "Government warning is correct.",
        }
 
    # Exact match failed — provide diagnostic detail
    similarity = fuzz.ratio(extracted_norm, canonical)
 
    header_hint = (
        ' The "GOVERNMENT WARNING:" header must be in ALL CAPS with a colon.'
        if not extracted_norm.startswith("GOVERNMENT WARNING:")
        else ""
    )
 
    return {
        "status":    FAIL,
        "extracted": extracted_norm,
        "expected":  canonical,
        "message": (
            f"Government warning does not match required text "
            f"(similarity: {similarity}%).{header_hint}"
        ),
    }
 
 
# ── Secondary Fields ──────────────────────────────────────────────────────────
 
def validate_secondary_fields(extracted_secondary: dict) -> dict:
    """
    For each secondary field, determine if it was found or missing.
    REVIEW if missing; PASS if present (no exact-match for secondary fields).
    """
    results = {}
    for field in SECONDARY_FIELDS:
        value = extracted_secondary.get(field)
        if value:
            results[field] = {
                "status":    PASS,
                "extracted": value,
                "message":   f"{FIELD_LABELS[field]} found.",
            }
        else:
            results[field] = {
                "status":    REVIEW,
                "extracted": None,
                "message":   f"{FIELD_LABELS[field]} not found on label.",
            }
    return results
 
 
# ── Master Validation ─────────────────────────────────────────────────────────
 
def validate_label(ocr_data: dict, user_brand: str, user_abv: str) -> dict:
    """
    Run all validations and return a single result dict.
 
    ocr_data keys must use underscores (brand_name, abv, government_warning, secondary)
    — matching what process_image() returns.
    """
    brand_result      = validate_brand_name(ocr_data.get("brand_name"), user_brand)
    abv_result        = validate_abv(ocr_data.get("abv"), user_abv)
    warning_result    = validate_government_warning(ocr_data.get("government_warning"))
    secondary_results = validate_secondary_fields(ocr_data.get("secondary", {}))
 
    big3_statuses = [
        brand_result["status"],
        abv_result["status"],
        warning_result["status"],
    ]
 
    if FAIL in big3_statuses:
        overall = FAIL
    else:
        missing = [
            FIELD_LABELS[k]
            for k, v in secondary_results.items()
            if v["status"] == REVIEW
        ]
        overall = REVIEW if missing else PASS
 
    missing_secondary = [
        FIELD_LABELS[k]
        for k, v in secondary_results.items()
        if v["status"] == REVIEW
    ]
 
    return {
        "overall":            overall,
        "brand_name":         brand_result,
        "abv":                abv_result,
        "government_warning": warning_result,
        "secondary":          secondary_results,
        "missing_secondary":  missing_secondary,
    }