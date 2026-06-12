import io
import zipfile
from datetime import datetime
from pathlib import Path
 
import streamlit as st
from PIL import Image
 
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_SUPPORTED = True
except ImportError:
    HEIC_SUPPORTED = False

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
/* Global */
html, body, [class*="css"] { font-family: 'Segoe UI', sans-serif; }
 
/* Status badges */
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
 
/* Field result rows */
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
 
/* Section headers */
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
            
/* Thumbnail strip */
.thumb-strip {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 480px;
    overflow-y: auto;
    padding-right: 4px;
}
.thumb-active {
    outline: 3px solid #1a7a4a;
    border-radius: 6px;
}
</style>
""", unsafe_allow_html=True)


if "results" not in st.session_state:
    st.session_state.results = []
if "staged_images" not in st.session_state:
    st.session_state.staged_images = []
if "active_idx" not in st.session_state:
    st.session_state.active_idx = 0

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
 

def open_pil(file_bytes: bytes, filename: str) -> Image.Image | None:
    """Safely open any supported image format, including HEIC."""
    try:
        return Image.open(io.BytesIO(file_bytes)).convert("RGB")
    except Exception:
        return None
 
 
def load_images_from_upload(uploaded_files) -> list[dict]:
    """
    Accept a list of uploaded file objects (single or multi-select).
    Returns list of {"name": str, "pil": Image}.
    Skips unsupported files and warns the user.
    """
    images   = []
    skipped  = []
    accepted = ACCEPTED_IMAGE_EXTENSIONS | {".webp", ".heic", ".heif"}
 
    for f in uploaded_files:
        suffix = Path(f.name).suffix.lower()
        if suffix not in accepted:
            skipped.append(f.name)
            continue
        pil = open_pil(f.read(), f.name)
        if pil:
            images.append({"name": f.name, "pil": pil})
        else:
            skipped.append(f.name)
 
    if skipped:
        st.warning(f"Skipped {len(skipped)} unsupported file(s): " + ", ".join(skipped))
 
    return images
 
 
def load_images_from_zip(zip_file) -> list[dict]:
    """Extract all supported images from an uploaded ZIP file."""
    accepted = ACCEPTED_IMAGE_EXTENSIONS | {".webp", ".heic", ".heif"}
    images   = []
    skipped  = []
 
    zip_bytes = zip_file.read()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for member in zf.namelist():
            suffix = Path(member).suffix.lower()
            if member.endswith("/"):
                continue
            if suffix not in accepted:
                skipped.append(member)
                continue
            pil = open_pil(zf.read(member), member)
            if pil:
                images.append({"name": Path(member).name, "pil": pil})
            else:
                skipped.append(member)
 
    if skipped:
        st.warning(f"Skipped {len(skipped)} unsupported file(s): " + ", ".join(skipped))
 
    return images

 
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
 
    # Overall badge
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"### {result['filename']}")
    with col2:
        st.markdown(badge_html(overall), unsafe_allow_html=True)
 
    # Big 3
    st.markdown('<div class="section-header">Required Fields</div>', unsafe_allow_html=True)
    for field in ["brand_name", "abv", "government_warning"]:
        r = result.get(field, {})
        render_field_row(
            FIELD_LABELS[field],
            r.get("status", FAIL),
            r.get("message", ""),
            r.get("extracted", "") or "",
        )
 
    # Secondary
    st.markdown('<div class="section-header">Secondary Fields</div>', unsafe_allow_html=True)
    for field, r in result.get("secondary", {}).items():
        render_field_row(
            FIELD_LABELS[field],
            r.get("status", REVIEW),
            r.get("message", ""),
            r.get("extracted", "") or "",
        )
 
    # Explanation
    if result.get("explanation"):
        st.markdown('<div class="section-header">AI Analysis</div>', unsafe_allow_html=True)
        st.info(result["explanation"])
 

# layout 
st.title("🍷 TTB Label Compliance Checker")
st.caption("Upload a label image and enter the expected values to verify compliance.")
st.divider()
 

# Upload section
upload_tab, camera_tab = st.tabs(["📁 Upload Images", "📷 Use Camera"])
 
with upload_tab:
    accepted_types = ["jpg", "jpeg", "png", "webp", "zip"]
    if HEIC_SUPPORTED:
        accepted_types += ["heic", "heif"]
 
    uploaded_files = st.file_uploader(
        "Drop images or a ZIP here — select multiple with Ctrl/Cmd+Click",
        type=accepted_types,
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
 
    if uploaded_files:
        # Separate ZIPs from image uploads
        zip_files   = [f for f in uploaded_files if f.name.lower().endswith(".zip")]
        image_files = [f for f in uploaded_files if not f.name.lower().endswith(".zip")]
 
        new_staged = []
        for zf in zip_files:
            new_staged.extend(load_images_from_zip(zf))
        if image_files:
            new_staged.extend(load_images_from_upload(image_files))
 
        if new_staged:
            st.session_state.staged_images = new_staged
            st.session_state.active_idx    = 0
 
with camera_tab:
    st.caption("Point your camera at the label and capture it directly.")
    camera_image = st.camera_input("Capture label")
 
    if camera_image:
        pil = open_pil(camera_image.read(), "camera_capture.jpg")
        if pil:
            # Replace staged images with just the camera shot
            st.session_state.staged_images = [{"name": "camera_capture.jpg", "pil": pil}]
            st.session_state.active_idx    = 0
            st.success("Camera image ready — fill in the expected values and run the check.")
 
 
# Preview: thumbnail strip + large preview
staged = st.session_state.staged_images
 
if staged:
    st.divider()
    prev_left, prev_right = st.columns([1, 3], gap="large")
 
    with prev_left:
        st.markdown("**Queue**")
        for i, item in enumerate(staged):
            is_active = (i == st.session_state.active_idx)
            border_color = "#1a7a4a" if is_active else "#dddddd"
            st.markdown(
                f'<div style="border: 3px solid {border_color}; border-radius: 6px; '
                f'overflow: hidden; margin-bottom: 8px;">',
                unsafe_allow_html=True,
            )
            st.image(item["pil"], caption=item["name"], use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
 
            if not is_active:
                if st.button(f"Preview", key=f"thumb_{i}"):
                    st.session_state.active_idx = i
                    st.rerun()
 
    with prev_right:
        active = staged[st.session_state.active_idx]
        st.markdown(f"**Previewing:** {active['name']}")
        st.image(active["pil"], use_container_width=True)
 

    # Expected values
    st.divider()
    val_left, val_right = st.columns([1, 1], gap="large")
 
    with val_left:
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
            "These values apply to all images in the queue. "
            "The government warning is checked against the official TTB text automatically."
        )
 
    with val_right:
        st.subheader(f"Queue Summary")
        st.metric("Images ready to check", len(staged))
        if not HEIC_SUPPORTED:
            st.info("💡 Install `pillow-heif` to enable HEIC/iPhone photo support.")
 
    st.divider()
 
    # Run and clear button
    run_col, clear_col, _ = st.columns([1, 1, 2])
    with run_col:
        go = st.button("▶ Run Check", type="primary", use_container_width=True)
    with clear_col:
        if st.button("🗑 Clear Queue", use_container_width=True):
            st.session_state.staged_images = []
            st.session_state.active_idx    = 0
            st.rerun()
 
    # Processing
    if go:
        if not brand_input.strip():
            st.error("Please enter the expected Brand Name.")
        elif not abv_input.strip():
            st.error("Please enter the expected ABV.")
        else:
            new_results = []
            progress    = st.progress(0, text="Starting…")
 
            for i, item in enumerate(staged):
                progress.progress(
                    i / len(staged),
                    text=f"Processing {i+1}/{len(staged)}: {item['name']}",
                )
                result = run_single(
                    item["pil"],
                    item["name"],
                    brand_input.strip(),
                    abv_input.strip(),
                )
                new_results.append(result)
 
            progress.progress(1.0, text="Done!")
            progress.empty()
 
            st.session_state.results.extend(new_results)
 
            st.divider()
            st.subheader("Results")
            for result in new_results:
                with st.container(border=True):
                    render_result(result)
 
else:
    # No images staged yet
    st.divider()
    st.info("👆 Upload images or use the camera tab above to get started.")
 
 
# Session history summary
if st.session_state.results:
    st.divider()
 
    total   = len(st.session_state.results)
    passes  = sum(1 for r in st.session_state.results if r["overall"] == PASS)
    fails   = sum(1 for r in st.session_state.results if r["overall"] == FAIL)
    reviews = sum(1 for r in st.session_state.results if r["overall"] == REVIEW)
 
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Checked", total)
    m2.metric("✅ Pass",       passes)
    m3.metric("⚠️ Review",    reviews)
    m4.metric("❌ Fail",       fails)
 
    export_col, clear_col, _ = st.columns([1, 1, 2])
 
    with export_col:
        zip_bytes = build_export_zip(st.session_state.results)
        st.download_button(
            label="⬇ Export Results (ZIP)",
            data=zip_bytes,
            file_name=EXPORT_ZIP_NAME,
            mime="application/zip",
            use_container_width=True,
        )
 
    with clear_col:
        if st.button("🗑 Clear Session", use_container_width=True):
            st.session_state.results       = []
            st.session_state.staged_images = []
            st.session_state.active_idx    = 0
            st.rerun()