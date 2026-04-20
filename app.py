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

# ---------- REFINED CSS (SMOOTHER UI) ----------
def inject_custom_ui():
    st.markdown("""
    <style>
    /* Professional Grey Background */
    [data-testid="stAppViewContainer"] { background-color: #f4f7f9; }
    
    /* Elegant Question Card */
    .q-card {
        background: white;
        padding: 30px;
        border-radius: 16px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.05);
        margin-bottom: 20px;
        border-top: 6px solid #4B90FF;
        transition: all 0.3s ease;
    }
    
    /* Feedback Banner with Slide-in */
    .feedback-banner {
        padding: 15px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 20px;
        font-weight: 700;
        font-size: 1.1rem;
        animation: slideDown 0.5s cubic-bezier(0.18, 0.89, 0.32, 1.28);
    }
    
    @keyframes slideDown {
        from { transform: translateY(-30px); opacity: 0; }
        to { transform: translateY(0); opacity: 1; }
    }

    /* Pulsing Timer for Urgency */
    .timer-box { font-size: 1.6rem; font-weight: 900; font-family: monospace; }
    .timer-low { color: #ff4b4b; animation: pulse 0.8s infinite; }
    @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.05); } 100% { transform: scale(1); } }

    /* Button Polish */
    .stButton > button {
        border-radius: 10px;
        font-weight: 500;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)

inject_custom_ui()

# ---------- AUDIO ENGINE ----------
def play_sound(sound_type):
    urls = {
        "correct": "https://www.soundjay.com/misc/sounds/bell-ringing-05.wav",
        "wrong": "https://www.soundjay.com/buttons/sounds/button-10.wav",
        "timeout": "https://www.soundjay.com/button/beep-07.wav",
        "finish": "https://www.soundjay.com/misc/sounds/tada-fanfare-01.wav"
    }
    st.markdown(f'<script>new Audio("{urls[sound_type]}").play();</script>', unsafe_allow_html=True)

# ---------- EXTRACTION & PARSER ----------
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
                [span_5](start_span)text += pytesseract.image_to_string(im.original)[span_5](end_span)
    return text

def parse_mcqs(text):
    questions = []
    text = re.sub(r"\n+", "\n", text.replace("\r", ""))
    
    # Smarter Answer Key Detection
    answer_map = {}
    found_answers = re.findall(r"(\d+)\s*[\.\-\s]\s*[\(\[]?([A-D])[\)\]]?", text)
    for num, ans in found_answers:
        answer_map[int(num)] = ans.upper()

    blocks = re.split(r"\n(?=\d+\.\s)", text)
    qn = 1
    for block in blocks:
        block = block.strip()
        if not block.startswith(str(qn)): continue
        
        options = re.findall(r"\[([A-D])\]\s*([^\[]+)", block)
        opt_dict = {k: v.strip() for k, v in options}
        for op in ["A","B","C","D"]:
            if op not in opt_dict: opt_dict[op] = "N/A"
        
        q_lines = block.split("[A]")[0].strip().split("\n")
        correct_ans = answer_map.get(qn, "A") # Fallback to A if not found
        
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
        [span_6](start_span)file = st.file_uploader("Select Exam PDF", type=["pdf"])[span_6](end_span)
        if file:
            with st.status("Analyzing Test Structure..."):
                st.session_state.questions = parse_mcqs(extract_text(file))
            st.rerun()

elif st.session_state.finished:
    if not st.session_state.played_finish:
        play_sound("finish")
        st.session_state.played_finish = True

    st.title("📊 Performance Review")
    total = len(st.session_state.questions)
    
    results = []
    correct_count = 0
    for i, q in enumerate(st.session_state.questions):
        u_ans = st.session_state.answers.get(i)
        is_correct = (u_ans == q["answer"])
        if is_correct: correct_count += 1
        results.append({
            "Question": i + 1,
            "Outcome": "✅ Correct" if is_correct else ("🕒 Timeout" if u_ans == "Timed Out" else "❌ Wrong"),
            "Your Answer": u_ans,
            "Actual": q["answer"],
            "Speed": f"{st.session_state.question_times.get(i, 0):.1f}s"
        })

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Score", f"{correct_count} / {total}")
    col2.metric("Accuracy", f"{(correct_count/total)*100:.1f}%")
    avg_t = sum(st.session_state.question_times.values())/total if total > 0 else 0
    col3.metric("Avg Speed", f"{avg_t:.1f}s")

    st.divider()
    st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)

    if st.button("New Test Session", type="primary"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

else:
    # 1. NAVIGATION PALETTE (Smooth Grid)
    st.sidebar.title("📋 Progress")
    total_qs = len(st.session_state.questions)
    for row in range((total_qs // 4) + 1):
        cols = st.sidebar.columns(4)
        for c in range(4):
            idx = row * 4 + c
            if idx < total_qs:
                icon = "🔵" if idx == st.session_state.current_q else ("🟩" if idx in st.session_state.answers else "⬜")
                if cols[c].button(f"{icon}\n{idx+1}", key=f"nav_{idx}"):
                    st.session_state.current_q = idx
                    st.session_state.start_time = None
                    st.session_state.revealed = False
                    st.rerun()

    # 2. TIMER LOGIC
    if st.session_state.start_time is None:
        st.session_state.start_time = time.time()
    
    elapsed = time.time() - st.session_state.start_time
    rem = int(st.session_state.time_per_q - elapsed)

    if rem <= 0 and not st.session_state.revealed:
        play_sound("timeout")
        st.session_state.question_times[st.session_state.current_q] = st.session_state.time_per_q
        st.session_state.answers[st.session_state.current_q] = "Timed Out"
        st.session_state.revealed = True
        st.rerun()

    t_col1, t_col2 = st.columns([5, 1])
    with t_col1:
        st.progress(max(0.0, min(1.0, rem / st.session_state.time_per_q)))
    with t_col2:
        t_class = "timer-low" if rem < 10 else ""
        st.markdown(f"<div class='timer-box {t_class}'>{max(0, rem)}s</div>", unsafe_allow_html=True)

    # 3. QUESTION CARD
    curr_idx = st.session_state.current_q
    q = st.session_state.questions[curr_idx]

    st.markdown(f"""
    <div class="q-card">
        <small style="color:#4B90FF; font-weight:700;">QUESTION {curr_idx + 1} OF {total_qs}</small>
        <h3 style="margin-top:10px; color:#1f2937;">{q['en'] if st.session_state.lang == 'EN' else q['hi']}</h3>
    </div>
    """, unsafe_allow_html=True)

    st.session_state.lang = st.radio("Language Select", ["EN", "HI"], horizontal=True, label_visibility="collapsed")

    # 4. FEEDBACK (ONLY ON REVEAL)
    if st.session_state.revealed:
        user_ans = st.session_state.answers.get(curr_idx)
        if user_ans == q["answer"]:
            st.markdown('<div class="feedback-banner" style="background:#d1fae5; color:#065f46; border: 1px solid #10b981;">✨ Excellent! Correct Answer.</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="feedback-banner" style="background:#fee2e2; color:#991b1b; border: 1px solid #ef4444;">❌ Incorrect. Right answer is {q["answer"]}.</div>', unsafe_allow_html=True)

    # 5. OPTIONS (UNIQUE KEYS PREVENT GHOSTING)
    for label, text in q["options"].items():
        btn_type = "secondary"
        prefix = f"{label}."
        
        if st.session_state.revealed:
            if label == q["answer"]:
                btn_type = "primary"
                prefix = f"✅ {label}."
            elif label == st.session_state.answers.get(curr_idx):
                prefix = f"❌ {label}."

        if st.button(f"{prefix} {text}", key=f"q{curr_idx}_opt_{label}", use_container_width=True, type=btn_type):
            if not st.session_state.revealed:
                time_taken = time.time() - st.session_state.start_time
                st.session_state.question_times[curr_idx] = min(time_taken, st.session_state.time_per_q)
                st.session_state.answers[curr_idx] = label
                play_sound("correct" if label == q["answer"] else "wrong")
                st.session_state.revealed = True
                st.rerun()

    # 6. AUTO-ADVANCE DELAY
    if st.session_state.revealed:
        time.sleep(2.2) # Adjusted for slightly faster smoothness
        if curr_idx < total_qs - 1:
            st.session_state.current_q += 1
            st.session_state.start_time = None
            st.session_state.revealed = False
            st.rerun()
        else:
            st.session_state.finished = True
            st.rerun()

    # Smooth clock refresh
    time.sleep(1)
    st.rerun()
