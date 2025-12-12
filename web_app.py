import streamlit as st
import google.generativeai as genai
import requests
import pypdf
import os
import time
import speech_recognition as sr

# --- CONFIGURATION ---
GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", None)
ELEVENLABS_API_KEY = st.secrets.get("E", None)
VOICE_ID = "21m00Tcm4TlvDq8ikWAM" 

# --- UI SETUP ---
st.set_page_config(page_title="AI Interviewer", page_icon="🤖")
st.title("🤖 AI Interviewer Pro")

# --- DIAGNOSTIC SECTION (Crucial for Debugging) ---
with st.expander("🛠️ System Diagnostics (Open if stuck)", expanded=False):
    st.write(f"**Streamlit Version:** {st.__version__}")
    if GOOGLE_API_KEY:
        try:
            st.write(f"**Google Library Version:** {genai.__version__}")
            genai.configure(api_key=GOOGLE_API_KEY)
            
            # ASK GOOGLE: "What models do you have?"
            st.write("Checking available models...")
            my_models = []
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    my_models.append(m.name)
            
            st.success(f"Found {len(my_models)} models: {my_models}")
        except Exception as e:
            st.error(f"Diagnostic Error: {e}")
    else:
        st.error("Google API Key missing.")

# --- SMART MODEL SELECTION ---
def get_working_model():
    if not GOOGLE_API_KEY: return None
    genai.configure(api_key=GOOGLE_API_KEY)
    
    # 1. Get list of ALL valid models from Google
    available_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
    except Exception as e:
        st.error(f"Connection Failed: {e}")
        return None

    # 2. Pick the best one that actually exists
    # We prefer Flash, but will take anything that is in the list.
    chosen_model = None
    
    # Priority list
    preferences = ["models/gemini-1.5-flash", "models/gemini-pro", "models/gemini-1.0-pro"]
    
    for pref in preferences:
        if pref in available_models:
            chosen_model = pref
            break
    
    # If priorities aren't there, just grab the first one in the list
    if not chosen_model and available_models:
        chosen_model = available_models[0]
        
    if chosen_model:
        print(f"✅ Selected Model: {chosen_model}")
        return genai.GenerativeModel(chosen_model)
    
    return None

model = get_working_model()

# --- AUDIO & UTILS ---
# --- AUDIO FUNCTION (DEBUG MODE) ---
def get_elevenlabs_audio(text):
    # 1. Check if Key exists
    if not ELEVENLABS_API_KEY:
        st.error("🚫 Error: ELEVENLABS_API_KEY is missing from Secrets.")
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
        
        # 2. Check for success
        if response.status_code == 200:
            return response.content
        else:
            # 3. PRINT THE ERROR (This tells us the problem)
            st.error(f"🔈 Voice Error: {response.text}")
            return None
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

def transcribe_audio(audio_file):
    r = sr.Recognizer()
    with sr.AudioFile(audio_file) as source:
        audio_data = r.record(source)
        try: return r.recognize_google(audio_data)
        except: return None

def read_pdf(file):
    reader = pypdf.PdfReader(file)
    text = ""
    for page in reader.pages: text += page.extract_text()
    return text

# --- APP LOGIC ---
if not GOOGLE_API_KEY or not ELEVENLABS_API_KEY:
    st.error("⚠️ API Keys are missing! Check Settings -> Secrets.")
    st.stop()

if "messages" not in st.session_state: st.session_state.messages = []
if "interview_active" not in st.session_state: st.session_state.interview_active = False

with st.sidebar:
    st.header("1. Upload Resume")
    uploaded_file = st.file_uploader("Choose PDF...", type=["pdf"])

    if uploaded_file:
        st.success("File Ready! ✅")
        if not st.session_state.interview_active:
            if st.button("🚀 Start Interview"):
                if not model:
                    st.error("❌ No AI models available. Check Diagnostics above.")
                else:
                    with st.spinner("AI is reading..."):
                        try:
                            text = read_pdf(uploaded_file)
                            prompt = f"Resume: {text}. \n\nGreet the candidate and ask the first question."
                            chat = model.start_chat(history=[])
                            response = chat.send_message(prompt)
                            st.session_state.chat_session = chat
                            
                            audio = get_elevenlabs_audio(response.text)
                            st.session_state.messages.append({"role": "assistant", "content": response.text, "audio": audio})
                            st.session_state.interview_active = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

# Chat Interface
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if "audio" in msg and msg["audio"]: st.audio(msg["audio"], format="audio/mp3")

if st.session_state.interview_active:
    audio_val = st.audio_input("🎤 Record Answer")
    text_val = st.chat_input("Type Answer...")
    
    final_input = None
    if audio_val:
        with st.spinner("Transcribing..."): final_input = transcribe_audio(audio_val)
    elif text_val:
        final_input = text_val
        
    if final_input:
        st.session_state.messages.append({"role": "user", "content": final_input})
        with st.chat_message("user"): st.write(final_input)
        
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    time.sleep(1)
                    chat = st.session_state.chat_session
                    response = chat.send_message(final_input)
                    st.write(response.text)
                    audio = get_elevenlabs_audio(response.text)
                    if audio: st.audio(audio, format="audio/mp3", autoplay=True)
                    st.session_state.messages.append({"role": "assistant", "content": response.text, "audio": audio})
                except Exception as e:
                    if "429" in str(e): st.warning("🚦 Speed Limit. Wait 10s.")
                    else: st.error(f"Error: {e}")
else:
    if not uploaded_file: st.info("👈 Upload Resume to Start")


