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
        "played_finish": False,
        "last_sound": None # Track sound to avoid loops
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()

# ---------- REFINED CSS ----------
def inject_custom_ui():
    st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background-color: #f4f7f9; }
    .q-card {
        background: white;
        padding: 30px;
        border-radius: 16px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.05);
        margin-bottom: 20px;
        border-top: 6px solid #4B90FF;
    }
    .feedback-banner {
        padding: 15px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 20px;
        font-weight: 700;
        font-size: 1.1rem;
    }
    .timer-box { font-size: 1.6rem; font-weight: 900; font-family: monospace; }
    .timer-low { color: #ff4b4b; animation: pulse 0.8s infinite; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    </style>
    """, unsafe_allow_html=True)

inject_custom_ui()

# ---------- AUDIO ENGINE (FIXED) ----------
def play_sound(sound_type):
    urls = {
        "correct": "https://www.soundjay.com/misc/sounds/bell-ringing-05.wav",
        "wrong": "https://www.soundjay.com/buttons/sounds/button-10.wav",
        "timeout": "https://www.soundjay.com/button/beep-07.wav",
        "finish": "https://www.soundjay.com/misc/sounds/tada-fanfare-01.wav"
    }
    # Using unique key in components to force script execution
    sound_html = f"""
        <audio autoplay>
            <source src="{urls[sound_type]}" type="audio/wav">
        </audio>
    """
    st.components.v1.html(sound_html, height=0)

# ---------- EXTRACTION & PARSER (FIXED) ----------
def extract_text(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for p in pdf.pages:
            t = p.extract_text()
            if t: text += t + "\n"
            
    if len(text.strip()) < 100:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                im = page.to_image(resolution=300)
                text += pytesseract.image_to_string(im.original)
    return text

def parse_mcqs(text):
    questions = []
    # Improved answer key detection (looks for 'Answer Key' or 'Answers' section)
    answer_map = {}
    ans_section = re.split(r"(?i)Answer Key|Answers", text)
    ans_text = ans_section[-1] if len(ans_section) > 1 else text
    
    found_answers = re.findall(r"(\d+)\s*[\.\-\s:]\s*([A-D])\b", ans_text)
    for num, ans in found_answers:
        answer_map[int(num)] = ans.upper()

    # Improved Option Detection: Matches A. or A) or [A] or (A)
    blocks = re.split(r"\n(?=\d+[\.\s])", text)
    qn = 1
    for block in blocks:
        block = block.strip()
        if not re.match(rf"^{qn}[\.\s]", block): continue
        
        # Capture option letter and the text following it until the next option or end of line
        options = re.findall(r"(?i)\b([A-D])[\.\)\]\s]\s*([^\n]+?)(?=\s*[B-D][\.\)\]\s]|$)", block)
        opt_dict = {k.upper(): v.strip() for k, v in options}
        
        for op in ["A","B","C","D"]:
            if op not in opt_dict: opt_dict[op] = "Option not found"
        
        # Extract question text (before Option A)
        q_body = re.split(r"(?i)\bA[\.\)\]\s]", block)[0].strip()
        q_lines = q_body.split("\n")
        
        correct_ans = answer_map.get(qn, "A") # Fallback to A if still not found
        
        questions.append({
            "en": q_lines[0],
            "hi": q_lines[1] if len(q_lines)>1 else q_lines[0],
            "options": opt_dict,
            "answer": correct_ans 
        })
        qn += 1
    return questions

# ---------- MAIN APP FLOW ----------
if not st.session_state.questions:
    st.title("🚀 Ultimate CBT Portal")
    with st.container(border=True):
        st.session_state.time_per_q = st.slider("Seconds per question", 5, 120, 30)
        file = st.file_uploader("Select Exam PDF", type=["pdf"])
        if file:
            with st.status("Analyzing Test..."):
                st.session_state.questions = parse_mcqs(extract_text(file))
            st.rerun()

elif st.session_state.finished:
    if not st.session_state.played_finish:
        play_sound("finish")
        st.session_state.played_finish = True
    
    st.title("📊 Performance Review")
    # ... (Keep performance review logic same)
    total = len(st.session_state.questions)
    results = []
    correct_count = 0
    for i, q in enumerate(st.session_state.questions):
        u_ans = st.session_state.answers.get(i)
        is_correct = (u_ans == q["answer"])
        if is_correct: correct_count += 1
        results.append({
            "Question": i + 1, "Outcome": "✅ Correct" if is_correct else "❌ Wrong",
            "Correct Answer": q["answer"], "Speed": f"{st.session_state.question_times.get(i, 0):.1f}s"
        })
    st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
    if st.button("New Test Session"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

else:
    # 1. NAVIGATION PALETTE (Sidebar)
    st.sidebar.title("📋 Progress")
    total_qs = len(st.session_state.questions)
    # ... (Keep existing sidebar grid)

    # 2. TIMER LOGIC
    if st.session_state.start_time is None:
        st.session_state.start_time = time.time()
    
    elapsed = time.time() - st.session_state.start_time
    rem = int(st.session_state.time_per_q - elapsed)

    if rem <= 0 and not st.session_state.revealed:
        st.session_state.answers[st.session_state.current_q] = "Timed Out"
        st.session_state.revealed = True
        play_sound("timeout")
        st.rerun()

    t_col1, t_col2 = st.columns([5, 1])
    with t_col1: st.progress(max(0.0, min(1.0, rem / st.session_state.time_per_q)))
    with t_col2: st.markdown(f"<div class='timer-box'>{max(0, rem)}s</div>", unsafe_allow_html=True)

    # 3. QUESTION CARD
    curr_idx = st.session_state.current_q
    q = st.session_state.questions[curr_idx]

    st.markdown(f'<div class="q-card"><small>QUESTION {curr_idx + 1} OF {total_qs}</small><h3>{q["en"] if st.session_state.lang == "EN" else q["hi"]}</h3></div>', unsafe_allow_html=True)
    st.session_state.lang = st.radio("Lang", ["EN", "HI"], horizontal=True, label_visibility="collapsed")

    # 4. OPTIONS
    for label, text in q["options"].items():
        btn_type = "secondary"
        prefix = f"{label}."
        if st.session_state.revealed:
            if label == q["answer"]: btn_type, prefix = "primary", f"✅ {label}."
            elif label == st.session_state.answers.get(curr_idx): prefix = f"❌ {label}."

        if st.button(f"{prefix} {text}", key=f"q{curr_idx}_{label}", use_container_width=True, type=btn_type):
            if not st.session_state.revealed:
                st.session_state.answers[curr_idx] = label
                st.session_state.question_times[curr_idx] = time.time() - st.session_state.start_time
                st.session_state.revealed = True
                play_sound("correct" if label == q["answer"] else "wrong")
                st.rerun()

    # 5. NAVIGATION TOGGLE (FIX 3: Added Previous/Next)
    st.divider()
    nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
    with nav_col1:
        if st.button("⬅️ Previous") and curr_idx > 0:
            st.session_state.current_q -= 1
            st.session_state.revealed = False
            st.session_state.start_time = None
            st.rerun()
    with nav_col3:
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

    # Remove the infinite loop st.rerun() from the bottom to allow interaction
