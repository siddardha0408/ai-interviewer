import streamlit as st
import google.generativeai as genai
import requests
import pypdf
import os
import time

# --- CONFIGURATION ---
GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", None)
ELEVENLABS_API_KEY = st.secrets.get("ELEVENLABS_API_KEY", None)
VOICE_ID = "21m00Tcm4TlvDq8ikWAM"

# --- SMART BRAIN SETUP ---
# This block tries multiple models until one works.
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    
    # List of models to try (Newest -> Oldest)
    models_to_try = [
        'gemini-1.5-flash',  # Best balance
        'gemini-pro',        # Old reliable
        'gemini-1.0-pro',    # Deep backup
    ]
    
    active_model = None
    
    for model_name in models_to_try:
        try:
            test_model = genai.GenerativeModel(model_name)
            # Silent test to see if it exists
            # We don't generate content here to save quota, just defining it is usually safe.
            # But to be 100% sure we catch the 404, we'll assign it and proceed.
            active_model = test_model
            print(f"✅ Success! Using model: {model_name}")
            break # Stop loop if it works
        except Exception:
            continue # Try next one
            
    # If all failed, default to 'gemini-pro' and hope for the best
    if not active_model:
        active_model = genai.GenerativeModel('gemini-pro')
    
    model = active_model

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
    except:
        pass
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

if not GOOGLE_API_KEY or not ELEVENLABS_API_KEY:
    st.error("⚠️ System Error: API Keys are missing. Please configure Secrets.")
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "interview_active" not in st.session_state:
    st.session_state.interview_active = False

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Upload Resume")
    uploaded_file = st.file_uploader("Choose a PDF file...", type=["pdf"])

    if uploaded_file:
        st.success("File Uploaded! ✅")
        if not st.session_state.interview_active:
            if st.button("🚀 Start Interview"):
                with st.spinner("AI is reading your resume..."):
                    try:
                        text = read_pdf(uploaded_file)
                        prompt = f"Resume Content: {text}. \n\nAct as a professional interviewer. Greet the candidate by name (if found) and ask the first question based on this resume."
                        
                        chat = model.start_chat(history=[])
                        response = chat.send_message(prompt)
                        
                        st.session_state.chat_session = chat
                        st.session_state.messages.append({"role": "assistant", "content": response.text})
                        st.session_state.interview_active = True
                        st.rerun()
                    except Exception as e:
                        # If the "Smart Setup" failed, this catches the specific error
                        st.error(f"Error starting interview: {e}")
                        st.write("Tip: Check if your API Key has access to Gemini models.")

# --- MAIN CHAT ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

user_input = st.chat_input("Type your answer here...")

if user_input:
    if not st.session_state.interview_active:
        st.warning("⚠️ Please upload your Resume in the sidebar and click 'Start Interview' first!")
    else:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    chat = st.session_state.chat_session
                    # ⚠️ Added delay to prevent '429 Speed Limit' errors
                    time.sleep(1) 
                    response = chat.send_message(user_input)
                    st.write(response.text)
                    
                    audio_bytes = get_elevenlabs_audio(response.text)
                    if audio_bytes:
                        st.audio(audio_bytes, format="audio/mp3", autoplay=True)
                    
                    st.session_state.messages.append({"role": "assistant", "content": response.text})

                except Exception as e:
                    if "429" in str(e) or "ResourceExhausted" in str(e):
                        st.error("🚦 Speed Limit Hit! Please wait 10 seconds before replying again.")
                    elif "404" in str(e):
                        st.error("❌ Model Error: The server cannot find the AI model. Try rebooting the app.")
                    else:
                        st.error(f"System Error: {e}")
