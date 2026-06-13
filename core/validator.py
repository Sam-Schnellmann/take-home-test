import re
from rapidfuzz import fuzz

from config import (
    PASS, REVIEW, FAIL,
    GOVERNMENT_WARNING, GOVERNMENT_WARNING_HEADER,
)
from core.analyzer import get_government_warning_analysis


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def strip_punctuation(text: str) -> str:
    """Remove all punctuation so periods/commas don't affect fuzzy score."""
    return re.sub(r"[^\w\s]", "", text)


REQUIRED_PERIODS = ["defects.", "problems."]


def check_required_periods(text: str) -> list[str]:
    """
    Return a list of words that should have a trailing period but don't.
    Checks for 'defects.' and 'problems.' in the extracted text (case-insensitive).
    """
    missing = []
    text_lower = text.lower()
    for token in REQUIRED_PERIODS:
        word = token.rstrip(".")          # e.g. "defects"
        # The word exists but the period is missing
        has_with_period    = token in text_lower
        has_without_period = bool(re.search(rf"\b{word}\b", text_lower))
        if has_without_period and not has_with_period:
            missing.append(token)
    return missing


# ── Brand Name ────────────────────────────────────────────────────────────────

def validate_brand_name(extracted: str | None, expected: str) -> dict:
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
            "status":    REVIEW,
            "extracted": extracted_norm,
            "expected":  expected_norm,
            "message":   (
                f'Capitalization mismatch: label reads "{extracted_norm}", '
                f'expected "{expected_norm}". '
                "Verify the exact casing on the physical label."
            ),
        }

    return {
        "status":    FAIL,
        "extracted": extracted_norm,
        "expected":  expected_norm,
        "message":   f'Label reads "{extracted_norm}", expected "{expected_norm}".',
    }


# ── ABV ───────────────────────────────────────────────────────────────────────

def validate_abv(extracted: str | None, expected: str) -> dict:
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
    Three-layer validation:

    Layer 1 — Header:  "GOVERNMENT WARNING:" must be exactly ALL CAPS with colon.
    Layer 2 — Periods: "defects." and "problems." must be present.
                       OCR often misses these tiny periods — checked explicitly
                       rather than relying on fuzzy score.
    Layer 3 — Fuzzy:   Case-insensitive AND punctuation-stripped comparison,
                       so neither caps nor missing commas/periods affect the score.
                       PASS ≥ 99%, REVIEW 60–97%, FAIL < 60%.
    """
    canonical     = normalize_whitespace(GOVERNMENT_WARNING)
    canonical_up  = strip_punctuation(canonical.upper())

    if not extracted:
        return {
            "status":   FAIL,
            "extracted": None,
            "expected":  canonical,
            "message":  f'"{GOVERNMENT_WARNING_HEADER}" block not found on label.',
        }

    extracted_norm = normalize_whitespace(extracted)
    extracted_up   = strip_punctuation(extracted_norm.upper())

    # ── Layer 1: Header casing ────────────────────────────────────────────────
    header_valid = extracted_norm.startswith("GOVERNMENT WARNING:")
    header_hint  = (
        ' The "GOVERNMENT WARNING:" header must be in ALL CAPS and include the colon.'
        if not header_valid else ""
    )

    # ── Layer 2: Explicit period check ────────────────────────────────────────
    missing_periods = check_required_periods(extracted_norm)
    period_hint = ""
    if missing_periods:
        words = " and ".join(f'"{w}"' for w in missing_periods)
        period_hint = (
            f" The word(s) {words} must be followed by a period — "
            "these are easy to miss in small print. Please verify on the physical label."
        )

    # ── Layer 3: Fuzzy match (punctuation-stripped, uppercased) ───────────────
    similarity = fuzz.ratio(extracted_up, canonical_up)

    # Perfect text but wrong header caps
    if similarity >= 99 and not header_valid:
        return {
            "status":    FAIL,
            "extracted": extracted_norm,
            "expected":  canonical,
            "message":   f"Government warning text matches, but the header format is incorrect.{header_hint}",
        }

    # PASS — text matches and periods are present (or OCR found them)
    if similarity >= 99 and not missing_periods:
        return {
            "status":    PASS,
            "extracted": extracted_norm,
            "expected":  canonical,
            "message":   "Government warning is correct.",
        }

    # PASS text score but periods flagged — bump to REVIEW
    if similarity >= 99 and missing_periods:
        return {
            "status":    REVIEW,
            "extracted": extracted_norm,
            "expected":  canonical,
            "message":   (
                f"Government warning text matches (similarity: {similarity:.1f}%), "
                f"but period(s) could not be confirmed by OCR.{period_hint}"
                f"{header_hint}"
            ),
        }

    # REVIEW
    if similarity >= 60:
        specific_analysis = get_government_warning_analysis(extracted_norm, canonical)
        analysis_note = f"\n\n{specific_analysis}" if specific_analysis else ""
        return {
            "status":    REVIEW,
            "extracted": extracted_norm,
            "expected":  canonical,
            "message":   (
                f"Government warning could not be fully verified "
                f"(similarity: {similarity:.1f}%). "
                "Image may be blurry, dark, or partially obscured. "
                f"Please manually review the physical label.{period_hint}{header_hint}{analysis_note}"
            ),
        }

    # FAIL
    return {
        "status":    FAIL,
        "extracted": extracted_norm,
        "expected":  canonical,
        "message":   (
            f"Government warning does not match required text "
            f"(similarity: {similarity:.1f}%). "
            f"Check wording, spelling, capitalization, numbering, and punctuation."
            f"{period_hint}{header_hint}"
        ),
    }


# ── Master Validation ─────────────────────────────────────────────────────────

def validate_label(ocr_data: dict, user_brand: str, user_abv: str) -> dict:
    brand_result   = validate_brand_name(ocr_data.get("brand_name"), user_brand)
    abv_result     = validate_abv(ocr_data.get("abv"), user_abv)
    warning_result = validate_government_warning(ocr_data.get("government_warning"))

    if (
        brand_result["status"] == FAIL
        or abv_result["status"] == FAIL
        or warning_result["status"] == FAIL
    ):
        overall = FAIL
    elif (
        brand_result["status"] == REVIEW
        or warning_result["status"] == REVIEW
    ):
        overall = REVIEW
    else:
        overall = PASS

    return {
        "overall":            overall,
        "brand_name":         brand_result,
        "abv":                abv_result,
        "government_warning": warning_result,
    }