import streamlit as st
import pdfplumber
import re
import time
from PIL import Image
import pytesseract

# ---------- SESSION INITIALIZATION ----------
def init_session():
    defaults = {
        "questions": [],
        "current_q": 0,
        "answers": {},
        "start_time": None,
        "time_per_q": 30,
        "finished": False,
        "lang": "EN"
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()

# ---------- CUSTOM CSS (The "Magic" for UI/Animations) ----------
def inject_custom_css():
    st.markdown("""
    <style>
    /* Main Background and Font */
    [data-testid="stAppViewContainer"] {
        background-color: #f8f9fa;
    }
    
    /* Card Style for Question */
    .q-card {
        background: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        margin-bottom: 20px;
        animation: fadeIn 0.5s ease-in-out;
    }
    
    /* Animations */
    @keyframes fadeIn {
        0% { opacity: 0; transform: translateY(10px); }
        100% { opacity: 1; transform: translateY(0); }
    }
    
    @keyframes pulse {
        0% { transform: scale(1); color: #ff4b4b; }
        50% { transform: scale(1.1); color: #b91c1c; }
        100% { transform: scale(1); color: #ff4b4b; }
    }
    
    .timer-critical {
        animation: pulse 1s infinite;
        font-weight: bold;
    }

    /* Professional Grid Palette */
    .sidebar-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 8px;
        padding: 10px;
    }
    
    /* Button Hover Smoothing */
    div.stButton > button {
        transition: all 0.2s ease-in-out;
        border-radius: 8px;
    }
    
    div.stButton > button:hover {
        transform: scale(1.02);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# ---------- OCR & PARSER (Retained from previous) ----------
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
            if op not in opt_dict: opt_dict[op] = "Missing"
        q_text = block.split("[A]")[0].strip().split("\n")
        questions.append({
            "en": q_text[0], "hi": q_text[1] if len(q_text)>1 else q_text[0],
            "A": opt_dict["A"], "B": opt_dict["B"], "C": opt_dict["C"], "D": opt_dict["D"],
            "answer": "A" # Placeholder logic
        })
        qn += 1
    return questions

def alert():
    st.markdown('<script>new Audio("https://www.soundjay.com/button/beep-07.wav").play();</script>', unsafe_allow_html=True)

# ---------- APPLICATION FLOW ----------
if not st.session_state.questions:
    st.title("🧪 CBT Exam Portal")
    st.markdown("### Prepare for your test with custom timers and smart tracking.")
    
    with st.expander("⚙️ Test Settings", expanded=True):
        st.session_state.time_per_q = st.slider("Time per question (seconds)", 5, 120, 30)
    
    file = st.file_uploader("Drop your PDF here", type=["pdf"])
    if file:
        with st.status("Reading Exam File..."):
            text = extract_text(file)
            st.session_state.questions = parse_mcqs(text)
        st.rerun()

elif st.session_state.finished:
    st.balloons()
    st.title("📊 Performance Dashboard")
    # (Results summary metrics code...)
    if st.button("Re-take Test"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

else:
    # 1. LIVE TIMER (TOP)
    if st.session_state.start_time is None:
        st.session_state.start_time = time.time()

    elapsed = time.time() - st.session_state.start_time
    rem = int(st.session_state.time_per_q - elapsed)

    if rem <= 0:
        alert()
        st.session_state.answers[st.session_state.current_q] = "None"
        if st.session_state.current_q < len(st.session_state.questions) - 1:
            st.session_state.current_q += 1
            st.session_state.start_time = None
            st.rerun()
        else:
            st.session_state.finished = True
            st.rerun()

    # Timer Display with Animation Class
    t_class = "timer-critical" if rem < 10 else ""
    col1, col2 = st.columns([5, 1])
    with col1:
        st.progress(max(0.0, rem / st.session_state.time_per_q))
    with col2:
        st.markdown(f"<h3 class='{t_class}' style='margin-top:-10px;'>{rem}s</h3>", unsafe_allow_html=True)

    # 2. SIDEBAR PALETTE
    st.sidebar.title("🎯 Exam Map")
    st.sidebar.markdown("---")
    
    total = len(st.session_state.questions)
    grid = st.sidebar.container()
    
    # Render Palette buttons in a clean layout
    # Streamlit doesn't support custom HTML button clicks easily, 
    # so we use native columns but style the container
    with grid:
        # We loop through columns to create the grid effect
        for row in range((total // 4) + 1):
            cols = st.columns(4)
            for col_idx in range(4):
                q_idx = row * 4 + col_idx
                if q_idx < total:
                    # Logic for emoji indicators
                    label = f"{q_idx + 1}"
                    if q_idx == st.session_state.current_q: icon = "🔵"
                    elif q_idx in st.session_state.answers: icon = "🟩"
                    else: icon = "⬜"
                    
                    if cols[col_idx].button(f"{icon}\n{label}", key=f"nav_{q_idx}"):
                        st.session_state.current_q = q_idx
                        st.session_state.start_time = None
                        st.rerun()

    # 3. QUESTION CARD
    i = st.session_state.current_q
    q = st.session_state.questions[i]

    st.markdown(f"""
    <div class="q-card">
        <p style="color: #6c757d; font-weight: bold;">QUESTION {i+1} OF {total}</p>
        <hr>
        <h3>{'English' if st.session_state.lang == 'EN' else 'Hindi'}</h3>
    </div>
    """, unsafe_allow_html=True)
    
    st.session_state.lang = st.radio("Switch Language", ["EN", "HI"], horizontal=True, label_visibility="collapsed")
    
    q_txt = q["en"] if st.session_state.lang == "EN" else q["hi"]
    st.markdown(f"### {q_txt}")

    # 4. OPTIONS (STYLISH)
    st.write("")
    for op in ["A", "B", "C", "D"]:
        selected = st.session_state.answers.get(i) == op
        if st.button(f"**{op}** : {q[op]}", key=f"btn_{i}_{op}", 
                     use_container_width=True, 
                     type="primary" if selected else "secondary"):
            st.session_state.answers[i] = op
            # Smoothly move to next
            if i < total - 1:
                st.session_state.current_q += 1
                st.session_state.start_time = None
            else:
                st.session_state.finished = True
            st.rerun()

    # 5. FOOTER NAVIGATION
    st.divider()
    f1, f2, f3 = st.columns([1,2,1])
    if i > 0:
        if f1.button("⬅️ Previous", use_container_width=True):
            st.session_state.current_q -= 1
            st.session_state.start_time = None
            st.rerun()
    if i < total - 1:
        if f3.button("Next ➡️", use_container_width=True):
            st.session_state.current_q += 1
            st.session_state.start_time = None
            st.rerun()
    else:
        if f3.button("Submit 🏁", type="primary", use_container_width=True):
            st.session_state.finished = True
            st.rerun()

    # 6. REFRESH LOOP
    time.sleep(1)
    st.rerun()
