# Statuses for the app
PASS = "PASS"
REVIEW = "REVIEW"
FAIL = "FAIL"
 
# Government Warning
#  Label must match exactly, including spaces and punctuation.
GOVERNMENT_WARNING = (
    "GOVERNMENT WARNING: "
    "(1) According to the Surgeon General, women should not drink alcoholic beverages "
    "during pregnancy because of the risk of birth defects. "
    "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
    "operate machinery, and may cause health problems."
)
 
# GOVERNMENT_WARNING header must be ALL CAPS
GOVERNMENT_WARNING_HEADER = "GOVERNMENT WARNING:"
 
# The Big 3 — these must pass for an overall PASS. Any failure -> FAIL
BIG_3 = ["brand_name", "abv", "government_warning"]
 
# Secondary fields
#  missing fields -> REVIEW (if Big 3 all pass)
#  present but unreadable or wrong -> REVIEW
SECONDARY_FIELDS = [
    "bottler_name_address",
    "varietal_designation",
    "appellation_of_origin",
    "vintage_date",
    "net_volume",
    "sulfite_declaration",
]
 
# Readable labels for display and export
# Keys must use underscores — used everywhere in the codebase
FIELD_LABELS = {
    "brand_name":            "Brand Name",
    "abv":                   "ABV (%)",
    "government_warning":    "Government Warning",
    "bottler_name_address":  "Bottler Name and Address",
    "varietal_designation":  "Varietal Designation",
    "appellation_of_origin": "Appellation of Origin",
    "vintage_date":          "Vintage Date",
    "net_volume":            "Net Volume",
    "sulfite_declaration":   "Sulfite Declaration",
}
 
# Accepted image formats
ACCEPTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
 
# Anthropic model — used for both OCR and AI explanations
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
 
# Export filenames
EXPORT_JSON_NAME = "ttb_results.json"
EXPORT_CSV_NAME  = "ttb_results.csv"
EXPORT_XLSX_NAME = "ttb_results.xlsx"
EXPORT_ZIP_NAME  = "ttb_results.zip"
 
# XLSX row color fills (ARGB format — must be 8 hex digits)
XLSX_COLOR_FAIL   = "FFFF4C4C"  # Red
XLSX_COLOR_REVIEW = "FFFFD700"  # Yellow  ← was "FFFD700" (7 digits, invalid)
XLSX_COLOR_PASS   = None        # No fill