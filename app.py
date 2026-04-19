# app.py
import streamlit as st
import pdfplumber
import re
import time
from PIL import Image
import pytesseract

# ---------- SESSION ----------
defaults = {
    "questions": [],
    "current_q": 0,
    "answers": [],
    "start_time": None,
    "time_per_q": 30,
    "finished": False,
    "lang": "EN",
    "selected": None
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ---------- OCR ----------
def extract_text_ocr(file):
    images = []
    text = ""

    pdf = pdfplumber.open(file)
    for page in pdf.pages:
        im = page.to_image(resolution=300)
        img = im.original
        text += pytesseract.image_to_string(img)

    return text


# ---------- NORMAL TEXT ----------
def extract_text(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for p in pdf.pages:
            t = p.extract_text()
            if t:
                text += t + "\n"

    # fallback OCR if text too small
    if len(text.strip()) < 100:
        text = extract_text_ocr(file)

    return text


# ---------- AI ANSWER DETECTION (RULE BASED) ----------
def guess_answer(question, options):
    # simple math detection
    for k, v in options.items():
        if "=" in question:
            try:
                expr = question.split("=")[0]
                result = eval(expr)
                if str(int(result)) in v:
                    return k
            except:
                pass

    return "No Answer"


# ---------- SMART PARSER ----------
def parse_mcqs(text):
    questions = []

    text = text.replace("\r", "")
    text = re.sub(r"\n+", "\n", text)

    # answer key
    answer_map = {}
    for num, ans in re.findall(r"(\d+)\.\s*\((\w)\)", text):
        answer_map[int(num)] = ans.upper()

    blocks = re.split(r"\n(?=\d+\.\s)", text)

    qn = 1

    for block in blocks:
        block = block.strip()

        if not block.startswith(str(qn)):
            continue

        # fix broken options
        block = block.replace("\n[A]", " [A]")
        block = block.replace("\n[B]", " [B]")
        block = block.replace("\n[C]", " [C]")
        block = block.replace("\n[D]", " [D]")

        options = re.findall(r"\[([A-D])\]\s*([^\[]+)", block)

        opt_dict = {}
        for k, v in options:
            opt_dict[k] = " ".join(v.split())

        # auto fix missing
        for op in ["A","B","C","D"]:
            if op not in opt_dict:
                opt_dict[op] = "Option missing"

        try:
            q_text = block.split("[A]")[0].strip()
        except:
            continue

        lines = q_text.split("\n")
        en = lines[0]
        hi = lines[1] if len(lines) > 1 else ""

        if len(en) < 5:
            continue

        # answer logic
        answer = answer_map.get(qn)
        if not answer:
            answer = guess_answer(en, opt_dict)

        questions.append({
            "question_en": en,
            "question_hi": hi,
            "A": opt_dict["A"],
            "B": opt_dict["B"],
            "C": opt_dict["C"],
            "D": opt_dict["D"],
            "answer": answer
        })

        qn += 1

    return questions


# ---------- ALERT ----------
def alert():
    st.markdown("""
    <script>
    var audio = new Audio("https://www.soundjay.com/button/beep-07.wav");
    audio.play();
    if (navigator.vibrate) {
        navigator.vibrate(500);
    }
    </script>
    """, unsafe_allow_html=True)


# ---------- UI ----------
st.title("🧪 Ultimate CBT Test App")

file = st.file_uploader("Upload PDF", type=["pdf"])

if file and not st.session_state.questions:
    text = extract_text(file)
    st.session_state.questions = parse_mcqs(text)
    st.session_state.answers = [None]*len(st.session_state.questions)


# ---------- MAIN ----------
if st.session_state.questions and not st.session_state.finished:

    total = len(st.session_state.questions)
    i = st.session_state.current_q
    q = st.session_state.questions[i]

    if st.session_state.start_time is None:
        st.session_state.start_time = time.time()

    remaining = int(st.session_state.time_per_q - (time.time() - st.session_state.start_time))

    if remaining <= 0:
        alert()
        st.session_state.answers[i] = "No Answer"
        st.session_state.current_q += 1
        st.session_state.start_time = None
        st.rerun()

    # ---------- SIDEBAR ----------
    st.sidebar.title("📊 Palette")
    st.sidebar.markdown(f"⏳ {remaining}s")

    st.sidebar.markdown("""
    🟦 Current  
    🟩 Answered  
    ⬜ Not Answered  
    """)

    cols = st.sidebar.columns(5)

    for idx in range(total):
        color = "⬜"
        if st.session_state.answers[idx]:
            color = "🟩"
        if idx == i:
            color = "🟦"

        with cols[idx % 5]:
            if st.button(f"{color}{idx+1}", key=f"nav_{idx}"):
                st.session_state.current_q = idx
                st.session_state.start_time = None
                st.session_state.selected = None
                st.rerun()

    # ---------- TOP ----------
    c1, c2 = st.columns([2,1])
    with c1:
        st.session_state.lang = st.radio("Lang", ["EN","HI"], horizontal=True)
    with c2:
        st.markdown(f"### ⏳ {remaining}")

    # ---------- QUESTION ----------
    st.subheader(f"Q {i+1}")
    st.write(q["question_en"] if st.session_state.lang=="EN" else q["question_hi"])

    # ---------- OPTIONS ----------
    for op in ["A","B","C","D"]:

        color = ""
        if st.session_state.selected:
            if op == q["answer"]:
                color = "🟢"
            elif op == st.session_state.selected:
                color = "🔴"

        if st.button(f"{color} {op}. {q[op]}", key=f"{i}_{op}"):

            if not st.session_state.selected:
                st.session_state.selected = op
                st.session_state.answers[i] = op

                time.sleep(1)

                st.session_state.current_q += 1
                st.session_state.start_time = None
                st.session_state.selected = None
                st.rerun()


# ---------- RESULT ----------
if st.session_state.finished:
    st.title("Result")

    score = sum(
        1 for i,q in enumerate(st.session_state.questions)
        if st.session_state.answers[i] == q["answer"]
    )

    st.success(f"Score {score}/{len(st.session_state.questions)}")
