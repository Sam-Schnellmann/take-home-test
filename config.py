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

# GOVERNEMENT_WARNING header
#  must be ALL CAPS
GOVERNMENT_WARNING_HEADER = "GOVERNMENT WARNING:"

# the big 3
#  these must pass for an overall PASS. Any failure -> FAIL
BIG_3 = ["brand name", "abv", "government warning"]

# Secondary fields
#  missing fields -> review (if Big 3 all pass)
#  present but unreadable or wrong -> review
SECONDARY_FIELDS = [
    "bottler_name_address",
    "varietal_designation",
    "appellation_of_origin",
    "vintage_date",
    "net_volume",
    "sulfite_declaration",
]

# Readable labels for display and export
FIELD_LABELS = {
    "brand name":            "Brand Name",
    "abv":                   "ABV (%)",
    "government warning":    "Government Warning",
    "bottler_name_address":  "Bottler Name and Address",
    "varietal_designation":  "Varietal Designation",
    "appellation_of_origin": "Appellation of Origin",
    "vintage_date":          "Vintage Date",
    "net_volume":            "Net Volume",
    "sulfite_declaration":   "Sulfite Declaration"
}

# Accepted image formats
ACCEPTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}

# Tesseract path (Windows)
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# OLLAMA_MODEL
OLLAMA_MODEL = "llama3"

# Export filenames
EXPORT_JSON_NAME  = "ttb_results.json"
EXPORT_CSV_NAME   = "ttb_results.csv"
EXPORT_EXCEL_NAME = "ttb_results.xlsx"
EXPORT_ZIP_NAME   = "ttb_results.zip"

# XLSX color fills
XLSX_COLOR_FAIL   = "FFFF4C4C"  # Red
XLSX_COLOR_REVIEW = "FFFD700"  # Yellow
XLSX_COLOR_PASS   = None  # no fill