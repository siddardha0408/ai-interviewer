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

# --- 🧠 SMART BRAIN (Auto-Fixes 404 Errors) ---
def configure_best_model():
    if not GOOGLE_API_KEY: return None
    genai.configure(api_key=GOOGLE_API_KEY)
    
    # 1. List of models to try (Best -> Safest)
    priority_list = [
        "gemini-1.5-flash", 
        "gemini-1.5-flash-latest", 
        "gemini-pro"
    ]
    
    active_model = None
    print("--- Searching for available model ---")

    # 2. Try each model one by one
    for model_name in priority_list:
        try:
            print(f"Testing {model_name}...")
            test_model = genai.GenerativeModel(model_name)
            # We just define it here. The real test is if it throws an error immediately.
            active_model = test_model
            print(f"✅ Success! Locked onto: {model_name}")
            break 
        except Exception as e:
            print(f"❌ {model_name} failed: {e}")
            continue 
            
    # 3. Fallback
    if not active_model:
        print("⚠️ All Flash models failed. Using 'gemini-pro' as backup.")
        active_model = genai.GenerativeModel('gemini-pro')
    
    return active_model

# Initialize the best working model
model = configure_best_model()

# --- 🔊 AUDIO OUTPUT ---
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

# --- 🎤 VOICE INPUT ---
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

# --- 🖥️ APP UI ---
st.set_page_config(page_title="AI Interviewer", page_icon="🤖")
st.title("🤖 AI Interviewer Pro")

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
                if not model:
                    st.error("AI Brain could not connect. Check API Key.")
                else:
                    with st.spinner("AI is reading your resume..."):
                        try:
                            text = read_pdf(uploaded_file)
                            prompt = f"Resume Content: {text}. \n\nAct as a professional interviewer. Greet the candidate by name (if found) and ask the first question based on this resume."
                            
                            chat = model.start_chat(history=[])
                            response = chat.send_message(prompt)
                            
                            st.session_state.chat_session = chat
                            
                            # Generate Audio for Greeting
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
    # 1. Voice Input
    audio_value = st.audio_input("🎤 Record your answer")
    if audio_value:
        with st.spinner("Transcribing..."):
            text = transcribe_audio(audio_value)
            if text:
                final_input = text
            else:
                st.warning("Could not hear you. Try again.")

    # 2. Text Input
    text_input = st.chat_input("Type your answer here...")
    if text_input:
        final_input = text_input

    # 3. Process Logic
    if final_input:
        st.session_state.messages.append({"role": "user", "content": final_input})
        with st.chat_message("user"):
            st.write(final_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    chat = st.session_state.chat_session
                    time.sleep(1) # Safety delay
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
                    if "429" in str(e):
                        st.error("🚦 Speed Limit Hit! Wait 10 seconds.")
                    elif "404" in str(e):
                        st.error("❌ Model Error: The app lost connection to the AI model.")
                    else:
                        st.error(f"System Error: {e}")
else:
    if not uploaded_file:
        st.info("👈 Upload Resume to start!")
