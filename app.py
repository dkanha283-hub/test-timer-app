# app.py
import streamlit as st
import pdfplumber
import re
import time

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


# ---------- SOUND + VIBRATION ----------
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


# ---------- EXTRACT ----------
def extract_text(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for p in pdf.pages:
            t = p.extract_text()
            if t:
                text += t + "\n"
    return text


def extract_answers(text):
    ans = {}
    for num, a in re.findall(r"(\d+)\.\s*\((\w)\)", text):
        ans[int(num)] = a.upper()
    return ans


def parse_mcqs(text):
    qs = []
    blocks = re.split(r"\n\d+\.\s", text)
    ans_map = extract_answers(text)
    qn = 1

    for b in blocks:
        b = b.strip()
        if not b:
            continue

        opts = re.findall(r"\[([A-D])\]\s*(.*?)\s*(?=\[|$)", b)
        if len(opts) < 4:
            continue

        q_text = b.split("[A]")[0].strip().split("\n")
        en = q_text[0]
        hi = q_text[1] if len(q_text) > 1 else ""

        opt_dict = {k: v.strip() for k, v in opts}

        qs.append({
            "question_en": en,
            "question_hi": hi,
            "A": opt_dict["A"],
            "B": opt_dict["B"],
            "C": opt_dict["C"],
            "D": opt_dict["D"],
            "answer": ans_map.get(qn, "No Answer")
        })
        qn += 1

    return qs


# ---------- LOAD ----------
st.title("🧪 RRB CBT Test App")

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

    elapsed = time.time() - st.session_state.start_time
    remaining = int(st.session_state.time_per_q - elapsed)

    # TIME UP
    if remaining <= 0:
        alert()
        st.session_state.answers[i] = "No Answer"
        st.session_state.current_q += 1
        st.session_state.start_time = None
        st.rerun()

    # ---------- SIDEBAR (RRB STYLE) ----------
    st.sidebar.title("📊 Question Panel")

    st.sidebar.markdown(f"### ⏳ {remaining} sec")

    # LEGEND
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
            if st.button(f"{color}{idx+1}", key=f"side_{idx}"):
                st.session_state.current_q = idx
                st.session_state.start_time = None
                st.session_state.selected = None
                st.rerun()

    # ---------- TOP ----------
    col1, col2 = st.columns([2,1])

    with col1:
        st.session_state.lang = st.radio("Language", ["EN","HI"], horizontal=True)

    with col2:
        st.markdown(f"### ⏳ {remaining}")

    # ---------- QUESTION ----------
    st.subheader(f"Question {i+1}")
    st.write(q["question_en"] if st.session_state.lang=="EN" else q["question_hi"])

    # ---------- OPTIONS ----------
    for op in ["A","B","C","D"]:

        label = f"{op}. {q[op]}"
        color = ""

        if st.session_state.selected:
            if op == q["answer"]:
                color = "🟢"
            elif op == st.session_state.selected:
                color = "🔴"

        if st.button(f"{color} {label}", key=f"{i}_{op}"):

            if not st.session_state.selected:
                st.session_state.selected = op
                st.session_state.answers[i] = op

                time.sleep(1)

                st.session_state.current_q += 1
                st.session_state.start_time = None
                st.session_state.selected = None
                st.rerun()


# ---------- RESULTS ----------
if st.session_state.finished:
    st.title("📊 Result")

    score = sum(
        1 for i,q in enumerate(st.session_state.questions)
        if st.session_state.answers[i] == q["answer"]
    )

    st.success(f"Score {score}/{len(st.session_state.questions)}")
