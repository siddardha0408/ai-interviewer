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
            # Silent fail for Vultr/Free tier issues
            return None
    except:
        return None

def read_pdf(file):
    reader = pypdf.PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

# --- APP UI ---
st.set_page_config(page_title="AI Interviewer", page_icon="🤖")
st.title("🤖 AI Interviewer Pro")

if not GOOGLE_API_KEY:
    st.error("⚠️ GOOGLE_API_KEY is missing in Secrets.")
    st.stop()

# --- 1. SAFE SESSION STATE INITIALIZATION (The Fix) ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# Initialize chat_session to None if it doesn't exist
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None

if "resume_loaded" not in st.session_state:
    st.session_state.resume_loaded = False

# --- SIDEBAR ---
with st.sidebar:
    st.header("Setup")
    uploaded_file = st.file_uploader("Upload Resume (PDF)", type=["pdf"])
    
    if uploaded_file and not st.session_state.resume_loaded:
        if st.button("Analyze Resume"):
            with st.spinner("Reading..."):
                text = read_pdf(uploaded_file)
                prompt = f"Resume Content: {text}. Greet the candidate and ask the first question."
                
                # Create the chat session
                chat = model.start_chat(history=[])
                response = chat.send_message(prompt)
                
                # Store it in session state
                st.session_state.chat_session = chat
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                st.session_state.resume_loaded = True
                st.rerun()

# --- CHAT AREA ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# --- INPUT AREA ---
user_input = st.chat_input("Type your answer here...")

if user_input:
    # --- 2. SAFETY CHECK (The Fix) ---
    # If the user tries to type BEFORE uploading a resume, stop them.
    if st.session_state.chat_session is None:
        st.error("⚠️ Please upload a resume and click 'Analyze Resume' first!")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            # Now we know chat_session exists because of the check above
            chat = st.session_state.chat_session
            response = chat.send_message(user_input)
            st.write(response.text)
            
            audio_bytes = get_elevenlabs_audio(response.text)
            if audio_bytes:
                st.audio(audio_bytes, format="audio/mp3", autoplay=True)
            else:
                st.caption("🔇 Voice unavailable (Server Limit)")
            
    st.session_state.messages.append({"role": "assistant", "content": response.text})
