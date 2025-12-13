import streamlit as st
import google.generativeai as genai
import requests
import pypdf
import os

# --- CONFIGURATION ---
# Checks for keys in Streamlit Secrets.
GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", None)
ELEVENLABS_API_KEY = st.secrets.get("ELEVENLABS_API_KEY", None)
VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel Voice

# --- SETUP ---
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-flash-latest')

# --- FUNCTIONS ---

def get_elevenlabs_audio(text):
    """
    Generates audio but catches the Vultr/Free Tier 'Unusual Activity' error
    so it doesn't break the app or show ugly errors.
    """
    if not ELEVENLABS_API_KEY: 
        return None
        
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
        
        # Success Case
        if response.status_code == 200:
            return response.content
            
        # Error Handling
        else:
            error_msg = response.text
            # Specifically check for the Vultr/Free Tier error
            if "unusual_activity" in error_msg:
                print("⚠️ ElevenLabs Error: Free Tier usage on Vultr detected. Audio suppressed.")
                return None  # Return None silently
            
            # Log other errors to console only (not UI)
            print(f"⚠️ ElevenLabs API Error: {response.status_code} - {error_msg}")
            return None
            
    except Exception as e:
        print(f"⚠️ Audio Connection Error: {e}")
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

# Check for keys
if not GOOGLE_API_KEY or not ELEVENLABS_API_KEY:
    st.error("⚠️ API Keys are missing! Please set them in Streamlit Secrets.")
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar
with st.sidebar:
    st.header("Setup")
    uploaded_file = st.file_uploader("Upload Resume (PDF)", type=["pdf"])
    
    # Logic to load resume only once
    if uploaded_file and not st.session_state.get("resume_loaded", False):
        if st.button("Analyze Resume"):
            with st.spinner("Reading..."):
                text = read_pdf(uploaded_file)
                prompt = f"Resume Content: {text}. Greet the candidate and ask the first question."
                
                chat = model.start_chat(history=[])
                response = chat.send_message(prompt)
                
                st.session_state.chat_session = chat
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                st.session_state.resume_loaded = True
                st.rerun()

# Chat Area
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Input Area
user_input = st.chat_input("Type your answer here...")

if user_input:
    # 1. Show User Input
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # 2. Generate and Show AI Response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            chat = st.session_state.chat_session
            response = chat.send_message(user_input)
            st.write(response.text)
            
            # 3. Handle Audio Safely
            audio_bytes = get_elevenlabs_audio(response.text)
            if audio_bytes:
                st.audio(audio_bytes, format="audio/mp3", autoplay=True)
            else:
                # Show a polite note instead of a red error
                st.caption("🔇 Voice mode unavailable (Server Limit)")
            
    st.session_state.messages.append({"role": "assistant", "content": response.text})
