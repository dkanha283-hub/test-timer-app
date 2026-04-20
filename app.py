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
        "answers": {},  # Changed to dict for better tracking
        "start_time": None,
        "time_per_q": 30,
        "finished": False,
        "lang": "EN",
        "selected": None
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()

# -[span_2](start_span)[span_3](start_span)--------- OCR & TEXT EXTRACTION[span_2](end_span)[span_3](end_span) ----------
def extract_text_ocr(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            # Resolution 300 for better OCR accuracy
            im = page.to_image(resolution=300)
            img = im.original
            text += pytesseract.image_to_string(img)
    return text

def extract_text(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for p in pdf.pages:
            t = p.extract_text()
            if t:
                text += t + "\n"
    # [span_4](start_span)Fallback to OCR if text extraction yields little result[span_4](end_span)
    if len(text.strip()) < 100:
        text = extract_text_ocr(file)
    return text

# -[span_5](start_span)--------- SMART PARSER[span_5](end_span) ----------
def parse_mcqs(text):
    questions = []
    text = text.replace("\r", "")
    text = re.sub(r"\n+", "\n", text)

    # Extract answer key if present in format "1. (A)"
    answer_map = {}
    for num, ans in re.findall(r"(\d+)\.\s*\((\w)\)", text):
        answer_map[int(num)] = ans.upper()

    blocks = re.split(r"\n(?=\d+\.\s)", text)
    qn = 1

    for block in blocks:
        block = block.strip()
        if not block.startswith(str(qn)):
            continue

        # Clean broken option formatting
        for char in ["A", "B", "C", "D"]:
            block = block.replace(f"\n[{char}]", f" [{char}]")

        options = re.findall(r"\[([A-D])\]\s*([^\[]+)", block)
        opt_dict = {k: " ".join(v.split()) for k, v in options}
        
        # Fill missing options
        for op in ["A","B","C","D"]:
            if op not in opt_dict: opt_dict[op] = "Option missing"

        try:
            q_text = block.split("[A]")[0].strip()
        except:
            continue

        lines = q_text.split("\n")
        en = lines[0]
        hi = lines[1] if len(lines) > 1 else ""

        if len(en) < 5: continue

        questions.append({
            "question_en": en,
            "question_hi": hi,
            "A": opt_dict["A"],
            "B": opt_dict["B"],
            "C": opt_dict["C"],
            "D": opt_dict["D"],
            "answer": answer_map.get(qn, "A") # Default to A if no key found
        })
        qn += 1
    return questions

# ---------- ALERTS ----------
def alert():
    st.markdown("""
    <script>
    var audio = new Audio("https://www.soundjay.com/button/beep-07.wav");
    audio.play();
    if (navigator.vibrate) { navigator.vibrate(500); }
    </script>
    """, unsafe_allow_html=True)

# ---------- UI SETTINGS ----------
st.set_page_config(page_title="Ultimate CBT Pro", layout="wide")

# ---------- UPLOAD SCREEN ----------
if not st.session_state.questions:
    st.title("🧪 Ultimate CBT Test App")
    st.info("Upload a PDF to start. You can customize the timer per question below.")
    
    st.session_state.time_per_q = st.slider("Seconds per question", 5, 120, 30)
    
    file = st.file_uploader("Upload PDF", type=["pdf"])
    if file:
        with st.spinner("Processing PDF Content..."):
            text = extract_text(file)
            st.session_state.questions = parse_mcqs(text)
            st.rerun()

# ---------- RESULTS SCREEN ----------
elif st.session_state.finished:
    st.title("📊 Test Results")
    total = len(st.session_state.questions)
    score = sum(1 for i, q in enumerate(st.session_state.questions) 
                if st.session_state.answers.get(i) == q["answer"])
    
    st.success(f"Final Score: {score} / {total}")
    
    if st.button("Restart Test"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# ---------- MAIN TEST INTERFACE ----------
else:
    # 1. TIMER LOGIC (TOP OF PAGE)
    if st.session_state.start_time is None:
        st.session_state.start_time = time.time()

    elapsed = time.time() - st.session_state.start_time
    remaining = int(st.session_state.time_per_q - elapsed)

    # 2. AUTO-ADVANCE ON TIMEOUT
    if remaining <= 0:
        alert()
        st.session_state.answers[st.session_state.current_q] = "Timed Out"
        if st.session_state.current_q < len(st.session_state.questions) - 1:
            st.session_state.current_q += 1
            st.session_state.start_time = None
            st.rerun()
        else:
            st.session_state.finished = True
            st.rerun()

    # 3. TOP UI: TIMER & PROGRESS
    t_color = "green" if remaining > 10 else "red"
    
    col_t1, col_t2 = st.columns([5, 1])
    with col_t1:
        prog = max(0.0, min(1.0, remaining / st.session_state.time_per_q))
        st.progress(prog)
    with col_t2:
        st.markdown(f"### :{t_color}[{remaining}s]")

    # 4. SIDEBAR PALETTE
    st.sidebar.title("📊 Question Palette")
    total_qs = len(st.session_state.questions)
    grid_cols = st.sidebar.columns(4)
    
    for idx in range(total_qs):
        label = f"{idx+1}"
        style = "secondary"
        if idx == st.session_state.current_q: style = "primary"
        elif idx in st.session_state.answers: style = "success" # Custom style if supported, otherwise uses colors
        
        # Color coding buttons using status emojis
        status_emoji = "⚪"
        if idx in st.session_state.answers: status_emoji = "🟩"
        if idx == st.session_state.current_q: status_emoji = "🟦"

        if grid_cols[idx % 4].button(f"{status_emoji}{idx+1}", key=f"nav_{idx}"):
            st.session_state.current_q = idx
            st.session_state.start_time = None
            st.rerun()

    # 5. QUESTION DISPLAY
    i = st.session_state.current_q
    q = st.session_state.questions[i]
    
    st.divider()
    c1, c2 = st.columns([3, 1])
    with c1:
        st.subheader(f"Question {i+1}")
    with c2:
        st.session_state.lang = st.radio("Language", ["EN", "HI"], horizontal=True, label_visibility="collapsed")

    q_text = q["question_en"] if st.session_state.lang == "EN" else q["question_hi"]
    st.markdown(f"#### {q_text}")

    # 6. OPTIONS
    current_answer = st.session_state.answers.get(i)
    
    for op in ["A", "B", "C", "D"]:
        # Highlight selected option
        is_selected = (current_answer == op)
        if st.button(f"{op}. {q[op]}", key=f"opt_{i}_{op}", 
                     use_container_width=True, 
                     type="primary" if is_selected else "secondary"):
            st.session_state.answers[i] = op
            
            # Auto-move to next after selection
            if i < len(st.session_state.questions) - 1:
                st.session_state.current_q += 1
                st.session_state.start_time = None
            else:
                st.session_state.finished = True
            st.rerun()

    # 7. BOTTOM NAVIGATION
    st.write("")
    n1, n2, n3 = st.columns([1, 1, 1])
    if i > 0:
        if n1.button("⬅️ Previous", use_container_width=True):
            st.session_state.current_q -= 1
            st.session_state.start_time = None
            st.rerun()
    
    if i < len(st.session_state.questions) - 1:
        if n2.button("Next ➡️", use_container_width=True):
            st.session_state.current_q += 1
            st.session_state.start_time = None
            st.rerun()
    else:
        if n3.button("Submit Test 🏁", type="primary", use_container_width=True):
            st.session_state.finished = True
            st.rerun()

    # 8. LIVE REFRESH LOOP
    time.sleep(1)
    st.rerun()
