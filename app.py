"""
app.py
------
Dynamic Mind Map Generator — secured by DAF (Dynamic Auth Framework)

Run:
  streamlit run app.py
"""

import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path
import tempfile
import os

from dotenv import load_dotenv
load_dotenv()

from auth import is_authenticated, get_current_user, logout, show_auth_page
from extractor import extract_mindmap
from storage import save_map, load_map, list_maps, delete_map, map_exists
from renderer import render_mindmap

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="MapGen — Mind Map Generator",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Auth gate ─────────────────────────────────────────────────────────────────

if not is_authenticated():
    show_auth_page()
    st.stop()

# ── Authenticated — get user context ──────────────────────────────────────────

user     = get_current_user()
user_id  = user["id"]
username = user["username"]

# ── Styling ───────────────────────────────────────────────────────────────────

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #0E0E0E; }
[data-testid="stHeader"]           { background: transparent; }
[data-testid="stSidebar"]          { background: #141414; border-right: 1px solid #242424; }
#MainMenu, footer { visibility: hidden; }
h1, h2, h3 { color: #E6E1D6; font-weight: 700; }
p, li       { color: #AAA; }
.divider { border: none; border-top: 1px solid #242424; margin: 20px 0; }
.mono    { font-family: monospace; font-size: 12px; color: #666; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────

for key, default in {"current_map_id": None, "error": None}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ── Query param routing ───────────────────────────────────────────────────────

params = st.query_params
if "map_id" in params and st.session_state.current_map_id is None:
    incoming_id = params["map_id"]
    if map_exists(incoming_id, user_id):
        st.session_state.current_map_id = incoming_id

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(f"""
    <div style="padding: 8px 0 20px 0;">
        <div style="font-family:monospace; font-size:10px; letter-spacing:2px;
             text-transform:uppercase; color:#555; margin-bottom:6px;">Signed in as</div>
        <div style="font-size:16px; font-weight:700; color:#C8B97A;">◈ {username}</div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("＋ New map", use_container_width=True, type="primary"):
            st.session_state.current_map_id = None
            st.session_state.error = None
            st.query_params.clear()
            st.rerun()
    with col2:
        if st.button("Sign out", use_container_width=True):
            logout()
            st.query_params.clear()
            st.rerun()

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    st.markdown("<div class='mono'>Your maps</div>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    saved = list_maps(user_id)

    if not saved:
        st.markdown(
            "<div style='color:#555; font-size:13px;'>No maps yet — upload a PDF to get started.</div>",
            unsafe_allow_html=True
        )
    else:
        for entry in saved:
            c1, c2 = st.columns([5, 1])
            with c1:
                is_active = entry["id"] == st.session_state.current_map_id
                label = f"{'▶ ' if is_active else ''}{entry['subject']}"
                if st.button(label, key=f"load_{entry['id']}", use_container_width=True):
                    st.session_state.current_map_id = entry["id"]
                    st.session_state.error = None
                    st.query_params["map_id"] = entry["id"]
                    st.rerun()
            with c2:
                if st.button("✕", key=f"del_{entry['id']}"):
                    delete_map(entry["id"], user_id)
                    if st.session_state.current_map_id == entry["id"]:
                        st.session_state.current_map_id = None
                        st.query_params.clear()
                    st.rerun()

            created = entry.get("created_at", "")[:16].replace("T", " ")
            st.markdown(
                f"<div class='mono' style='margin:-6px 0 10px 0;'>"
                f"{created} · {entry['theme_count']} themes · {entry['lecture_count']} lectures"
                f"{'  ⚠' if entry.get('has_warnings') else ''}</div>",
                unsafe_allow_html=True
            )

# ── Main: view map ────────────────────────────────────────────────────────────

if st.session_state.current_map_id:
    map_id = st.session_state.current_map_id

    try:
        schema = load_map(map_id, user_id)
    except FileNotFoundError as e:
        st.session_state.current_map_id = None
        st.session_state.error = str(e)
        st.rerun()

    if schema.get("warnings"):
        with st.expander(f"⚠ {len(schema['warnings'])} extraction warning(s)", expanded=False):
            for w in schema["warnings"]:
                st.markdown(f"- {w}")

    try:
        base_url = st.secrets["APP_BASE_URL"]
    except Exception:
        base_url = os.getenv("APP_BASE_URL", "http://localhost:8501")
    share_url = f"{base_url}/?map_id={map_id}"
    st.markdown(
        f"<div style='font-family:monospace; font-size:12px; color:#555; margin-bottom:16px;'>"
        f"🔗 {share_url}</div>",
        unsafe_allow_html=True
    )

    try:
        html = render_mindmap(schema)
        components.html(html, height=820, scrolling=False)
    except ValueError as e:
        st.error(f"Render error: {e}")

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    try:
        html_bytes = render_mindmap(schema).encode("utf-8")
        st.download_button(
            label="⬇ Download HTML",
            data=html_bytes,
            file_name=f"{schema.get('subject', 'mindmap').replace(' ', '_')}.html",
            mime="text/html",
        )
    except Exception:
        pass

# ── Main: upload ──────────────────────────────────────────────────────────────

else:
    if st.session_state.error:
        st.error(st.session_state.error)
        st.session_state.error = None

    st.markdown("""
    <div style="padding: 32px 0 8px 0;">
        <div style="font-family:monospace; font-size:10px; letter-spacing:2px;
             text-transform:uppercase; color:#555; margin-bottom:8px;">Knowledge Graph Generator</div>
        <h1 style="margin:0; font-size:32px; color:#E6E1D6;">
            Upload a PDF.<br>Get an interactive mind map.
        </h1>
        <p style="margin-top:12px; color:#666; font-size:15px;">
            Structured lecture notes, course slides, or textbook chapters work best.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2])

    with col1:
        uploaded = st.file_uploader("Upload PDF", type=["pdf"], label_visibility="collapsed")
        if uploaded:
            st.markdown(
                f"<div class='mono'>📄 {uploaded.name} · {uploaded.size / 1024:.1f} KB</div>",
                unsafe_allow_html=True
            )

    with col2:
        st.markdown("""
        <div style="background:#141414; border:1px solid #242424; border-radius:10px; padding:20px 24px;">
            <div style="font-family:monospace; font-size:10px; letter-spacing:2px;
                 text-transform:uppercase; color:#555; margin-bottom:12px;">Works best with</div>
            <ul style="color:#888; font-size:13px; padding-left:16px; margin:0;">
                <li>Lecture slide decks (PDF export)</li>
                <li>Structured course notes</li>
                <li>Textbook chapters with clear headings</li>
            </ul>
            <div style="margin-top:16px; font-family:monospace; font-size:10px;
                 letter-spacing:2px; text-transform:uppercase; color:#555;">Not supported</div>
            <ul style="color:#888; font-size:13px; padding-left:16px; margin:8px 0 0 0;">
                <li>Scanned / image-only PDFs</li>
                <li>Password-protected files</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("Generate mind map →", type="primary", disabled=(uploaded is None)):
        with st.spinner("Extracting knowledge structure via Claude…"):
            suffix = Path(uploaded.name).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name
            try:
                schema = extract_mindmap(tmp_path)
                schema["source_file"] = uploaded.name
                map_id = save_map(schema, user_id)
                st.session_state.current_map_id = map_id
                st.query_params["map_id"] = map_id
                st.rerun()
            except ValueError as e:
                st.session_state.error = str(e)
                st.rerun()
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
