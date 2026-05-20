"""
auth.py
-------
DPP (Dynamic Password Protocol) authentication for the Mind Map app.
Extracted directly from DAF streamlit_app.py — same Supabase project,
same daf_users table, same DPP logic.

Reference:
  "Dynamic Password Protocol for User Authentication"
  H. Channabasava & S. Kanthimathi, CompCom 2019, Springer Nature
"""

import hmac
from datetime import datetime, timezone

import streamlit as st
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError


# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_PLACEHOLDER = "x"

_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65_536,
    parallelism=4,
    hash_len=32,
)


# ── Supabase client ───────────────────────────────────────────────────────────

from db import get_supabase


# ── DPP Core ──────────────────────────────────────────────────────────────────

def _build_parameter_map(password: str, placeholder: str) -> str:
    return "".join("1" if ch == placeholder else "0" for ch in password)


def _extract_static_part(password: str, parameter_map: str) -> str:
    return "".join(ch for ch, flag in zip(password, parameter_map) if flag == "0")


def _extract_dynamic_part(password: str, parameter_map: str) -> str:
    return "".join(ch for ch, flag in zip(password, parameter_map) if flag == "1")


def _get_current_time_parameter() -> str:
    """Return current UTC time as HHMM string."""
    return datetime.now(tz=timezone.utc).strftime("%H%M")


def _secure_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def dpp_register(password: str, placeholder: str = DEFAULT_PLACEHOLDER) -> tuple[str, str]:
    """
    Register — returns (static_hash, parameter_map).
    Raises ValueError on invalid input.
    """
    if not password:
        raise ValueError("Password must not be empty.")
    if len(placeholder) != 1:
        raise ValueError("Placeholder must be exactly one character.")
    if all(ch == placeholder for ch in password):
        raise ValueError("Password must contain at least one static character.")

    parameter_map = _build_parameter_map(password, placeholder)
    static_part   = _extract_static_part(password, parameter_map)
    static_hash   = _HASHER.hash(static_part)
    return static_hash, parameter_map


def dpp_authenticate(
    input_password: str,
    stored_hash: str,
    parameter_map: str,
) -> bool:
    """Two-stage DPP authentication — returns True/False."""
    if len(input_password) != len(parameter_map):
        return False

    # Stage 1 — Dynamic: extracted digits must match current UTC time
    dynamic_part = _extract_dynamic_part(input_password, parameter_map)
    live_dynamic = _get_current_time_parameter()
    if not _secure_compare(dynamic_part, live_dynamic):
        return False

    # Stage 2 — Static: extracted letters must match Argon2id hash
    static_part = _extract_static_part(input_password, parameter_map)
    try:
        _HASHER.verify(stored_hash, static_part)
        return True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


# ── Supabase DB operations ────────────────────────────────────────────────────

def db_user_exists(username: str) -> bool:
    supabase = get_supabase()
    result = supabase.table("daf_users") \
        .select("id") \
        .eq("username", username) \
        .execute()
    return len(result.data) > 0


def db_create_user(
    username: str,
    static_hash: str,
    parameter_map: str,
    placeholder: str,
):
    supabase = get_supabase()
    supabase.table("daf_users").insert({
        "username":      username,
        "static_hash":   static_hash,
        "parameter_map": parameter_map,
        "placeholder":   placeholder,
        "is_active":     True,
    }).execute()


def db_get_user(username: str) -> dict | None:
    supabase = get_supabase()
    result = supabase.table("daf_users") \
        .select("*") \
        .eq("username", username) \
        .execute()
    return result.data[0] if result.data else None


# ── Session helpers ───────────────────────────────────────────────────────────

def is_authenticated() -> bool:
    return st.session_state.get("authenticated", False)


def get_current_user() -> dict | None:
    return st.session_state.get("current_user", None)


def login(user: dict):
    """Set authenticated session state."""
    st.session_state["authenticated"] = True
    st.session_state["current_user"]  = user


def logout():
    """Clear session state."""
    for key in ["authenticated", "current_user"]:
        st.session_state.pop(key, None)


# ── Auth UI ───────────────────────────────────────────────────────────────────

def show_auth_page():
    """
    Render the full login/register UI.
    Blocks app rendering until authenticated.
    """
    st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background: #0D0D0D; }
    [data-testid="stHeader"]           { background: transparent; }
    .auth-header {
        text-align: center;
        padding: 40px 0 32px 0;
    }
    .auth-logo {
        font-family: monospace;
        font-size: 32px;
        color: #C8B97A;
        font-weight: 800;
        letter-spacing: -1px;
    }
    .auth-sub {
        font-size: 13px;
        color: #555;
        margin-top: 6px;
        font-family: monospace;
    }
    .auth-card {
        background: #141414;
        border: 1px solid #242424;
        border-radius: 12px;
        padding: 32px;
        max-width: 440px;
        margin: 0 auto;
    }
    .info-box {
        background: #1A1A1A;
        border-left: 3px solid #C8B97A;
        border-radius: 4px;
        padding: 12px 16px;
        font-size: 12px;
        color: #888;
        margin-bottom: 20px;
        font-family: monospace;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="auth-header">
        <div class="auth-logo">◈ MapGen</div>
        <div class="auth-sub">Dynamic Mind Map Generator · Secured by DAF</div>
    </div>
    """, unsafe_allow_html=True)

    utc_now = datetime.now(tz=timezone.utc)
    hhmm    = utc_now.strftime("%H%M")

    tab_login, tab_register = st.tabs(["Sign In", "Register"])

    # ── LOGIN ─────────────────────────────────────────────────────────────────
    with tab_login:
        st.markdown(f"""
        <div class="info-box">
            Current UTC: <b>{utc_now.strftime("%H:%M")} UTC</b>
            &nbsp;·&nbsp; Dynamic value: <b>{hhmm}</b>
            &nbsp;·&nbsp; Fill your <b>x</b> positions with these digits
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            username  = st.text_input("Username", placeholder="e.g. botnet")
            password  = st.text_input("Password", type="password",
                                       placeholder=f"e.g. Bot{hhmm[:2]}net{hhmm[2:]}")
            submitted = st.form_submit_button("Sign in →", use_container_width=True,
                                               type="primary")

        if submitted:
            if not username or not password:
                st.error("Username and password are required.")
            else:
                with st.spinner("Verifying…"):
                    user = db_get_user(username.strip())
                    if not user or not user.get("is_active"):
                        st.error("Invalid credentials.")
                    else:
                        success = dpp_authenticate(
                            input_password=password,
                            stored_hash=user["static_hash"],
                            parameter_map=user["parameter_map"],
                        )
                        if success:
                            login(user)
                            st.rerun()
                        else:
                            st.error("Invalid credentials.")

    # ── REGISTER ──────────────────────────────────────────────────────────────
    with tab_register:
        st.markdown("""
        <div class="info-box">
            Use <b>x</b> to mark dynamic positions in your password.<br>
            e.g. <b>Botxxnetxx</b> → at 21:30 UTC → login with <b>Bot21net30</b>
        </div>
        """, unsafe_allow_html=True)

        with st.form("register_form"):
            new_username  = st.text_input("Username", placeholder="e.g. botnet")
            new_password  = st.text_input("Registration password", type="password",
                                           placeholder="e.g. Botxxnetxx")
            placeholder   = st.text_input("Placeholder character",
                                           value="x", max_chars=1)
            submitted_reg = st.form_submit_button("Create account →",
                                                   use_container_width=True,
                                                   type="primary")

        if submitted_reg:
            if not new_username or not new_password:
                st.error("All fields are required.")
            else:
                with st.spinner("Creating account…"):
                    try:
                        uname = new_username.strip()
                        if db_user_exists(uname):
                            st.error("Username already taken.")
                        else:
                            static_hash, parameter_map = dpp_register(
                                new_password, placeholder
                            )
                            db_create_user(uname, static_hash, parameter_map, placeholder)
                            st.success("Account created — sign in above.")
                            col1, col2, col3 = st.columns(3)
                            col1.metric("Length",   len(parameter_map))
                            col2.metric("Static",   parameter_map.count("0"))
                            col3.metric("Dynamic",  parameter_map.count("1"))
                            st.code(f"Parameter map: {parameter_map}")
                    except ValueError as e:
                        st.error(str(e))
