import re
from rapidfuzz import fuzz

from config import (
    PASS, REVIEW, FAIL,
    GOVERNMENT_WARNING, GOVERNMENT_WARNING_HEADER,
    BIG_3, SECONDARY_FIELDS, FIELD_LABELS,
)

def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())

# big 3
# brand name
def validate_brand_name(extracted: str | None, expected: str) -> dict:
    """
    Exact, case-sensitive match.
    extracted: what OSR pulled off the label
    expected: what the user entered as the correct value
    """

    if not extracted:
        return {
            "status": FAIL,
            "extracted": None,
            "expected": expected,
            "message": "Brand name could not be read from the label."
        }
    
    extracted_norm = normalize_whitespace(extracted)
    expected_norm = normalize_whitespace(expected)

    if extracted_norm == expected_norm:
        return {
            "status": PASS,
            "extracted": extracted_norm,
            "expected": expected_norm,
            "message": "Brand name matches expected value."
        }
    
    # give the agent a useful diff hint
    if extracted_norm.upper() == expected_norm.upper():
        hint = "Capitalization mismatch: check case on every word."
    else:
        hint = f'Label reads "{extracted_norm}", expected "{expected_norm}".'

    return {
        "status": FAIL,
        "extracted": extracted_norm,
        "expected": expected_norm,
        "message": hint
    }

# ABV
def validate_abv(extracted: str | None, expected: str) -> dict:
    """
    Numeric comparison of ABV percentages.
    extracted : numeric string from OCR (e.g. "13.5")
    expected  : what the user typed (e.g. "13.5" or "13.5%")
    """
    # Strip % and whitespace from user input
    expected_clean = re.sub(r"[%\s]", "", expected).strip()
 
    if not extracted:
        return {
            "status": FAIL,
            "extracted": None,
            "expected": expected_clean,
            "message": "ABV percentage could not be read from the label.",
        }
 
    try:
        extracted_f = float(extracted)
        expected_f  = float(expected_clean)
    except ValueError:
        return {
            "status": FAIL,
            "extracted": extracted,
            "expected": expected_clean,
            "message": "ABV value is not a valid number.",
        }
 
    if abs(extracted_f - expected_f) < 0.01:   # floating-point tolerance
        return {
            "status": PASS,
            "extracted": f"{extracted_f}%",
            "expected":  f"{expected_f}%",
            "message": "ABV matches.",
        }
 
    return {
        "status": FAIL,
        "extracted": f"{extracted_f}%",
        "expected":  f"{expected_f}%",
        "message": f"ABV on label is {extracted_f}%, expected {expected_f}%.",
    }

# Government Warning
def validate_government_warning(extracted: str | None) -> dict:
    """
    The government warning must match the canonical text EXACTLY
    (after whitespace normalization). No fuzzy matching — a spelling mistake
    on the label is a real failure, not an OCR artifact we should paper over.
 
    To help agents diagnose OCR issues vs real label problems, we also report
    the fuzzy similarity score.
    """
    canonical = normalize_whitespace(GOVERNMENT_WARNING)
 
    if not extracted:
        return {
            "status": FAIL,
            "extracted": None,
            "expected": canonical,
            "message": f'"{GOVERNMENT_WARNING_HEADER}" block not found on label.',
        }
 
    extracted_norm = normalize_whitespace(extracted)
 
    if extracted_norm == canonical:
        return {
            "status": PASS,
            "extracted": extracted_norm,
            "expected": canonical,
            "message": "Government warning is correct.",
        }
 
    # Exact match failed — provide diagnostic detail
    similarity = fuzz.ratio(extracted_norm, canonical)
 
    # Check for all-caps header specifically (common failure mode)
    if not extracted_norm.startswith("GOVERNMENT WARNING:"):
        header_hint = (
            ' The "GOVERNMENT WARNING:" header must be in ALL CAPS with a colon.'
        )
    else:
        header_hint = ""
 
    return {
        "status": FAIL,
        "extracted": extracted_norm,
        "expected": canonical,
        "message": (
            f"Government warning does not match required text "
            f"(similarity: {similarity}%).{header_hint}"
        ),
    }

# secondary fields
def validate_secondary_fields(extracted_secondary: dict) -> dict:
    """
    For each secondary field, determine if it was found or missing.
    Returns a dict of field_key → {status, extracted, message}
    REVIEW if missing; PASS if present (we don't exact-match secondary fields).
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

# Master validation
def validate_label(ocr_data: dict, user_brand: str, user_abv: str) -> dict:
    """
    Run all validations and return a single result dict:
    {
        overall:            PASS / REVIEW / FAIL,
        brand_name:         {status, extracted, expected, message},
        abv:                {status, extracted, expected, message},
        government_warning: {status, extracted, expected, message},
        secondary_fields:   {field_key: {status, extracted, message}},
        missing_secondary:  [list of human readable field names]
    }
    """
    brand_result      = validate_brand_name(ocr_data.get("brand name"), user_brand)
    abv_result        = validate_abv(ocr_data.get("abv"), user_abv)
    warning_result    = validate_government_warning(ocr_data.get("government warning"))
    secondary_results = validate_secondary_fields(ocr_data.get("secondary", {}))

    # Determine the overall status
    big3_statuses = [brand_result["status"], abv_result["status"], warning_result["status"]]

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
        "secondary_fields":   secondary_results,
        "missing_secondary":  missing_secondary,
    }