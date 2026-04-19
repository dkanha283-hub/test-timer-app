# app.py
import streamlit as st
import pdfplumber
import re
import time

# ---------- SESSION ----------
for key, default in {
    "questions": [],
    "current_q": 0,
    "answers": [],
    "timer_start": None,
    "time_per_q": 30,
    "finished": False,
    "lang": "EN",
    "selected": None
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ---------- EXTRACT ----------
def extract_text(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    return text


def extract_answers(text):
    answers = {}
    matches = re.findall(r"(\d+)\.\s*\((\w)\)", text)
    for num, ans in matches:
        answers[int(num)] = ans.upper()
    return answers


def parse_mcqs(text):
    questions = []
    blocks = re.split(r"\n\d+\.\s", text)
    answer_map = extract_answers(text)
    q_number = 1

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        options = re.findall(r"\[([A-D])\]\s*(.*?)\s*(?=\[|$)", block)
        if len(options) < 4:
            continue

        q_part = block.split("[A]")[0].strip()
        parts = q_part.split("\n")

        en = parts[0]
        hi = parts[1] if len(parts) > 1 else ""

        opt_dict = {k: v.strip() for k, v in options}

        questions.append({
            "question_en": en,
            "question_hi": hi,
            "A": opt_dict.get("A", ""),
            "B": opt_dict.get("B", ""),
            "C": opt_dict.get("C", ""),
            "D": opt_dict.get("D", ""),
            "answer": answer_map.get(q_number, "No Answer")
        })

        q_number += 1

    return questions


# ---------- NEXT ----------
def next_q():
    st.session_state.current_q += 1
    st.session_state.timer_start = None
    st.session_state.selected = None

    if st.session_state.current_q >= len(st.session_state.questions):
        st.session_state.finished = True


# ---------- UI ----------
st.title("🧪 Test Timer Pro (CBT Mode)")

# TOP BAR (LIKE CBT)
col1, col2 = st.columns(2)

with col1:
    st.session_state.lang = st.radio(
        "Language",
        ["EN", "HI"],
        horizontal=True
    )

with col2:
    if st.session_state.timer_start:
        remaining = int(
            st.session_state.time_per_q
            - (time.time() - st.session_state.timer_start)
        )
        st.markdown(f"### ⏳ {max(0, remaining)} sec")

file = st.file_uploader("Upload PDF", type=["pdf"])


# ---------- LOAD ----------
if file and not st.session_state.questions:
    with st.spinner("Processing PDF..."):
        text = extract_text(file)
        qs = parse_mcqs(text)

        if qs:
            st.session_state.questions = qs
            st.session_state.answers = [None] * len(qs)
        else:
            st.error("❌ PDF not supported")


# ---------- QUIZ ----------
if st.session_state.questions and not st.session_state.finished:

    i = st.session_state.current_q
    q = st.session_state.questions[i]

    if st.session_state.timer_start is None:
        st.session_state.timer_start = time.time()

    remaining = int(
        st.session_state.time_per_q
        - (time.time() - st.session_state.timer_start)
    )

    if remaining <= 0:
        st.session_state.answers[i] = "No Answer"
        next_q()
        st.rerun()

    st.subheader(f"Question {i+1}")

    if st.session_state.lang == "EN":
        st.write(q["question_en"])
    else:
        st.write(q["question_hi"])

    # OPTION BUTTONS WITH COLOR
    for op in ["A", "B", "C", "D"]:

        label = f"{op}. {q[op]}"

        # default
        btn_type = "secondary"

        if st.session_state.selected:
            if op == q["answer"]:
                btn_type = "primary"  # correct = green
            elif op == st.session_state.selected:
                btn_type = "secondary"  # wrong selected
            else:
                btn_type = "secondary"

        if st.button(label, key=f"{i}_{op}", type=btn_type):

            if not st.session_state.selected:
                st.session_state.selected = op
                st.session_state.answers[i] = op

                # show result then auto move
                time.sleep(1.5)
                next_q()
                st.rerun()


# ---------- RESULTS ----------
if st.session_state.finished:
    st.title("📊 Results")

    score = 0
    wrong = []

    for i, q in enumerate(st.session_state.questions):
        user = st.session_state.answers[i]
        correct = q["answer"]

        if user == correct:
            score += 1
        else:
            wrong.append((i, q, user, correct))

    st.success(f"Score: {score}/{len(st.session_state.questions)}")

    if st.checkbox("❌ Review Wrong Only"):
        for i, q, user, correct in wrong:
            st.write(f"Q{i+1}")
            st.write(q["question_en"])
            st.write(f"Your: {user} | Correct: {correct}")
