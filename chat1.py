import os
import streamlit as st
import google.generativeai as genai
from supabase import create_client, Client

st.set_page_config(page_title="Gemini Chatbot", page_icon="🤖", layout="centered")

# CONFIG - set these in .streamlit/secrets.toml
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL", ""))
SUPABASE_ANON = st.secrets.get("SUPABASE_ANON_KEY", os.getenv("SUPABASE_ANON_KEY", ""))
MODEL_NAME = "gemini-2.5-flash"

missing = [k for k, v in {"GEMINI_API_KEY": GEMINI_API_KEY, "SUPABASE_URL": SUPABASE_URL, "SUPABASE_ANON_KEY": SUPABASE_ANON}.items() if not v]
if missing:
    st.error(f"Missing secrets: {', '.join(missing)}. Add them to `.streamlit/secrets.toml`.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)

@st.cache_resource
def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_ANON)

supabase = get_supabase()

# SESSION STATE DEFAULTS
for k, v in {"user": None, "access_token": None, "messages": [], "chat_session": None, "auth_mode": "Sign In", "auth_error": "", "auth_success": ""}.items():
    if k not in st.session_state:
        st.session_state[k] = v


def sign_up(email, password):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        if res.user:
            st.session_state.auth_success = "Account created! Check your email to confirm, then sign in."
            st.session_state.auth_error = ""
        else:
            st.session_state.auth_error = "Sign-up failed. Try again."
    except Exception as e:
        st.session_state.auth_error = f"Error: {e}"


def sign_in(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if res.user:
            st.session_state.user = res.user
            st.session_state.access_token = res.session.access_token
            st.session_state.auth_error = ""
            model = genai.GenerativeModel(model_name=MODEL_NAME)
            st.session_state.chat_session = model.start_chat(history=[])
            st.session_state.messages = []
            st.rerun()
        else:
            st.session_state.auth_error = "Invalid email or password."
    except Exception as e:
        st.session_state.auth_error = f"Error: {e}"


def sign_out():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    for key in ["user", "access_token", "chat_session"]:
        st.session_state[key] = None
    st.session_state.messages = []
    st.rerun()


def show_auth_page():
    st.markdown("<h2 style='text-align:center'>🤖 Gemini Chatbot</h2><p style='text-align:center;color:gray'>Sign in to start chatting</p>", unsafe_allow_html=True)
    st.divider()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        mode = st.radio("Mode", ["Sign In", "Sign Up"], index=0 if st.session_state.auth_mode == "Sign In" else 1, horizontal=True, label_visibility="collapsed")
        st.session_state.auth_mode = mode
        st.markdown(f"### {mode}")

        email = st.text_input("Email", placeholder="you@example.com", key="auth_email")
        password = st.text_input("Password", placeholder="Password (min 6 chars)", type="password", key="auth_password")
        confirm = None
        if mode == "Sign Up":
            confirm = st.text_input("Confirm Password", placeholder="Repeat password", type="password", key="auth_confirm")

        if st.session_state.auth_error:
            st.error(st.session_state.auth_error)
        if st.session_state.auth_success:
            st.success(st.session_state.auth_success)

        st.write("")
        if st.button(mode, use_container_width=True, type="primary"):
            if not email or not password:
                st.session_state.auth_error = "Email and password are required."
                st.rerun()
            elif mode == "Sign Up":
                if confirm is None or password != confirm:
                    st.session_state.auth_error = "Passwords do not match."
                    st.rerun()
                elif len(password) < 6:
                    st.session_state.auth_error = "Password must be at least 6 characters."
                    st.rerun()
                else:
                    sign_up(email, password)
                    st.rerun()
            else:
                sign_in(email, password)


def show_chat_page():
    user_email = st.session_state.user.email

    with st.sidebar:
        st.markdown(f"👤 **{user_email}**")
        st.divider()
        st.header("Settings")
        temperature = st.slider("Temperature", 0.0, 1.0, 0.7, 0.1)
        max_tokens = st.slider("Max output tokens", 256, 2048, 1024, 128)
        st.divider()
        if st.button("🗑️ Clear Chat", use_container_width=True):
            model = genai.GenerativeModel(model_name=MODEL_NAME)
            st.session_state.chat_session = model.start_chat(history=[])
            st.session_state.messages = []
            st.rerun()
        st.divider()
        if st.button("🚪 Sign Out", use_container_width=True):
            sign_out()
        st.caption(f"Model: `{MODEL_NAME}`")
        st.caption(f"Messages: {len(st.session_state.messages)}")

    st.title("🤖 Gemini Chatbot")
    st.caption("Session memory enabled · Powered by Gemini 2.5 Flash")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_input := st.chat_input("Type a message..."):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = st.session_state.chat_session.send_message(
                    user_input,
                    generation_config=genai.types.GenerationConfig(temperature=temperature, max_output_tokens=max_tokens),
                )
                reply = response.text
            st.markdown(reply)

        st.session_state.messages.append({"role": "assistant", "content": reply})


# ROUTER
if st.session_state.user is None:
    show_auth_page()
else:
    show_chat_page()
