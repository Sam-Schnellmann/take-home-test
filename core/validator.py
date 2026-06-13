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

    if extracted_norm.upper() == expected_norm.upper():
        return {
            "status": REVIEW,
            "extracted": extracted_norm,
            "expected": expected_norm,
            "message": (
                f'Capitalization mismatch: label reads "{extracted_norm}", '
                f'expected "{expected_norm}". '
                "Verify the exact casing on the physical label."
            ),
        }

    #     hint = "Capitalization mismatch: check case on every word."
    # else:
    #     hint = f'Label reads "{extracted_norm}", expected "{expected_norm}".'

    return {
        "status":    FAIL,
        "extracted": extracted_norm,
        "expected":  expected_norm,
        # "message":   hint,
        "message": f'Label reads "{extracted_norm}", expected "{expected_norm}".',
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

    if abs(extracted_f - expected_f) < 0.01:
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
    Validation rules:
      - "GOVERNMENT WARNING:" header must be exactly ALL CAPS with a colon.
      - Body text is compared case-insensitively.
      - PASS   = similarity >= 99.99%
      - REVIEW = 60.00% <= similarity < 99.99%
      - FAIL   = similarity < 60.00%
    """

    canonical = normalize_whitespace(GOVERNMENT_WARNING)
    canonical_up = canonical.upper()

    if not extracted:
        return {
            "status": FAIL,
            "extracted": None,
            "expected": canonical,
            "message": f'"{GOVERNMENT_WARNING_HEADER}" block not found on label.',
        }

    extracted_norm = normalize_whitespace(extracted)
    extracted_up = extracted_norm.upper()

    # Header must be EXACTLY "GOVERNMENT WARNING:"
    header_valid = extracted_norm.startswith("GOVERNMENT WARNING:")

    if not header_valid:
        header_hint = (
            ' The "GOVERNMENT WARNING:" header must be in ALL CAPS '
            "and include the colon."
        )
    else:
        header_hint = ""

    similarity = fuzz.ratio(extracted_up, canonical_up)

    # Body matches perfectly, but header casing is wrong
    if similarity >= 99.99 and not header_valid:
        return {
            "status": FAIL,
            "extracted": extracted_norm,
            "expected": canonical,
            "message": (
                "Government warning text matches, but the header "
                f'format is incorrect.{header_hint}'
            ),
        }

    # PASS
    if similarity >= 99.99:
        return {
            "status": PASS,
            "extracted": extracted_norm,
            "expected": canonical,
            "message": "Government warning is correct.",
        }

    # REVIEW
    if similarity >= 60:
        return {
            "status": REVIEW,
            "extracted": extracted_norm,
            "expected": canonical,
            "message": (
                "Government warning could not be fully verified. "
                "Image may be blurry, dark, low resolution, or partially obscured. "
                f"(similarity: {similarity:.2f}%). "
                f"Please manually review the physical label.{header_hint}"
            ),
        }

    # FAIL
    return {
        "status": FAIL,
        "extracted": extracted_norm,
        "expected": canonical,
        "message": (
            "Government warning does not match required text "
            f"(similarity: {similarity:.2f}%). "
            f"Check wording, spelling, capitalization, numbering, and punctuation."
            f"{header_hint}"
        ),
    }


# ── Secondary Fields ──────────────────────────────────────────────────────────

def validate_secondary_fields(extracted_secondary: dict) -> dict:
    """
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
    brand_result      = validate_brand_name(ocr_data.get("brand_name"), user_brand)
    abv_result        = validate_abv(ocr_data.get("abv"), user_abv)
    warning_result    = validate_government_warning(ocr_data.get("government_warning"))
    secondary_results = validate_secondary_fields(ocr_data.get("secondary", {}))

    # FAIL takes precedence
    if (
        brand_result["status"] == FAIL
        or abv_result["status"] == FAIL
        or warning_result["status"] == FAIL
    ):
        overall = FAIL

    # REVIEW is next
    elif (
        brand_result["status"] == REVIEW
        or abv_result["status"] == REVIEW
        or warning_result["status"] == REVIEW
        or any(
            result["status"] == REVIEW
            for result in secondary_results.values()
        )
    ):
        overall = REVIEW

    # Everything else must be PASS
    else:
        overall = PASS

    missing_secondary = [
        FIELD_LABELS[k]
        for k, v in secondary_results.items()
        if v["status"] == REVIEW
    ]

    return {
        "overall": overall,
        "brand_name": brand_result,
        "abv": abv_result,
        "government_warning": warning_result,
        "secondary": secondary_results,
        "missing_secondary": missing_secondary,
    }