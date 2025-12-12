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
VOICE_ID = "21m00Tcm4TlvDq8ikWAM" # Rachel Voice

# --- SMART MODEL SELECTOR ---
def configure_best_model():
    if not GOOGLE_API_KEY: return None
    genai.configure(api_key=GOOGLE_API_KEY)
    
    # Try 1.5 Flash (Fastest) -> Pro (Reliable)
    priority_list = ["models/gemini-1.5-flash", "models/gemini-pro"]
    
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for priority in priority_list:
            if priority in available_models:
                return genai.GenerativeModel(priority)
    except:
        pass
    return genai.GenerativeModel('gemini-pro')

model = configure_best_model()

# --- AUDIO FUNCTION (WITH DEBUGGING) ---
def get_elevenlabs_audio(text):
    if not ELEVENLABS_API_KEY: 
        st.warning("⚠️ No ElevenLabs Key found in Secrets!")
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
        if response.status_code == 200:
            return response.content
        else:
            # Show the actual error on screen if it fails
            st.error(f"Voice Error: {response.text}")
            return None
    except Exception as e:
        st.error(f"Connection Error: {e}")
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
st.title("🤖 AI Interviewer Pro")

if not GOOGLE_API_KEY or not ELEVENLABS_API_KEY:
    st.error("⚠️ API Keys are missing! Go to 'Manage App' -> 'Secrets' to add them.")
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
                if not model:
                    st.error("AI Brain not connected.")
                else:
                    with st.spinner("AI is reading your resume..."):
                        try:
                            text = read_pdf(uploaded_file)
                            prompt = f"Resume Content: {text}. \n\nAct as a professional interviewer. Greet the candidate by name (if found) and ask the first question based on this resume."
                            
                            chat = model.start_chat(history=[])
                            response = chat.send_message(prompt)
                            
                            st.session_state.chat_session = chat
                            # Store the greeting
                            st.session_state.messages.append({"role": "assistant", "content": response.text, "audio": get_elevenlabs_audio(response.text)})
                            st.session_state.interview_active = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error starting interview: {e}")

# --- MAIN CHAT ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        # If this message has audio attached, show the player
        if "audio" in msg and msg["audio"]:
            st.audio(msg["audio"], format="audio/mp3", autoplay=False)

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
                st.warning("Could not understand audio. Try again.")

    # Text Input
    text_input = st.chat_input("Type your answer here...")
    if text_input:
        final_input = text_input

    # Process Input
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
                    
                    # Generate Audio
                    audio_bytes = get_elevenlabs_audio(response.text)
                    if audio_bytes:
                        # Auto-play the newest message
                        st.audio(audio_bytes, format="audio/mp3", autoplay=True)
                    
                    st.session_state.messages.append({"role": "assistant", "content": response.text, "audio": audio_bytes})

                except Exception as e:
                    if "429" in str(e):
                        st.error("🚦 Speed Limit Hit! Wait 10 seconds.")
                    else:
                        st.error(f"System Error: {e}")
else:
    if not uploaded_file:
        st.info("👈 Please upload a Resume to unlock the microphone and chat!")
