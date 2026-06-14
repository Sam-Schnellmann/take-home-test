import io
import zipfile
from datetime import datetime
from pathlib import Path

import streamlit as st
from PIL import Image, ImageOps

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


# Page config

st.set_page_config(
    page_title="TTB Label Compliance Checker",
    page_icon="🍷",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# CSS

st.markdown("""
<style>
html, body, [class*="css"] { font-family: 'Segoe UI', sans-serif; }
.badge { display: inline-block; padding: 0.3em 0.9em; border-radius: 5px; font-size: 0.95rem; font-weight: 700; letter-spacing: 0.07em; text-transform: uppercase; }
.badge-pass   { background: #1a7a4a; color: #fff; }
.badge-review { background: #b58a00; color: #fff; }
.badge-fail   { background: #c0392b; color: #fff; }
.field-row { display: flex; align-items: flex-start; gap: 0.65rem; padding: 0.4rem 0; border-bottom: 1px solid #e8e8e8; }
.field-dot { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; margin-top: 4px; }
.dot-pass   { background: #1a7a4a; }
.dot-review { background: #e6a817; }
.dot-fail   { background: #c0392b; }
.field-label { font-weight: 600; min-width: 180px; font-size: 0.9rem; }
.field-msg   { color: #444; font-size: 0.88rem; }
.section-header { font-size: 0.72rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: #999; margin: 1rem 0 0.4rem 0; border-bottom: 1px solid #e4e4e4; padding-bottom: 3px; }
.thumb-wrap { border-radius: 6px; overflow: hidden; margin-bottom: 6px; cursor: pointer; transition: box-shadow 0.15s; }
.preview-placeholder { background: #f2f2f2; border-radius: 8px; border: 2px dashed #ccc; display: flex; align-items: center; justify-content: center; height: 200px; color: #aaa; font-size: 1rem; font-weight: 500; letter-spacing: 0.03em; }
.result-filename { font-size: 1rem; font-weight: 700; margin: 0; }
.block-container { padding-top: 1.5rem !important; padding-bottom: 2rem !important; }
[data-testid="column"]:nth-child(2) img { max-height: 300px; object-fit: contain; width: auto; margin: 0 auto; }
</style>
""", unsafe_allow_html=True)


# Session state

if "results"        not in st.session_state: st.session_state.results        = []
if "staged_images"  not in st.session_state: st.session_state.staged_images  = []
if "active_idx"     not in st.session_state: st.session_state.active_idx     = 0
if "rotations"      not in st.session_state: st.session_state.rotations      = []
if "images"         not in st.session_state: st.session_state.images         = {}


# Helpers & Callbacks

def rotate_left(): st.session_state.rotations[st.session_state.active_idx] = (st.session_state.rotations[st.session_state.active_idx] - 90) % 360
def rotate_right(): st.session_state.rotations[st.session_state.active_idx] = (st.session_state.rotations[st.session_state.active_idx] + 90) % 360
def set_active(i): st.session_state.active_idx = i
def badge_html(status: str) -> str: return f'<span class="badge badge-{"pass" if status=="PASS" else "review" if status=="REVIEW" else "fail"}">{status}</span>'
def dot_html(status: str) -> str: return f'<div class="field-dot dot-{"pass" if status=="PASS" else "review" if status=="REVIEW" else "fail"}"></div>'

def render_field_row(label, status, message, extracted=""):
    detail = message + (f" <span style='color:#888;font-size:0.82rem;'>(read: \"{extracted}\")</span>" if extracted else "")
    st.markdown(f'<div class="field-row">{dot_html(status)} <span class="field-label">{label}</span> <span class="field-msg">{detail}</span></div>', unsafe_allow_html=True)

def open_pil(file_bytes, filename):
    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(file_bytes))).convert("RGB")
        return img
    except: return None

def load_images_from_upload(uploaded_files):
    images = []
    for f in uploaded_files:
        pil = open_pil(f.read(), f.name)
        if pil: images.append({"name": f.name, "pil": pil})
    return images

def get_rotated(idx):
    img = st.session_state.staged_images[idx]["pil"]
    rot = st.session_state.rotations[idx]
    return img.rotate(rot, expand=True) if rot != 0 else img

def run_single(pil_image, filename, brand, abv):
    ocr_data = process_image(pil_image)
    validation = validate_label(ocr_data, brand, abv)
    explanation = get_explanation(validation, filename) if validation["overall"] != PASS else ""
    return {"filename": filename, "timestamp": datetime.now().isoformat(), "overall": validation["overall"], "explanation": explanation, **{k: v for k, v in validation.items() if k != "overall"}}

def render_result(result, result_idx: int):
    col1, col2, col3 = st.columns([3, 1, 1])
    col1.markdown(f'<p class="result-filename">📄 {result["filename"]}</p>', unsafe_allow_html=True)
    col2.markdown(badge_html(result["overall"]), unsafe_allow_html=True)
    if result["overall"] == REVIEW:
        if col3.button("🔍 Review & Check", key=f"review_{result_idx}"):
            review_dialog(result_idx)
    st.markdown('<div class="section-header">Required Fields</div>', unsafe_allow_html=True)
    for field in ["brand_name", "abv", "government_warning"]:
        r = result.get(field, {})
        render_field_row(FIELD_LABELS[field], r.get("status", FAIL), r.get("message", ""), r.get("extracted", ""))
    if result.get("explanation"):
        st.markdown('<div class="section-header">AI Analysis</div>', unsafe_allow_html=True)
        st.info(result["explanation"])

# REVIEW & CHECK box
@st.dialog("Review & Check", width="large")
def review_dialog(result_idx: int):
    result = st.session_state.results[result_idx]
    filename = result["filename"]

    col_pass, col_fail = st.columns(2)
    pass_clicked = col_pass.button("✅ PASS", type="primary", width='stretch')
    fail_clicked = col_fail.button("❌ FAIL", type="secondary", width='stretch')

    review_fields = [
        FIELD_LABELS[field]
        for field in ["brand_name", "abv", "government_warning"]
        if result[field]["status"] == REVIEW
    ]
    for label in review_fields:
        st.markdown(f"Please review the **{label}**")

    if pass_clicked:
        for field in ["brand_name", "abv", "government_warning"]:
            if st.session_state.results[result_idx][field]["status"] == REVIEW:
                st.session_state.results[result_idx][field]["status"] = PASS
                st.session_state.results[result_idx][field]["message"] = "Manually approved."
        st.session_state.results[result_idx]["overall"] = PASS
        st.rerun()

    if fail_clicked:
        for field in ["brand_name", "abv", "government_warning"]:
            if st.session_state.results[result_idx][field]["status"] == REVIEW:
                st.session_state.results[result_idx][field]["status"] = FAIL
                st.session_state.results[result_idx][field]["message"] = "Manually rejected."
        st.session_state.results[result_idx]["overall"] = FAIL
        st.rerun()

    if filename in st.session_state.images:
        st.image(st.session_state.images[filename], width='stretch')
    else:
        st.warning("Image not available for preview.")


# UI Layout

st.markdown("##TTB Label Compliance Checker\n\n" \
"Upload photos below, enter the brand name and alcohol by volume you wish to compare, then scroll down for your results.\n\n\n" \
"Results can either be:\n\n" \
"1.) PASS - all three field requirements (Brand Name, ABV, and Government Warning) pass.\n\n" \
"2.) REVIEW - a field requirement (or more) was unclear to the checker. A manual check can be processed.\n\n" \
"3.) FAIL - a field requirement (or more) do not follow the rules that have been set.\n\n" \
'By selecting the "Download Zip" button, you download a zip file containing the analysis results in a JSON, CSV, and EXCEL format.\n\n\n' \
"To clear your session, please refresh the website.")
with st.container():
    files = st.file_uploader("Upload", type=["jpg", "jpeg", "png", "webp", "zip"], accept_multiple_files=True, label_visibility="collapsed")
    if files:
        new_staged = load_images_from_upload(files)
        if new_staged != st.session_state.staged_images:
            st.session_state.staged_images = new_staged
            st.session_state.rotations = [0] * len(new_staged)
            st.rerun()
    progress_placeholder = st.empty()

st.divider()
col_thumbs, col_preview, col_controls = st.columns([1, 3, 2], gap="medium")

with col_controls:
    brand_input = st.text_input("Brand Name", key="brand_field")
    abv_input = st.text_input("ABV", key="abv_field")
    go = st.button("▶ Submit", type="primary", width='stretch', disabled=not st.session_state.staged_images)

# Validation Run (Handles processing and rerun)
if go:
    if not brand_input.strip() or not abv_input.strip():
        st.error("Please enter both Brand Name and ABV.")
    else:
        results = []
        progress = progress_placeholder.progress(0, text="Checking labels...")
        for i, item in enumerate(st.session_state.staged_images):
            results.append(run_single(get_rotated(i), item["name"], brand_input.strip(), abv_input.strip()))
            st.session_state.images[item["name"]] = get_rotated(i)
            progress.progress((i + 1) / len(st.session_state.staged_images), text=f"Checking {item['name']}...")
        progress_placeholder.empty()
        st.session_state.results.extend(results)
        st.rerun()

# Final UI rendering
with col_thumbs:
    if st.session_state.staged_images:
        for i, item in enumerate(st.session_state.staged_images):
            st.button(item["name"][:16], key=f"thumb_{i}", on_click=set_active, args=(i,), width='stretch')

with col_preview:
    if st.session_state.staged_images:
        st.image(get_rotated(st.session_state.active_idx), width='content')
    else:
        st.markdown('<div class="preview-placeholder">Waiting for image</div>', unsafe_allow_html=True)

with col_controls:
    if st.session_state.results:
        st.download_button("⬇ Download ZIP", data=build_export_zip(st.session_state.results), file_name=EXPORT_ZIP_NAME, mime="application/zip", width='stretch')

if st.session_state.results:
    st.divider()
    for result_idx, result in enumerate(reversed(st.session_state.results)):
        with st.container(border=True): render_result(result, len(st.session_state.results) - 1 - result_idx)