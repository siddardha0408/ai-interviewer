import streamlit as st
import google.generativeai as genai
import requests
import pypdf
import os
import time # Add this to the top imports

# ... inside the chat loop ...
with st.chat_message("assistant"):
    with st.spinner("Thinking..."):
        time.sleep(2) # Wait 2 seconds to respect the speed limit
        chat = st.session_state.chat_session
        response = chat.send_message(user_input)

# --- CONFIGURATION ---
GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", None)
ELEVENLABS_API_KEY = st.secrets.get("ELEVENLABS_API_KEY", None)
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

# 1. Check API Keys
if not GOOGLE_API_KEY or not ELEVENLABS_API_KEY:
    st.error("⚠️ System Error: API Keys are missing. Please configure Secrets.")
    st.stop()

# 2. Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "interview_active" not in st.session_state:
    st.session_state.interview_active = False

# --- SIDEBAR (UPLOAD ONLY) ---
with st.sidebar:
    st.header("1. Upload Resume")
    # This forces the user to pick a file. 
    # The app will NOT proceed without this.
    uploaded_file = st.file_uploader("Choose a PDF file...", type=["pdf"])

    if uploaded_file:
        st.success("File Uploaded! ✅")
        
        # Only show the button if file is there and interview hasn't started
        if not st.session_state.interview_active:
            if st.button("🚀 Start Interview"):
                with st.spinner("AI is reading your resume..."):
                    # Read the User's PDF
                    text = read_pdf(uploaded_file)
                    
                    # Send to AI
                    prompt = f"Resume Content: {text}. \n\nAct as a professional interviewer. Greet the candidate by name (if found) and ask the first question based on this resume."
                    
                    chat = model.start_chat(history=[])
                    response = chat.send_message(prompt)
                    
                    # Save State
                    st.session_state.chat_session = chat
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                    st.session_state.interview_active = True
                    st.rerun()

# --- MAIN AREA ---

# If NO interview active, show instructions
if not st.session_state.interview_active:
    st.info("👈 Please upload your Resume (PDF) in the sidebar to begin.")
    st.write("The AI needs to read your resume to ask specific questions.")

# If interview IS active, show the Chat
else:
    # Display Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Chat Input (Only appears when interview is active)
    user_input = st.chat_input("Type your answer here...")

    if user_input:
        # Show User Message
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        # Get AI Response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                chat = st.session_state.chat_session
                response = chat.send_message(user_input)
                st.write(response.text)
                
                # Play Audio
                audio_bytes = get_elevenlabs_audio(response.text)
                if audio_bytes:
                    st.audio(audio_bytes, format="audio/mp3", autoplay=True)
                
        # Save AI Message
        st.session_state.messages.append({"role": "assistant", "content": response.text})
   
   

