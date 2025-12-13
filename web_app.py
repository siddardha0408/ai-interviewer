import streamlit as st
import google.generativeai as genai
import requests
import pypdf
import os

# --- CONFIGURATION ---
GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", None)
ELEVENLABS_API_KEY = st.secrets.get("E", None)
VOICE_ID = "21m00Tcm4TlvDq8ikWAM"

# --- SETUP ---
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-flash-latest')

# --- FUNCTIONS ---
def get_elevenlabs_audio(text):
    if not ELEVENLABS_API_KEY: return None
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "text": text,
        "model_id": "eleven_flash_v2_5",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
    }
    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            return response.content
        else:
            return None # Silent fail for safety
    except:
        return None

def read_pdf(file):
    reader = pypdf.PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

# --- PAGE CONFIG ---
st.set_page_config(page_title="AI Interviewer", page_icon="🤖")

# --- SESSION STATE INITIALIZATION ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None
if "resume_loaded" not in st.session_state:
    st.session_state.resume_loaded = False

# --- LOGIC FLOW ---

# MODE 1: LANDING PAGE (If resume is NOT loaded yet)
if not st.session_state.resume_loaded:
    st.title("🤖 AI Interviewer Pro")
    st.markdown("""
    ### 👋 Welcome!
    I am your AI Interviewer. To begin the session, I need to understand your background.
    
    **Please upload your Resume (PDF) below to start.**
    """)
    
    # Big central uploader
    uploaded_file = st.file_uploader("Upload your Resume", type=["pdf"])
    
    if uploaded_file:
        if st.button("🚀 Start Interview", type="primary"):
            if not GOOGLE_API_KEY:
                st.error("⚠️ API Keys missing in Secrets!")
                st.stop()
                
            with st.spinner("Analyzing your profile..."):
                # 1. Read PDF
                text = read_pdf(uploaded_file)
                
                # 2. Initial Prompt
                prompt = f"Resume Content: {text}. You are a professional interviewer. Greet the candidate by name (if found) and ask the first technical question based on their skills."
                
                # 3. Create Chat Session
                chat = model.start_chat(history=[])
                response = chat.send_message(prompt)
                
                # 4. Save to State
                st.session_state.chat_session = chat
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                st.session_state.resume_loaded = True
                
                # 5. Refresh to switch to Chat Mode
                st.rerun()

# MODE 2: CHAT INTERFACE (If resume IS loaded)
else:
    st.title("🎙️ Interview in Progress")
    
    # "New Interview" button in sidebar to reset
    with st.sidebar:
        if st.button("🔄 Start New Interview"):
            st.session_state.messages = []
            st.session_state.chat_session = None
            st.session_state.resume_loaded = False
            st.rerun()

    # Display Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Chat Input
    user_input = st.chat_input("Type your answer here...")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                chat = st.session_state.chat_session
                response = chat.send_message(user_input)
                st.write(response.text)
                
                # Audio Playback
                audio_bytes = get_elevenlabs_audio(response.text)
                if audio_bytes:
                    st.audio(audio_bytes, format="audio/mp3", autoplay=True)
                else:
                    st.caption("🔇 Voice unavailable (Server Limit)")
                
        st.session_state.messages.append({"role": "assistant", "content": response.text})
