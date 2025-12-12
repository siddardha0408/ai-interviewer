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

# --- SMART MODEL SELECTOR (The Fix) ---
def configure_best_model():
    if not GOOGLE_API_KEY: return None
    
    genai.configure(api_key=GOOGLE_API_KEY)
    
    # 1. Ask Google what models are available for THIS key
    available_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
    except Exception as e:
        st.error(f"Error listing models: {e}")
        return None

    # 2. Priority List (We want these first if available)
    # We prioritize 1.5 Flash because it has the best Free Tier limits
    priority_list = [
        "models/gemini-1.5-flash",
        "models/gemini-1.5-flash-latest",
        "models/gemini-1.5-pro",
        "models/gemini-1.0-pro",
        "models/gemini-pro"
    ]

    selected_model_name = None

    # Check if any priority model exists in the user's list
    for priority in priority_list:
        if priority in available_models:
            selected_model_name = priority
            break
            
    # Fallback: If none match, just take the first available one
    if not selected_model_name and available_models:
        selected_model_name = available_models[0]

    if selected_model_name:
        print(f"✅ Auto-Selected Model: {selected_model_name}")
        return genai.GenerativeModel(selected_model_name)
    else:
        st.error("❌ No available Gemini models found for this API Key.")
        return None

# Initialize the model using the smart function
model = configure_best_model()

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
                            st.session_state.messages.append({"role": "assistant", "content": response.text})
                            st.session_state.interview_active = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error starting interview: {e}")

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
                    time.sleep(1) 
                    response = chat.send_message(user_input)
                    st.write(response.text)
                    
                    audio_bytes = get_elevenlabs_audio(response.text)
                    if audio_bytes:
                        st.audio(audio_bytes, format="audio/mp3", autoplay=True)
                    
                    st.session_state.messages.append({"role": "assistant", "content": response.text})

                except Exception as e:
                    if "429" in str(e) or "ResourceExhausted" in str(e):
                        st.error("🚦 Speed Limit Hit! Please wait 10 seconds.")
                    else:
                        st.error(f"System Error: {e}")
