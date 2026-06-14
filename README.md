# TTB Label Compliance Checker

[https://take-home-test.streamlit.app/](https://take-home-test.streamlit.app/)

A prototype web application built for the U.S. Department of the Treasury take home assessment. It uses an AI powered OCR to automatically check alcohol beverage labels for TTB (Alcohol and Tobacco Tax and Trade Bureau) compliance, with a human-in-the-loop review workflow for ambiguous results.

---

## Setup & Installation

### Prerequisites

- Python 3.14.6+
- An Anthropic API key

### Install dependencies

```powershell
pip install -r requirements.txt
```

### Configure your API key

Create a folder named `.streamlit`, open the folder and create a toml file named `secrets.toml` in the project root:
`.streamlit/secrets.toml`


Inside that `secrets.toml` file is where you store an Anthropic API key:
```toml
ANTHROPIC_API_KEY = "your-api-key-here"
```

### Run the app
from the terminal, type the following to start this app:

```powershell
python -m streamlit run app.py
```

This command should open localhost automatically; however, if it does not: navigate to your browser and open this link [http://localhost:8501](http://localhost:8501)

---

## Project Structure

```
├── app.py                  # Main Streamlit UI
├── config.py               # Constants, thresholds, field labels
├── core/
│   ├── ocr.py              # Image -> structured text via Claude Haiku
│   ├── validator.py        # Field-level compliance rules
│   ├── analyzer.py         # AI explanation generator
│   └── exporter.py         # ZIP export (JSON, CSV, XLSX)
└── .streamlit/
    └── secrets.toml        # API key (Not committed. You will have to add this yourself)
```

---

## How to Use

1. Upload one or more label photos (JPG, PNG, WEBP, or ZIP of images)
2. Enter the expected **Brand Name** and **ABV** for the label batch
3. Click **Submit**
    - the app sends each image to Claude for OCR, then runs compliance validation
4. Review results below. REVIEW results include a **Review & Check** button to open a full-image popup where you can manually approve or reject
5. Click **Download ZIP** to export results as JSON, CSV, and Excel

To start a new session, refresh the page.

---

## Approach & Tools

### OCR Claude Haiku (`claude-haiku-4-5-20251001`)

Each label image is resized (max 1600px on the longest side) and encoded as JPEG before being sent to the Anthropic API. Claude Haiku extracts four fields from the image in a single pass:

- `raw_text` -> everything visible on the label
- `brand_name` -> the product/brand name, preserving exact capitalization
- `abv` -> numeric ABV value only (e.g. `4.2`)
- `government_warning` -> the full warning block including header

JPEG encoding (quality 92) is used instead of PNG to keep payload sizes under API limits for large label photos.

### Validation `validator.py`

Each field is validated independently, then an overall status is computed.

**Brand Name**
- Exact match (case-sensitive) → PASS
- Different text → FAIL
- Same letters, different capitalization, name not found → REVIEW (human can verify from the image)

**ABV**
- Numeric match within ±0.01% → PASS
- Different number → FAIL
- Not found by OCR → REVIEW

**Government Warning (three-layer check)**

| Layer | What it checks |
|---|---|
| Header | `"GOVERNMENT WARNING:"` must be exactly ALL CAPS, bolded, and have a colon |
| Periods | `"defects."` and `"problems."` must be present -> OCR often misses small periods |
| Fuzzy match | Punctuation-stripped, uppercased similarity via `rapidfuzz` -> PASS ≥ 99%, REVIEW 60–99%, FAIL < 60% |

Punctuation is stripped before fuzzy comparison so missing periods don't artificially lower the similarity score — they are caught by the dedicated period check instead.

**Overall status**

| Condition | Overall |
|---|---|
| Any field is FAIL | FAIL |
| Any field is REVIEW (AND none are marked FAIL) | REVIEW |
| ALL fields PASS | PASS |

### Human-in-the-Loop Review

REVIEW results display a **Review & Check** button. Clicking it opens a dialog showing:

- PASS / FAIL decision buttons
- Which specific fields need review
- The full label image for visual inspection

Marking PASS flips all REVIEW fields to PASS. Marking FAIL flips only the REVIEW fields to FAIL (already-passing fields are left unchanged). Decisions are final within the session.

### AI Explanation (Claude Haiku)

For any non-PASS result, a second Claude Haiku call generates a 2–4 sentence plain-language explanation of what failed and what needs to be corrected. This is shown in the **AI Analysis** section beneath the field rows.

For REVIEW results on the government warning, a third call pinpoints specific text differences (e.g. a misspelled word, missing period, or wrong numbering format).

### Export

Results can be downloaded as a ZIP containing:

- `ttb_results.json`: full structured data including all field details
- `ttb_results.csv`: flat tabular format
- `ttb_results.xlsx`: color-coded Excel file (red = FAIL, yellow = REVIEW, no fill = PASS)

---

## Assumptions Made

- **Only the 3 fields are validated.** The TTB requires additional fields (bottler address, net volume, sulfite declaration, etc.) but based on the assessment scope, only Brand Name, ABV, and Government Warning are checked. Secondary fields are stubbed out in `config.py` and can be re-enabled.
- **The government warning text is fixed.** The canonical warning text is hardcoded in `config.py`. Both variations (wine/beer vs. wiskey) use the same text per TTB requirements.
- **ABV tolerance is ±0.01%.** Labels may print `4.2%` when the expected value is `4.20%` -> these are treated as equivalent.
- **One label per image.** The app does not attempt to separate front and back panels -> Claude Haiku reads both panels from the same image.
- **HEIC support is optional.** `pillow-heif` enables iPhone photo uploads. If not installed, HEIC files are silently skipped.
- **Session is not persisted.** Refreshing the page clears all results. There is no database or authentication layer.
