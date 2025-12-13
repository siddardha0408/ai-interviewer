import streamlit as st
import google.generativeai as genai
import requests
import pypdf
import os
import tempfile

# --- CONFIGURATION ---
GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", None)
ELEVENLABS_API_KEY = st.secrets.get("E", None)
VOICE_ID = "21m00Tcm4TlvDq8ikWAM"

# --- SETUP ---
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    # Using 1.5-flash because it is fast and supports audio input directly
    model = genai.GenerativeModel('gemini-1.5-flash')

# --- FUNCTIONS ---

def get_elevenlabs_audio(text):
    """Fetch audio from ElevenLabs."""
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

def transcribe_audio(audio_file):
    """Uses Gemini to transcribe the audio file to text."""
    try:
        # 1. Save audio to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
            temp_audio.write(audio_file.getvalue())
            temp_path = temp_audio.name
        
        # 2. Upload to Gemini (It handles audio natively!)
        myfile = genai.upload_file(temp_path)
        
        # 3. Ask Gemini to transcribe
        result = model.generate_content([myfile, "Transcribe this audio exactly as spoken."])
        
        # 4. Clean up
        os.remove(temp_path)
        return result.text
    except Exception as e:
        st.error(f"Transcription failed: {e}")
        return None

def read_pdf(file):
    reader = pypdf.PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

# --- PAGE CONFIG ---
st.set_page_config(page_title="AI Interviewer", page_icon="🎙️")

# --- SESSION STATE ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None
if "resume_loaded" not in st.session_state:
    st.session_state.resume_loaded = False

# --- LOGIC FLOW ---

# MODE 1: LANDING PAGE (Upload Resume)
if not st.session_state.resume_loaded:
    st.title("🎙️ AI Voice Interviewer")
    st.markdown("### Step 1: Upload your Resume to start")
    
    uploaded_file = st.file_uploader("Upload PDF Resume", type=["pdf"])
    
    if uploaded_file:
        if st.button("🚀 Start Interview", type="primary"):
            if not GOOGLE_API_KEY:
                st.error("⚠️ API Keys missing in Secrets!")
                st.stop()
                
            with st.spinner("Analyzing profile..."):
                text = read_pdf(uploaded_file)
                prompt = f"Resume Content: {text}. You are a professional interviewer. Greet the candidate and ask the first question."
                
                chat = model.start_chat(history=[])
                response = chat.send_message(prompt)
                
                st.session_state.chat_session = chat
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                st.session_state.resume_loaded = True
                st.rerun()

# MODE 2: CHAT INTERFACE
else:
    st.title("🎙️ Interview Room")

    # --- CHAT HISTORY ---
    # We display history FIRST so the input is at the bottom
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # --- INPUT AREA (Voice OR Text) ---
    st.write("---")
    col1, col2 = st.columns([1, 4])
    
    user_text = None
    
    # OPTION A: AUDIO INPUT
    audio_val = st.audio_input("🎤 Speak your answer")
    
    # OPTION B: TEXT INPUT
    text_val = st.chat_input("Or type your answer here...")

    # LOGIC: Check which input was used
    if audio_val:
        with st.spinner("Listening & Transcribing..."):
            transcribed_text = transcribe_audio(audio_val)
            if transcribed_text:
                user_text = transcribed_text
    elif text_val:
        user_text = text_val

    # --- PROCESS INPUT ---
    if user_text:
        # 1. Show User Message
        st.session_state.messages.append({"role": "user", "content": user_text})
        with st.chat_message("user"):
            st.write(user_text)

        # 2. Generate AI Response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                chat = st.session_state.chat_session
                response = chat.send_message(user_text)
                st.write(response.text)
                
                # 3. GENERATE AUDIO (The "Impact" Part)
                # We do this immediately after text generation
                audio_bytes = get_elevenlabs_audio(response.text)
                if audio_bytes:
                    st.audio(audio_bytes, format="audio/mp3", autoplay=True)
                else:
                    st.warning("🔇 Voice limit reached or API error.")
        
        st.session_state.messages.append({"role": "assistant", "content": response.text})
        
        # Rerun to clear the input widgets specifically helps reset audio
        # Note: Streamlit handles reruns automatically for chat_input, 
        # but for audio_input we might need manual reset logic in complex apps.
        # For now, this standard flow works best.
