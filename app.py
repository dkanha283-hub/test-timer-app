# app.py
import streamlit as st
import pdfplumber
import time
import json
import google.generativeai as genai

# ---------- GEMINI SETUP ----------
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-1.5-flash")

# ---------- SESSION STATE ----------
if "questions" not in st.session_state:
    st.session_state.questions = []
if "current_q" not in st.session_state:
    st.session_state.current_q = 0
if "answers" not in st.session_state:
    st.session_state.answers = []
if "timer_start" not in st.session_state:
    st.session_state.timer_start = None
if "time_per_q" not in st.session_state:
    st.session_state.time_per_q = 30
if "finished" not in st.session_state:
    st.session_state.finished = False


# ---------- FUNCTIONS ----------
def extract_text(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    return text


def parse(text):
    prompt = f"""
    Extract all MCQ questions.

    Return ONLY JSON like this:
    [
      {{
        "question": "...",
        "A": "...",
        "B": "...",
        "C": "...",
        "D": "...",
        "answer": "A"
      }}
    ]

    RULES:
    - No explanation
    - No markdown
    - Only JSON

    TEXT:
    {text}
    """

    response = model.generate_content(prompt)
    content = response.text.strip()

    # clean markdown if exists
    if "```" in content:
        content = content.split("```")[1]

    try:
        return json.loads(content)
    except:
        st.error("❌ Failed to read questions. Try another PDF.")
        return []


def next_q():
    st.session_state.current_q += 1
    st.session_state.timer_start = None

    if st.session_state.current_q >= len(st.session_state.questions):
        st.session_state.finished = True


# ---------- UI ----------
st.title("🧪 Test Timer App")

st.sidebar.header("⚙️ Settings")
st.session_state.time_per_q = st.sidebar.number_input(
    "Time per Question (seconds)", 5, 300, 30
)

file = st.file_uploader("Upload your MCQ PDF", type=["pdf"])


# ---------- LOAD QUESTIONS ----------
if file and not st.session_state.questions:
    with st.spinner("Reading PDF..."):
        text = extract_text(file)
        qs = parse(text)

        if qs:
            st.session_state.questions = qs
            st.session_state.answers = [None] * len(qs)
            st.session_state.current_q = 0


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

    st.sidebar.markdown(f"# ⏳ {max(0, remaining)} sec")

    if remaining <= 0:
        st.session_state.answers[i] = "No Answer"
        next_q()
        st.rerun()

    st.subheader(f"Question {i+1}")
    st.write(q["question"])

    for op in ["A", "B", "C", "D"]:
        if st.button(f"{op}. {q[op]}", key=f"{i}_{op}"):
            st.session_state.answers[i] = op
            next_q()
            st.rerun()


# ---------- RESULTS ----------
if st.session_state.finished:
    st.title("📊 Results")

    score = 0

    for i, q in enumerate(st.session_state.questions):
        user = st.session_state.answers[i]
        correct = q["answer"]

        if user == correct:
            score += 1

        st.write(f"Q{i+1}: Your = {user} | Correct = {correct}")

    st.success(f"Score: {score}/{len(st.session_state.questions)}")if st.session_state.questions and not st.session_state.finished:

    q_idx = st.session_state.current_q
    question = st.session_state.questions[q_idx]

    # Timer setup
    if st.session_state.timer_start is None:
        st.session_state.timer_start = time.time()

    elapsed = time.time() - st.session_state.timer_start
    remaining = int(st.session_state.time_per_q - elapsed)

    # Sidebar Timer
    st.sidebar.markdown(f"# ⏳ {max(0, remaining)} sec")

    if remaining <= 0:
        st.session_state.answers[q_idx] = "No Answer"
        next_question()
        st.rerun()

    # Display Question
    st.subheader(f"Question {q_idx + 1}")
    st.write(question["question"])

    # Options
    for option in ["A", "B", "C", "D"]:
        if st.button(f"{option}. {question[option]}", key=f"{q_idx}_{option}"):
            st.session_state.answers[q_idx] = option
            next_question()
            st.rerun()

# ---------- RESULTS ----------
if st.session_state.finished:
    st.title("📊 Results")

    score = 0

    for i, q in enumerate(st.session_state.questions):
        user_ans = st.session_state.answers[i]
        correct = q["answer"]

        if user_ans == correct:
            score += 1

        st.write(f"Q{i+1}: Your Answer = {user_ans} | Correct = {correct}")

    st.success(f"Final Score: {score}/{len(st.session_state.questions)}")
