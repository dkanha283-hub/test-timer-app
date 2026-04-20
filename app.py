import streamlit as st
import pdfplumber
import re
import time
import io
from PIL import Image

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
        "pdf_bytes": None,
        "played_finish": False
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()

# ---------- UI & CSS ----------
def inject_ui():
    st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background-color: #f0f2f6; }
    .q-card {
        background: white;
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        margin-bottom: 20px;
        border-top: 5px solid #4B90FF;
    }
    .timer-box { 
        font-size: 2.2rem; font-weight: 800; font-family: monospace; 
        text-align: right; color: #1e293b;
    }
    .timer-low { color: #ff4b4b; animation: blinker 1s linear infinite; }
    @keyframes blinker { 50% { opacity: 0; } }
    
    /* Sidebar Grid Styling */
    .stButton > button { width: 100%; border-radius: 8px; margin-bottom: 5px; }
    </style>
    """, unsafe_allow_html=True)

inject_ui()

# ---------- AUDIO ENGINE ----------
def play_sound(sound_type):
    urls = {
        "correct": "https://www.soundjay.com/misc/sounds/bell-ringing-05.wav",
        "wrong": "https://www.soundjay.com/buttons/sounds/button-10.wav",
        "timeout": "https://www.soundjay.com/button/beep-07.wav",
        "finish": "https://www.soundjay.com/misc/sounds/tada-fanfare-01.wav"
    }
    # Unique key ensures the HTML component re-renders and plays every time
    sound_id = f"sound_{int(time.time()*1000)}"
    st.components.v1.html(f"""
        <audio autoplay id="{sound_id}">
            <source src="{urls[sound_type]}" type="audio/wav">
        </audio>
    """, height=0)

# ---------- PARSER WITH VISUAL FALLBACK ----------
def parse_pdf(file_bytes):
    questions = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for p_idx, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            # Split into question blocks starting with a digit and dot (e.g. 1.)
            blocks = re.split(r"\n(?=\d+[\.\s])", text)
            
            for block in blocks:
                # 1. Extract Question Text
                q_match = re.search(r"^\d+[\.\s]+(.*?)(?=\s*[A-D][\.\)])", block, re.S)
                if not q_match: continue
                full_q = q_match.group(1).strip()
                
                # Split English/Hindi (Assuming they are separated by newline or '?')
                q_parts = full_q.split('\n')
                en_text = q_parts[0]
                hi_text = q_parts[1] if len(q_parts) > 1 else en_text
                
                # 2. Extract Options
                opts = {}
                for char in ['A', 'B', 'C', 'D']:
                    # Look for option text
                    opt_pattern = rf"{char}[\.\)]\s*(.*?)(?=\s*[B-D][\.\)]|$)"
                    opt_match = re.search(opt_pattern, block, re.S)
                    
                    if opt_match and len(opt_match.group(1).strip()) > 0:
                        opts[char] = {"text": opt_match.group(1).strip(), "image": None}
                    else:
                        # VISUAL FALLBACK: If text is missing, grab a crop of the line
                        # We use a heuristic: crop the area where the option should be
                        try:
                            # Search for the character location on the page to crop
                            char_objs = [char_obj for char_obj in page.chars if char_obj['text'] == char]
                            if char_objs:
                                target = char_objs[-1] # Get the last occurrence in this block
                                bbox = (0, target['top'] - 5, page.width, target['bottom'] + 15)
                                img = page.within_bbox(bbox).to_image(resolution=150).original
                                opts[char] = {"text": None, "image": img}
                            else:
                                opts[char] = {"text": "Check original PDF", "image": None}
                        except:
                            opts[char] = {"text": "Check original PDF", "image": None}

                questions.append({
                    "en": en_text, "hi": hi_text,
                    "options": opts,
                    "answer": "A", # Default Answer Key (Manual mapping recommended here)
                    "page": p_idx
                })
    return questions

# ---------- MAIN APP LOGIC ----------
if not st.session_state.questions:
    st.title("🎯 Advanced CBT Portal")
    file = st.file_uploader("Upload PDF Exam File", type=["pdf"])
    if file:
        st.session_state.pdf_bytes = file.read()
        with st.status("Parsing Questions & Visuals..."):
            st.session_state.questions = parse_pdf(st.session_state.pdf_bytes)
        st.rerun()

elif st.session_state.finished:
    st.title("📊 Test Results")
    if not st.session_state.played_finish:
        play_sound("finish")
        st.session_state.played_finish = True
    
    # Simple score calculation
    score = sum(1 for i, q in enumerate(st.session_state.questions) if st.session_state.answers.get(i) == q['answer'])
    st.metric("Total Score", f"{score} / {len(st.session_state.questions)}")
    
    if st.button("Start New Test"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

else:
    # 1. SIDEBAR GRID (SSC STYLE)
    st.sidebar.title("📑 Question Palette")
    total_qs = len(st.session_state.questions)
    for i in range(0, total_qs, 4):
        cols = st.sidebar.columns(4)
        for j in range(4):
            idx = i + j
            if idx < total_qs:
                # Color coding: Blue (current), Green (answered), White (pending)
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

    # 2. TOP BAR (Language + Timer)
    top_col1, top_col2 = st.columns([3, 1])
    with top_col1:
        st.session_state.lang = st.radio("Language", ["EN", "HI"], horizontal=True, label_visibility="collapsed")
    
    # Timer Engine
    if st.session_state.start_time is None:
        st.session_state.start_time = time.time()
    
    elapsed = time.time() - st.session_state.start_time
    rem = max(0, int(st.session_state.time_per_q - elapsed))
    
    with top_col2:
        t_class = "timer-low" if rem < 10 else ""
        st.markdown(f"<div class='timer-box {t_class}'>{rem}s</div>", unsafe_allow_html=True)

    # Handle Timeout
    if rem <= 0 and not st.session_state.revealed:
        st.session_state.answers[st.session_state.current_q] = "Timed Out"
        st.session_state.revealed = True
        play_sound("timeout")
        st.rerun()

    # 3. QUESTION CARD
    curr_idx = st.session_state.current_q
    q = st.session_state.questions[curr_idx]

    st.markdown(f"""
    <div class="q-card">
        <small style="color:#4B90FF;">QUESTION {curr_idx + 1}</small>
        <h3>{q['en'] if st.session_state.lang == 'EN' else q['hi']}</h3>
    </div>
    """, unsafe_allow_html=True)

    # 4. OPTIONS (WITH VISUAL FALLBACK)
    for label in ["A", "B", "C", "D"]:
        opt_data = q["options"][label]
        btn_type = "secondary"
        
        if st.session_state.revealed:
            if label == q["answer"]:
                btn_type = "primary"
            elif label == st.session_state.answers.get(curr_idx):
                btn_type = "secondary"

        # Show text or "View Image" indicator
        btn_text = f"{label}. {opt_data['text']}" if opt_data['text'] else f"{label}. [View Visual Below]"
        
        if st.button(btn_text, key=f"btn_{curr_idx}_{label}", use_container_width=True, type=btn_type):
            if not st.session_state.revealed:
                st.session_state.answers[curr_idx] = label
                st.session_state.revealed = True
                play_sound("correct" if label == q["answer"] else "wrong")
                st.rerun()
        
        # Display cropped image if text was missing
        if opt_data['image'] and not st.session_state.revealed:
            st.image(opt_data['image'], caption=f"Option {label} Original View", width=400)

    # 5. NAVIGATION TOGGLE
    st.divider()
    nav_col1, nav_col2, nav_col3 = st.columns([1, 1, 1])
    with nav_col1:
        if st.button("⬅️ Previous", use_container_width=True) and curr_idx > 0:
            st.session_state.current_q -= 1
            st.session_state.revealed = False
            st.session_state.start_time = None
            st.rerun()
    with nav_col3:
        next_label = "Next ➡️" if curr_idx < total_qs - 1 else "Finish 🏁"
        if st.button(next_label, use_container_width=True):
            if curr_idx < total_qs - 1:
                st.session_state.current_q += 1
                st.session_state.revealed = False
                st.session_state.start_time = None
            else:
                st.session_state.finished = True
            st.rerun()

    # 6. AUTO-ADVANCE AFTER SELECTION
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

    # Force UI refresh for timer
    time.sleep(0.5)
    st.rerun()
