import streamlit as st
import pdfplumber
import re
import time
from PIL import Image
import pytesseract
import pandas as pd

# ---------- SESSION INITIALIZATION ----------
def init_session():
    defaults = {
        "questions": [],
        "current_q": 0,
        "answers": {},
        "question_times": {},
        "start_time": None,
        "time_per_q": 30,
        "finished": False,
        "lang": "EN",
        "revealed": False,
        "played_finish": False
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()

# ---------- UI STYLING ----------
def inject_custom_ui():
    st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background-color: #f4f7f9; }
    .q-card {
        background: white;
        padding: 25px;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        margin-bottom: 20px;
        border-left: 5px solid #4B90FF;
    }
    .timer-box { font-size: 1.8rem; font-weight: 800; font-family: 'Courier New', monospace; text-align: center;}
    .timer-low { color: #ff4b4b; animation: pulse 1s infinite; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
    
    /* Sidebar Button Styling */
    .stButton > button { width: 100%; border-radius: 4px; padding: 5px; }
    </style>
    """, unsafe_allow_html=True)

inject_custom_ui()

def play_sound(sound_type):
    urls = {
        "correct": "https://www.soundjay.com/misc/sounds/bell-ringing-05.wav",
        "wrong": "https://www.soundjay.com/buttons/sounds/button-10.wav",
        "timeout": "https://www.soundjay.com/button/beep-07.wav",
        "finish": "https://www.soundjay.com/misc/sounds/tada-fanfare-01.wav"
    }
    sound_html = f'<audio autoplay><source src="{urls[sound_type]}" type="audio/wav"></audio>'
    st.components.v1.html(sound_html, height=0)

# ---------- PARSER (FIXED ISSUE 2) ----------
def extract_text(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for p in pdf.pages:
            t = p.extract_text()
            if t: text += t + "\n"
    return text

def parse_mcqs(text):
    questions = []
    # Clean text
    text = re.sub(r'\s+', ' ', text)
    
    # Locate Answer Key
    answer_map = {}
    ans_match = re.findall(r"(\d+)\s*[\.\-\)]\s*([A-D])\b", text)
    for num, ans in ans_match:
        answer_map[int(num)] = ans.upper()

    # Split by Question Number (e.g., 1. or 1 )
    q_blocks = re.split(r"(?=\d+[\.\s])", text)
    
    qn = 1
    for block in q_blocks:
        if not block.strip().startswith(str(qn)): continue
        
        # Robust Option Extraction (A, B, C, D in sequence)
        opt_dict = {}
        # Find positions of option markers
        pos = {}
        for char in ['A', 'B', 'C', 'D']:
            m = re.search(rf"[\(\[\s]{char}[\.\)\]\s]", block)
            if m: pos[char] = m.start()

        # Extract text between markers
        if 'A' in pos:
            q_text = block[:pos['A']].strip()
            # Try to get English/Hindi split if available
            q_parts = q_text.split('?') 
            en_q = q_parts[0] + '?' if len(q_parts) > 1 else q_text
            hi_q = q_parts[1] if len(q_parts) > 1 else en_q
            
            chars = sorted(pos.keys())
            for i in range(len(chars)):
                start = pos[chars[i]]
                end = pos[chars[i+1]] if i+1 < len(chars) else len(block)
                opt_raw = block[start:end].strip()
                # Clean marker from text (e.g., remove "A.")
                opt_text = re.sub(rf"^[\(\[\s]*{chars[i]}[\.\)\]\s]*", "", opt_raw).strip()
                opt_dict[chars[i]] = opt_text

            # Fill missing options
            for o in ["A","B","C","D"]:
                if o not in opt_dict: opt_dict[o] = "Option not detected"

            questions.append({
                "en": en_q, "hi": hi_q,
                "options": opt_dict,
                "answer": answer_map.get(qn, "A")
            })
            qn += 1
            
    return questions

# ---------- MAIN APP ----------
if not st.session_state.questions:
    st.title("🚀 Exam Portal")
    file = st.file_uploader("Upload Exam PDF", type=["pdf"])
    if file:
        with st.status("Parsing Exam..."):
            st.session_state.questions = parse_mcqs(extract_text(file))
        st.rerun()

elif st.session_state.finished:
    st.title("📊 Results")
    # Result UI (Omitted for brevity, keep your original)
    if st.button("Restart"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

else:
    # 1. SIDEBAR GRID (FIXED ISSUE 1)
    st.sidebar.markdown("### 📋 Question Palette")
    total_qs = len(st.session_state.questions)
    
    # Create a 4-column grid
    for i in range(0, total_qs, 4):
        cols = st.sidebar.columns(4)
        for j in range(4):
            idx = i + j
            if idx < total_qs:
                # Color logic: Current=Blue, Answered=Green, Empty=White
                if idx == st.session_state.current_q:
                    btn_label = f"🔵 {idx+1}"
                elif idx in st.session_state.answers:
                    btn_label = f"✅ {idx+1}"
                else:
                    btn_label = f"⚪ {idx+1}"
                
                if cols[j].button(btn_label, key=f"nav_{idx}"):
                    st.session_state.current_q = idx
                    st.session_state.revealed = False
                    st.session_state.start_time = None
                    st.rerun()

    # 2. TIMER LOGIC (FIXED ISSUE 3 & 4)
    if st.session_state.start_time is None:
        st.session_state.start_time = time.time()
    
    elapsed = time.time() - st.session_state.start_time
    rem = int(st.session_state.time_per_q - elapsed)

    # 3. HEADER & TIMER DISPLAY
    t_col1, t_col2 = st.columns([4, 1])
    with t_col2:
        t_class = "timer-low" if rem < 10 else ""
        st.markdown(f"<div class='timer-box {t_class}'>{max(0, rem)}s</div>", unsafe_allow_html=True)

    # Handle Timeout
    if rem <= 0 and not st.session_state.revealed:
        st.session_state.answers[st.session_state.current_q] = "Timed Out"
        st.session_state.revealed = True
        play_sound("timeout")
        st.rerun()

    # 4. QUESTION CARD
    curr_idx = st.session_state.current_q
    q = st.session_state.questions[curr_idx]

    st.markdown(f'<div class="q-card"><b>Q{curr_idx+1}</b><br>{q["en"]}</div>', unsafe_allow_html=True)
    
    # 5. OPTIONS
    for label in ["A", "B", "C", "D"]:
        text = q["options"][label]
        btn_type = "secondary"
        if st.session_state.revealed:
            if label == q["answer"]: btn_type = "primary"
        
        if st.button(f"{label}. {text}", key=f"opt_{label}_{curr_idx}", use_container_width=True, type=btn_type):
            if not st.session_state.revealed:
                st.session_state.answers[curr_idx] = label
                st.session_state.revealed = True
                play_sound("correct" if label == q["answer"] else "wrong")
                st.rerun()

    # 6. AUTO-ADVANCE & NAV (FIXED)
    st.divider()
    n_col1, n_col2, n_col3 = st.columns(3)
    
    with n_col1:
        if st.button("⬅️ Prev") and curr_idx > 0:
            st.session_state.current_q -= 1
            st.session_state.revealed = False
            st.session_state.start_time = None
            st.rerun()
            
    with n_col3:
        if curr_idx < total_qs - 1:
            if st.button("Next ➡️"):
                st.session_state.current_q += 1
                st.session_state.revealed = False
                st.session_state.start_time = None
                st.rerun()
        else:
            if st.button("Finish 🏁"):
                st.session_state.finished = True
                st.rerun()

    # AUTO JUMP after selection or timeout (2 second delay)
    if st.session_state.revealed:
        time.sleep(2)
        if curr_idx < total_qs - 1:
            st.session_state.current_q += 1
            st.session_state.revealed = False
            st.session_state.start_time = None
            st.rerun()
        else:
            st.session_state.finished = True
            st.rerun()

    # Keep timer ticking
    time.sleep(0.1)
    st.rerun()
