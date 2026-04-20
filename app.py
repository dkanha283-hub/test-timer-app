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
        "answers": {}, # Changed to dict for easier lookup
        "start_time": None,
        "time_per_q": 30,
        "finished": False,
        "lang": "EN"
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()

# ---------- OCR & EXTRACTION ----------
def extract_text_ocr(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            im = page.to_image(resolution=300)
            text += pytesseract.image_to_string(im.original)
    return text

def extract_text(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for p in pdf.pages:
            t = p.extract_text()
            if t: text += t + "\n"
    
    if len(text.strip()) < 100:
        text = extract_text_ocr(file)
    return text

# ---------- IMPROVED PARSER ----------
def parse_mcqs(text):
    questions = []
    # Normalize text
    text = re.sub(r"\n+", "\n", text.replace("\r", ""))
    
    # Identify Question Blocks (Digit followed by dot and space)
    blocks = re.split(r"\n(?=\d+\.\s)", text)
    
    for block in blocks:
        block = block.strip()
        # Regex to find options [A], [B], etc.
        options = re.findall(r"\[([A-D])\]\s*([^\[\n]+)", block)
        if not options: continue
        
        opt_dict = {k: v.strip() for k, v in options}
        # Fallback for missing options
        for op in ["A","B","C","D"]:
            if op not in opt_dict: opt_dict[op] = "N/A"
            
        q_text_full = block.split("[A]")[0].strip()
        lines = q_text_full.split("\n")
        
        questions.append({
            "question_en": lines[0],
            "question_hi": lines[1] if len(lines) > 1 else lines[0],
            "options": opt_dict,
            "answer": "A" # Defaulting to A if not found in text; adjust as needed
        })
    return questions

# ---------- UI COMPONENTS ----------
def show_results():
    st.title("🏆 Test Report")
    total = len(st.session_state.questions)
    correct = 0
    incorrect = 0
    unattempted = 0

    for i, q in enumerate(st.session_state.questions):
        user_ans = st.session_state.answers.get(i)
        if not user_ans: unattempted += 1
        elif user_ans == q["answer"]: correct += 1
        else: incorrect += 1

    col1, col2, col3 = st.columns(3)
    col1.metric("Correct", correct)
    col2.metric("Incorrect", incorrect)
    col3.metric("Unattempted", unattempted)
    
    st.progress(correct / total if total > 0 else 0)
    
    if st.button("Restart Test"):
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun()

# ---------- MAIN APP ----------
st.set_page_config(page_title="CBT Pro", layout="wide")

if not st.session_state.questions:
    st.title("🧪 CBT Test Uploader")
    file = st.file_uploader("Upload Exam PDF", type=["pdf"])
    if file:
        with st.spinner("Parsing questions..."):
            text = extract_text(file)
            st.session_state.questions = parse_mcqs(text)
            st.rerun()

elif st.session_state.finished:
    show_results()

else:
    # Sidebar Palette
    st.sidebar.title("Navigation")
    total_qs = len(st.session_state.questions)
    
    # Progress bar in sidebar
    progress = len(st.session_state.answers) / total_qs
    st.sidebar.progress(progress)
    
    cols = st.sidebar.columns(4)
    for idx in range(total_qs):
        status = "⚪"
        if idx in st.session_state.answers: status = "🟢"
        if idx == st.session_state.current_q: status = "🔵"
        
        if cols[idx % 4].button(f"{status}{idx+1}", key=f"nav_{idx}"):
            st.session_state.current_q = idx
            st.rerun()

    # Main Test Area
    q_idx = st.session_state.current_q
    q = st.session_state.questions[q_idx]
    
    st.subheader(f"Question {q_idx + 1} of {total_qs}")
    
    lang = st.radio("Language", ["English", "Hindi"], horizontal=True)
    display_text = q["question_en"] if lang == "English" else q["question_hi"]
    st.markdown(f"#### {display_text}")

    # Display Options
    selected_option = st.session_state.answers.get(q_idx)
    
    for label, text in q["options"].items():
        # Use button style for selection
        if st.button(f"{label}: {text}", 
                     key=f"opt_{q_idx}_{label}", 
                     use_container_width=True,
                     type="primary" if selected_option == label else "secondary"):
            st.session_state.answers[q_idx] = label
            st.rerun()

    # Navigation Buttons
    st.divider()
    nav_col1, nav_col2, nav_col3 = st.columns([1,1,1])
    
    if q_idx > 0:
        if nav_col1.button("⬅️ Previous"):
            st.session_state.current_q -= 1
            st.rerun()
            
    if q_idx < total_qs - 1:
        if nav_col2.button("Next ➡️"):
            st.session_state.current_q += 1
            st.rerun()
    else:
        if nav_col3.button("Finish Test 🚩", type="primary"):
            st.session_state.finished = True
            st.rerun()
