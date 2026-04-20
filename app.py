import streamlit as st
import pdfplumber
import re
import time
from PIL import Image
import pytesseract
import pandas as pd # Added for the analytics table

# ---------- SESSION INITIALIZATION ----------
def init_session():
    defaults = {
        "questions": [],
        "current_q": 0,
        "answers": {},
        "question_times": {}, # Track time spent per Q
        "start_time": None,
        "time_per_q": 30,
        "finished": False,
        "lang": "EN",
        "revealed": False
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()

# ---------- UI CSS (UNTOUCHED) ----------
def inject_custom_ui():
    st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background-color: #f0f2f6; }
    .q-card {
        background: white;
        padding: 25px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        margin-bottom: 25px;
        border-left: 5px solid #4B90FF;
    }
    .feedback-banner {
        padding: 12px;
        border-radius: 8px;
        text-align: center;
        margin-bottom: 15px;
        font-weight: bold;
        animation: slideDown 0.4s ease-out;
    }
    @keyframes slideDown {
        from { transform: translateY(-20px); opacity: 0; }
        to { transform: translateY(0); opacity: 1; }
    }
    .timer-box { font-size: 1.5rem; font-weight: 800; }
    .timer-low { color: #ff4b4b; animation: pulse 1s infinite; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    .stButton > button { border-radius: 8px; transition: all 0.2s; }
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
    st.markdown(f"""
    <script>
    var audio = new Audio("{urls[sound_type]}");
    audio.play();
    </script>
    """, unsafe_allow_html=True)

# ---------- EXTRACTION ENGINES ----------
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
    text = re.sub(r"\n+", "\n", text.replace("\r", ""))
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
        questions.append({
            "en": q_lines[0],
            "hi": q_lines[1] if len(q_lines)>1 else q_lines[0],
            "options": opt_dict,
            "answer": "A" # Note: Replace with actual parsing logic if answer keys exist
        })
        qn += 1
    return questions

# ---------- MAIN APP FLOW ----------
if not st.session_state.questions:
    st.title("🚀 Pro CBT Center")
    with st.container(border=True):
        st.session_state.time_per_q = st.slider("Set Timer (Seconds)", 5, 120, 30)
        file = st.file_uploader("Upload Exam PDF", type=["pdf"])
        if file:
            with st.spinner("Processing..."):
                st.session_state.questions = parse_mcqs(extract_text(file))
            st.rerun()

elif st.session_state.finished:
    # Play finish sound only once
    if "played_finish" not in st.session_state:
        play_sound("finish")
        st.session_state.played_finish = True

    st.title("📊 Performance Analytics")
    total = len(st.session_state.questions)
    
    # Calculate Score
    results = []
    correct_count = 0
    for i, q in enumerate(st.session_state.questions):
        u_ans = st.session_state.answers.get(i)
        is_correct = (u_ans == q["answer"])
        if is_correct: correct_count += 1
        
        results.append({
            "Q": i + 1,
            "Status": "✅ Correct" if is_correct else ("🕒 Timeout" if u_ans == "Timed Out" else "❌ Wrong"),
            "Time Spent": f"{st.session_state.question_times.get(i, 0):.1f}s"
        })

    # Top Metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Score", f"{correct_count} / {total}")
    m2.metric("Accuracy", f"{(correct_count/total)*100:.1f}%")
    avg_time = sum(st.session_state.question_times.values()) / total if total > 0 else 0
    m3.metric("Avg Speed", f"{avg_time:.1f}s / Q")

    # Analytics Table
    st.divider()
    st.subheader("Question Breakdown")
    st.table(pd.DataFrame(results))

    if st.button("Restart New Test"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

else:
    # 1. NAVIGATION PALETTE
    st.sidebar.title("📋 Navigation")
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

    # Timer UI
    t_col1, t_col2 = st.columns([5, 1])
    with t_col1:
        st.progress(max(0.0, min(1.0, rem / st.session_state.time_per_q)))
    with t_col2:
        t_class = "timer-low" if rem < 10 else ""
        st.markdown(f"<div class='timer-box {t_class}'>{max(0, rem)}s</div>", unsafe_allow_html=True)

    # 3. QUESTION DISPLAY
    curr_idx = st.session_state.current_q
    q = st.session_state.questions[curr_idx]

    st.markdown(f"""
    <div class="q-card">
        <small style="color:gray;">QUESTION {curr_idx + 1} OF {total_qs}</small>
        <h3 style="margin-top:10px;">{q['en'] if st.session_state.lang == 'EN' else q['hi']}</h3>
    </div>
    """, unsafe_allow_html=True)

    st.session_state.lang = st.radio("Lang", ["EN", "HI"], horizontal=True, label_visibility="collapsed")

    # 4. FEEDBACK BANNER
    if st.session_state.revealed:
        user_ans = st.session_state.answers.get(curr_idx)
        if user_ans == q["answer"]:
            st.markdown('<div class="feedback-banner" style="background:#d4edda; color:#155724;">✅ Correct!</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="feedback-banner" style="background:#f8d7da; color:#721c24;">❌ Incorrect/Timeout. Answer: {q["answer"]}</div>', unsafe_allow_html=True)

    # 5. OPTIONS
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
                # Record time taken
                time_taken = time.time() - st.session_state.start_time
                st.session_state.question_times[curr_idx] = min(time_taken, st.session_state.time_per_q)
                
                # Check answer and play sound
                st.session_state.answers[curr_idx] = label
                if label == q["answer"]:
                    play_sound("correct")
                else:
                    play_sound("wrong")
                
                st.session_state.revealed = True
                st.rerun()

    # 6. AUTO-ADVANCE
    if st.session_state.revealed:
        time.sleep(2.5)
        if curr_idx < total_qs - 1:
            st.session_state.current_q += 1
            st.session_state.start_time = None
            st.session_state.revealed = False
            st.rerun()
        else:
            st.session_state.finished = True
            st.rerun()

    # Refresher for Timer
    time.sleep(1)
    st.rerun()
