# app.py
import streamlit as st
import pdfplumber
import time
import json
from datetime import datetime
from openai import OpenAI

# ---------- CONFIG ----------
OPENAI_API_KEY = "YOUR_API_KEY_HERE"

client = OpenAI(api_key=OPENAI_API_KEY)

# ---------- INIT STATE ----------
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
def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text


def parse_questions_with_llm(text):
    prompt = f"""
    Extract MCQs from the text below.

    Return STRICT JSON format:
    [
      {{
        "question": "...",
        "A": "...",
        "B": "...",
        "C": "...",
        "D": "...",
        "answer": "A/B/C/D"
      }}
    ]

    TEXT:
    {text}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    content = response.choices[0].message.content

    try:
        return json.loads(content)
    except:
        st.error("Failed to parse questions. Check PDF format.")
        return []


def next_question():
    st.session_state.current_q += 1
    st.session_state.timer_start = None

    if st.session_state.current_q >= len(st.session_state.questions):
        st.session_state.finished = True


# ---------- UI ----------
st.title("🧪 Test Timer App")

# Sidebar settings
st.sidebar.header("⚙️ Settings")
st.session_state.time_per_q = st.sidebar.number_input(
    "Time per Question (seconds)", min_value=5, max_value=300, value=30
)

# ---------- PDF Upload ----------
uploaded_file = st.file_uploader("Upload your MCQ PDF", type=["pdf"])

if uploaded_file and not st.session_state.questions:
    with st.spinner("Extracting and analyzing PDF..."):
        text = extract_text_from_pdf(uploaded_file)
        questions = parse_questions_with_llm(text)

        st.session_state.questions = questions
        st.session_state.answers = [None] * len(questions)
        st.session_state.current_q = 0

# ---------- QUIZ ----------
if st.session_state.questions and not st.session_state.finished:

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
