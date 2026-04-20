# [span_1](start_span)requirements.txt needs: streamlit, pdfplumber, pytesseract, Pillow[span_1](end_span)
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
        "lang": "EN",
        "revealed": False # New: Tracks if answer colors are shown
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()

# ---------- CUSTOM CSS (With Color Logic) ----------
def inject_custom_css():
    st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background-color: #f8f9fa; }
    
    /* Animation for the feedback banner */
    .feedback-box {
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 20px;
        animation: fadeIn 0.3s ease-in;
        font-weight: bold;
        font-size: 1.2rem;
    }
    
    @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

    /* Custom Button Colors for Feedback */
    /* We use data-testid to target buttons precisely if needed, 
       but for this version, we will use Streamlit's native 'type' and icons */
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# ---------- OCR & PARSER (Retained) ----------
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
        
        # Simple extraction of English/Hindi lines
        q_text_area = block.split("[A]")[0].strip().split("\n")
        
        questions.append({
            "en": q_text_area[0],
            "hi": q_text_area[1] if len(q_text_area)>1 else q_text_area[0],
            "options": opt_dict,
            "answer": "A" # Note: In a real app, parse the answer key from the PDF footer
        })
        qn += 1
    return questions

# ---------- APP FLOW ----------
if not st.session_state.questions:
    st.title("🧪 Smart CBT Prep")
    st.session_state.time_per_q = st.slider("Time per question", 5, 120, 30)
    file = st.file_uploader("Upload PDF Exam", type=["pdf"])
    if file:
        with st.status("Parsing Exam..."):
            st.session_state.questions = parse_mcqs(extract_text(file))
        st.rerun()

elif st.session_state.finished:
    st.title("📊 Test Summary")
    score = sum(1 for i, q in enumerate(st.session_state.questions) if st.session_state.answers.get(i) == q["answer"])
    st.metric("Final Score", f"{score}/{len(st.session_state.questions)}")
    if st.button("Restart"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

else:
    # 1. TIMER & AUTO-REVEAL
    if st.session_state.start_time is None:
        st.session_state.start_time = time.time()

    elapsed = time.time() - st.session_state.start_time
    rem = int(st.session_state.time_per_q - elapsed)

    if rem <= 0 and not st.session_state.revealed:
        st.session_state.revealed = True
        st.rerun()

    # 2. TOP UI
    c1, c2 = st.columns([5, 1])
    with c1: st.progress(max(0.0, rem / st.session_state.time_per_q))
    with c2: st.markdown(f"### {'⌛' if rem > 5 else '⚠️'} {rem}s")

    # 3. QUESTION
    idx = st.session_state.current_q
    q = st.session_state.questions[idx]
    
    st.sidebar.title("Exam Map")
    # Palette logic
    cols = st.sidebar.columns(4)
    for i in range(len(st.session_state.questions)):
        icon = "🔵" if i == idx else ("🟩" if i in st.session_state.answers else "⬜")
        if cols[i%4].button(f"{icon}{i+1}", key=f"p_{i}"):
            st.session_state.current_q = i
            st.session_state.start_time = None
            st.session_state.revealed = False
            st.rerun()

    st.markdown(f"**Question {idx+1} of {len(st.session_state.questions)}**")
    lang = st.radio("Lang", ["EN", "HI"], horizontal=True, label_visibility="collapsed")
    st.markdown(f"### {q['en'] if lang == 'EN' else q['hi']}")

    # 4. INSTANT FEEDBACK UI
    if st.session_state.revealed:
        user_choice = st.session_state.answers.get(idx)
        if user_choice == q["answer"]:
            st.markdown('<div class="feedback-box" style="background:#d4edda; color:#155724;">🌟 Correct! Well done.</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="feedback-box" style="background:#f8d7da; color:#721c24;">❌ Incorrect. The right answer was {q["answer"]}.</div>', unsafe_allow_html=True)

    # 5. OPTIONS
    for label, text in q["options"].items():
        btn_type = "secondary"
        prefix = ""
        
        if st.session_state.revealed:
            if label == q["answer"]:
                btn_type = "primary" # Highlight Green
                prefix = "✅ "
            else:
                btn_type = "secondary"
                prefix = "❌ "
        
        if st.button(f"{prefix} {label}. {text}", key=f"opt_{idx}_{label}", use_container_width=True, type=btn_type):
            if not st.session_state.revealed:
                st.session_state.answers[idx] = label
                st.session_state.revealed = True
                st.rerun()

    # 6. AUTO-ADVANCE LOGIC
    if st.session_state.revealed:
        time.sleep(2) # Give user 2 seconds to see the "picture" (colors)
        if idx < len(st.session_state.questions) - 1:
            st.session_state.current_q += 1
            st.session_state.start_time = None
            st.session_state.revealed = False
        else:
            st.session_state.finished = True
        st.rerun()

    time.sleep(1)
    st.rerun()
