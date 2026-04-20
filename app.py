import streamlit as st
import pdfplumber
import pytesseract
from PIL import Image
import re
import time

# --- 1. PAGE CONFIGURATION & CSS INJECTION ---
st.set_page_config(page_title="Pro CBT Simulator", layout="wide", initial_sidebar_state="collapsed")

def inject_custom_css():
    st.markdown("""
        <style>
        /* Clean CBT Interface Styles */
        .stApp { background-color: #f4f6f9; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .question-box { background-color: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; font-size: 18px; }
        .option-label { cursor: pointer; transition: 0.3s; padding: 10px; border-radius: 5px; }
        .option-label:hover { background-color: #e2e8f0; }
        
        /* Haptic Shake Animation for Wrong Answers */
        @keyframes shake {
            0% { transform: translateX(0); }
            25% { transform: translateX(-5px); }
            50% { transform: translateX(5px); }
            75% { transform: translateX(-5px); }
            100% { transform: translateX(0); }
        }
        .shake { animation: shake 0.4s; }
        
        /* Top Bar mimicking RRB/OJEE */
        .top-bar { background-color: #1e3a8a; color: white; padding: 15px; border-radius: 5px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;}
        </style>
    """, unsafe_allow_html=True)

# --- 2. SESSION STATE MANAGEMENT ---
def initialize_state():
    if 'quiz_data' not in st.session_state:
        st.session_state.quiz_data = []
    if 'current_q_index' not in st.session_state:
        st.session_state.current_q_index = 0
    if 'user_answers' not in st.session_state:
        st.session_state.user_answers = {}
    if 'quiz_active' not in st.session_state:
        st.session_state.quiz_active = False
    if 'time_per_question' not in st.session_state:
        st.session_state.time_per_question = 60 # Default 60 seconds

# --- 3. ADVANCED PDF PARSING LOGIC ---
def parse_pdf_to_quiz(file):
    """
    Advanced extraction engine to handle bilingual (Hindi/English) PDFs
    and accurately separate questions from options.
    """
    extracted_text = ""
    try:
        # Step A: Extract text from all pages
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
        
        # Step B: FILTER OUT HINDI (Devanagari characters)
        # This removes the Unicode range for Hindi, keeping only English/Numbers
        extracted_text = re.sub(r'[\u0900-\u097F]+', '', extracted_text)
        
        # Step C: SPLIT INTO QUESTIONS
        # Strictly looks for a newline, followed by a number and a dot/bracket
        raw_splits = re.split(r'\n\s*(?:Q\.|Q)?\s*(\d+)[\.\)]\s+', "\n" + extracted_text)
        
        quiz_data = []
        
        # Group data: [preamble, Q1_num, Q1_text, Q2_num, Q2_text...]
        for i in range(1, len(raw_splits), 2):
            q_num = raw_splits[i]
            q_content = raw_splits[i+1].strip()
            
            # Step D: FIND OPTIONS INSIDE THE QUESTION
            # Looks for (A), (B), A., B., a), b), 1), 2)
            opt_pattern = r'\n?\s*(?:\([A-Da-d1-4]\)|[A-Da-d1-4][\.\)])\s+'
            q_parts = re.split(opt_pattern, q_content)
            
            question_text = q_parts[0].strip()
            options = []
            
            if len(q_parts) > 1:
                for opt in q_parts[1:]:
                    if opt.strip():
                        # Clean up formatting spacing
                        options.append(re.sub(r'\s+', ' ', opt.strip()))
            
            # Fallback if options were not cleanly found
            if len(options) < 2:
                options = ["Option A", "Option B", "Option C", "Option D"]
                question_text = q_content # Keep the whole block
            
            # Package the question
            quiz_data.append({
                "id": int(q_num),
                "question": question_text,
                "options": options[:4], 
                "answer": options[0] if options else "Option A", # Placeholder answer
                "explanation": "No explanation extracted from PDF."
            })
            
        if not quiz_data:
            st.warning("Could not automatically detect questions. Ensure they start with numbers on a new line (e.g., '1. ').")
            return []
            
        return quiz_data

    except Exception as e:
        st.error(f"Error parsing PDF: {e}")
        return []

# --- 4. TIMER & JS INJECTION ---
def inject_timer(seconds):
    """Injects JS to create a live timer and auto-clicks 'Next' when time is up."""
    html_code = f"""
    <div id="timer" style="font-size: 24px; font-weight: bold; color: #ef4444; text-align: right;"></div>
    <script>
        var timeLeft = {seconds};
        var timerElem = document.getElementById('timer');
        var timerId = setInterval(countdown, 1000);
        
        function countdown() {{
            if (timeLeft == 0) {{
                clearTimeout(timerId);
                // Look for the Next button and click it
                var buttons = window.parent.document.querySelectorAll('button');
                buttons.forEach(function(btn) {{
                    if(btn.innerText === 'Next Question' || btn.innerText === 'Submit Quiz') {{
                        btn.click();
                    }}
                }});
            }} else {{
                timerElem.innerHTML = "Time Left: " + timeLeft + "s";
                timeLeft--;
            }}
        }}
    </script>
    """
    st.components.v1.html(html_code, height=50)

# --- 5. MAIN UI & NAVIGATION ---
def render_dashboard():
    st.title("📊 Exam Analysis Dashboard")
    st.success("Quiz Completed Successfully!")
    
    total_qs = len(st.session_state.quiz_data)
    correct_count = 0
    
    for i, q in enumerate(st.session_state.quiz_data):
        user_ans = st.session_state.user_answers.get(i)
        is_correct = (user_ans == q["answer"])
        if is_correct:
            correct_count += 1
            
    # Calculate accuracy safely to avoid division by zero
    accuracy = (correct_count / total_qs) * 100 if total_qs > 0 else 0
    st.metric("Total Score", f"{correct_count} / {total_qs}", f"{accuracy:.1f}% Accuracy")
    
    st.write("### Detailed Review")
    for i, q in enumerate(st.session_state.quiz_data):
        with st.expander(f"Q{i+1}: {q['question'][:50]}..."):
            st.write(f"**Question:** {q['question']}")
            st.write(f"**Your Answer:** {st.session_state.user_answers.get(i, 'Not Attempted')}")
            st.write(f"**Correct Answer:** {q['answer']}") # Reminder: these are placeholder answers right now!
            st.info(f"**Explanation:** {q['explanation']}")
            
    if st.button("Start New Test"):
        st.session_state.clear()
        st.rerun()

def main():
    inject_custom_css()
    initialize_state()

    # SETUP SCREEN
    if not st.session_state.quiz_active and not st.session_state.user_answers:
        st.markdown('<div class="top-bar"><h2>CBT Simulator Setup</h2></div>', unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Upload your study material (PDF)", type="pdf")
        st.session_state.time_per_question = st.number_input("Time per question (seconds)", min_value=10, value=60)
        
        if uploaded_file and st.button("Parse & Start Quiz"):
            with st.spinner("Extracting text and formatting questions..."):
                parsed_data = parse_pdf_to_quiz(uploaded_file)
                if parsed_data:
                    st.session_state.quiz_data = parsed_data
                    st.session_state.quiz_active = True
                    st.rerun()

    # ACTIVE QUIZ SCREEN
    elif st.session_state.quiz_active:
        q_index = st.session_state.current_q_index
        q_data = st.session_state.quiz_data[q_index]
        total_qs = len(st.session_state.quiz_data)

        # Header bar
        st.markdown(f'''
            <div class="top-bar">
                <div>Section: Quantitative Aptitude</div>
                <div>Question {q_index + 1} of {total_qs}</div>
            </div>
        ''', unsafe_allow_html=True)

        # Timer
        inject_timer(st.session_state.time_per_question)

        # Question Area
        st.markdown(f'<div class="question-box"><b>Q{q_index + 1}.</b> {q_data["question"]}</div>', unsafe_allow_html=True)
        
        # Options
        selected_option = st.radio("Select an option:", q_data["options"], key=f"q_{q_index}", index=None)
        
        # Navigation Buttons
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            if q_index > 0:
                if st.button("Previous"):
                    st.session_state.current_q_index -= 1
                    st.rerun()
                    
        with col3:
            if q_index < total_qs - 1:
                if st.button("Next Question", type="primary"):
                    if selected_option:
                        st.session_state.user_answers[q_index] = selected_option
                    st.session_state.current_q_index += 1
                    st.rerun()
            else:
                if st.button("Submit Quiz", type="primary"):
                    if selected_option:
                        st.session_state.user_answers[q_index] = selected_option
                    st.session_state.quiz_active = False
                    st.rerun()

    # DASHBOARD SCREEN
    else:
        render_dashboard()

if __name__ == "__main__":
    main()
