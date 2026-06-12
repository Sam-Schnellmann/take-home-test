import io
import zipfile
from datetime import datetime
from pathlib import Path
 
import streamlit as st
from PIL import Image
 
from config import (
    PASS, REVIEW, FAIL,
    ACCEPTED_IMAGE_EXTENSIONS,
    FIELD_LABELS,
    EXPORT_ZIP_NAME,
)
from core.ocr import process_image
from core.validator import validate_label
from core.analyzer import get_explanation
from core.exporter import build_export_zip
 
 
# set up the page
st.set_page_config(
    page_title="TTB Label Compliance Checker",
    page_icon="🍷",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# CSS styles
st.markdown("""
<style>
/* ── Global ── */
html, body, [class*="css"] { font-family: 'Segoe UI', sans-serif; }
 
/* ── Status badges ── */
.badge {
    display: inline-block;
    padding: 0.35em 1.1em;
    border-radius: 6px;
    font-size: 1.05rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
.badge-pass   { background: #1a7a4a; color: #ffffff; }
.badge-review { background: #b58a00; color: #ffffff; }
.badge-fail   { background: #c0392b; color: #ffffff; }
 
/* ── Field result rows ── */
.field-row {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.5rem 0;
    border-bottom: 1px solid #e0e0e0;
}
.field-dot {
    width: 14px; height: 14px;
    border-radius: 50%;
    flex-shrink: 0;
    margin-top: 4px;
}
.dot-pass   { background: #1a7a4a; }
.dot-review { background: #e6a817; }
.dot-fail   { background: #c0392b; }
.field-label { font-weight: 600; min-width: 200px; }
.field-msg   { color: #444; font-size: 0.95rem; }
 
/* ── Section headers ── */
.section-header {
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #888;
    margin: 1.5rem 0 0.5rem 0;
    border-bottom: 1px solid #ddd;
    padding-bottom: 4px;
}
</style>
""", unsafe_allow_html=True)


if "results" not in st.session_state:
    st.session_state.results = []   # accumulated across multiple runs

# helpers
def badge_html(status: str) -> str:
    css = {"PASS": "pass", "REVIEW": "review", "FAIL": "fail"}.get(status, "fail")
    return f'<span class="badge badge-{css}">{status}</span>'
 
 
def dot_html(status: str) -> str:
    css = {"PASS": "pass", "REVIEW": "review", "FAIL": "fail"}.get(status, "fail")
    return f'<div class="field-dot dot-{css}"></div>'
 
 
def render_field_row(label: str, status: str, message: str, extracted: str = ""):
    detail = f"{message}"
    if extracted:
        detail += f" <span style='color:#777;font-size:0.88rem;'>(read: \"{extracted}\")</span>"
    st.markdown(
        f'<div class="field-row">'
        f'  {dot_html(status)}'
        f'  <span class="field-label">{label}</span>'
        f'  <span class="field-msg">{detail}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
 
 
def run_single(pil_image: Image.Image, filename: str, brand: str, abv: str) -> dict:
    """Full pipeline for one image. Returns result dict."""
    with st.spinner("Reading label…"):
        ocr_data = process_image(pil_image)
 
    with st.spinner("Validating fields…"):
        validation = validate_label(ocr_data, brand, abv)
 
    explanation = ""
    if validation["overall"] != PASS:
        with st.spinner("Generating explanation…"):
            explanation = get_explanation(validation, filename)
 
    return {
        "filename":    filename,
        "timestamp":   datetime.now().isoformat(timespec="seconds"),
        "overall":     validation["overall"],
        "explanation": explanation,
        **{k: v for k, v in validation.items() if k not in ("overall",)},
    }
 
 
def render_result(result: dict):
    overall = result["overall"]
 
    # ── Overall badge ──
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"### {result['filename']}")
    with col2:
        st.markdown(badge_html(overall), unsafe_allow_html=True)
 
    # ── Big 3 ──
    st.markdown('<div class="section-header">Required Fields</div>', unsafe_allow_html=True)
    for field in ["brand_name", "abv", "government_warning"]:
        r = result.get(field, {})
        render_field_row(
            FIELD_LABELS[field],
            r.get("status", FAIL),
            r.get("message", ""),
            r.get("extracted", "") or "",
        )
 
    # ── Secondary ──
    st.markdown('<div class="section-header">Secondary Fields</div>', unsafe_allow_html=True)
    for field, r in result.get("secondary", {}).items():
        render_field_row(
            FIELD_LABELS[field],
            r.get("status", REVIEW),
            r.get("message", ""),
            r.get("extracted", "") or "",
        )
 
    # ── Explanation ──
    if result.get("explanation"):
        st.markdown('<div class="section-header">AI Analysis</div>', unsafe_allow_html=True)
        st.info(result["explanation"])
 

# layout 
st.title("🍷 TTB Label Compliance Checker")
st.caption("Upload a label image and enter the expected values to verify compliance.")
 
st.divider()
 
# input blocks
left, right = st.columns([1, 1], gap="large")
 
with left:
    st.subheader("Upload Label")
    uploaded_file = st.file_uploader(
        "Drop an image or ZIP batch here",
        type=["jpg", "jpeg", "png", "zip"],
        label_visibility="collapsed",
    )
 
    if uploaded_file and uploaded_file.type.startswith("image"):
        st.image(uploaded_file, width='stretch')
 
with right:
    st.subheader("Expected Values")
    brand_input = st.text_input(
        "Brand Name",
        placeholder="Exactly as it should appear on the label",
    )
    abv_input = st.text_input(
        "ABV (%)",
        placeholder="e.g. 13.5",
    )
    st.caption(
        "These are the only values you need to enter. "
        "The government warning is checked against the official TTB text automatically."
    )
 
st.divider()
 
# run analysis button
run_col, _ = st.columns([1, 3])
with run_col:
    go = st.button("▶ Run Check", type="primary", width='stretch')
 
if go:
    if not uploaded_file:
        st.error("Please upload a label image or ZIP file first.")
    elif not brand_input.strip():
        st.error("Please enter the expected Brand Name.")
    elif not abv_input.strip():
        st.error("Please enter the expected ABV.")
    else:
        new_results = []
 
        # Zip batch
        if uploaded_file.name.lower().endswith(".zip"):
            zip_bytes = uploaded_file.read()
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                members = zf.namelist()
                image_members = [
                    m for m in members
                    if Path(m).suffix.lower() in ACCEPTED_IMAGE_EXTENSIONS
                ]
                skipped = [
                    m for m in members
                    if Path(m).suffix.lower() not in ACCEPTED_IMAGE_EXTENSIONS
                    and not m.endswith("/")   # ignore directory entries
                ]
 
                if skipped:
                    st.warning(
                        f"Skipped {len(skipped)} non-image file(s): "
                        + ", ".join(skipped)
                    )
 
                if not image_members:
                    st.error("No supported image files found in the ZIP.")
                else:
                    progress = st.progress(0, text="Processing batch…")
                    for i, member in enumerate(image_members):
                        img_data = zf.read(member)
                        pil_img = Image.open(io.BytesIO(img_data))
                        result = run_single(
                            pil_img,
                            Path(member).name,
                            brand_input.strip(),
                            abv_input.strip(),
                        )
                        new_results.append(result)
                        progress.progress(
                            (i + 1) / len(image_members),
                            text=f"Processed {i+1}/{len(image_members)}: {Path(member).name}",
                        )
                    progress.empty()
 
        # Only one image uploaded
        else:
            pil_img = Image.open(uploaded_file)
            result = run_single(
                pil_img,
                uploaded_file.name,
                brand_input.strip(),
                abv_input.strip(),
            )
            new_results.append(result)
 
        # history
        st.session_state.results.extend(new_results)
 
        # Show results
        st.divider()
        st.subheader("Results")
        for result in new_results:
            with st.container(border=True):
                render_result(result)
 
 
# Session history
if st.session_state.results:
    st.divider()
 
    total  = len(st.session_state.results)
    passes = sum(1 for r in st.session_state.results if r["overall"] == PASS)
    fails  = sum(1 for r in st.session_state.results if r["overall"] == FAIL)
    reviews= sum(1 for r in st.session_state.results if r["overall"] == REVIEW)
 
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Checked", total)
    m2.metric("✅ Pass",  passes)
    m3.metric("⚠️ Review", reviews)
    m4.metric("❌ Fail",  fails)
 
    # ── Export button ──
    export_col, clear_col, _ = st.columns([1, 1, 2])
 
    with export_col:
        zip_bytes = build_export_zip(st.session_state.results)
        st.download_button(
            label="⬇ Export Results (ZIP)",
            data=zip_bytes,
            file_name=EXPORT_ZIP_NAME,
            mime="application/zip",
            width='stretch',
        )
 
    with clear_col:
        if st.button("🗑 Clear Session", width='stretch'):
            st.session_state.results = []
            st.rerun()