import streamlit as st
import google.generativeai as genai
import requests
import pypdf
import os
import time
import speech_recognition as sr

# --- CONFIGURATION ---
GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", None)
ELEVENLABS_API_KEY = st.secrets.get("ELEVENLABS_API_KEY", None)
VOICE_ID = "21m00Tcm4TlvDq8ikWAM" 

# --- SETUP ---
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    
    # 🛑 SAFE MODE: Hardcoded to 'gemini-pro' (The most compatible model)
    try:
        model = genai.GenerativeModel('gemini-pro')
    except:
        st.error("Critical Error: Even gemini-pro failed. Please delete the app and redeploy.")

# --- AUDIO FUNCTION ---
def get_elevenlabs_audio(text):
    if not ELEVENLABS_API_KEY: return None
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2", # Changed to older, safer model
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
    }
    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            return response.content
    except:
        pass
    return None

def transcribe_audio(audio_file):
    r = sr.Recognizer()
    with sr.AudioFile(audio_file) as source:
        audio_data = r.record(source)
        try:
            return r.recognize_google(audio_data)
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
st.title("🤖 AI Interviewer Pro (Safe Mode)")

if not GOOGLE_API_KEY or not ELEVENLABS_API_KEY:
    st.error("⚠️ API Keys are missing! Go to Settings -> Secrets.")
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
                        
                        # Greeting Audio
                        audio_data = get_elevenlabs_audio(response.text)
                        
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": response.text,
                            "audio": audio_data
                        })
                        st.session_state.interview_active = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error starting interview: {e}")

# --- MAIN CHAT ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if "audio" in msg and msg["audio"]:
            st.audio(msg["audio"], format="audio/mp3")

# --- INPUT AREA ---
final_input = None

if st.session_state.interview_active:
    # Voice Input
    audio_value = st.audio_input("🎤 Record your answer")
    if audio_value:
        with st.spinner("Transcribing..."):
            text = transcribe_audio(audio_value)
            if text:
                final_input = text
            else:
                st.warning("Could not hear you. Try again.")

    # Text Input
    text_input = st.chat_input("Type your answer here...")
    if text_input:
        final_input = text_input

    # Process
    if final_input:
        st.session_state.messages.append({"role": "user", "content": final_input})
        with st.chat_message("user"):
            st.write(final_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    chat = st.session_state.chat_session
                    time.sleep(1) 
                    response = chat.send_message(final_input)
                    st.write(response.text)
                    
                    audio_bytes = get_elevenlabs_audio(response.text)
                    if audio_bytes:
                        st.audio(audio_bytes, format="audio/mp3", autoplay=True)
                    
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": response.text,
                        "audio": audio_bytes
                    })

                except Exception as e:
                     st.error(f"System Error: {e}")
else:
    if not uploaded_file:
        st.info("👈 Upload Resume to start!")
