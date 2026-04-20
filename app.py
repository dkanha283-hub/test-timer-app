import streamlit as st
import pdfplumber
import re
import time
import os

# --- 1. PAGE CONFIGURATION & CSS ---
st.set_page_config(page_title="Pro CBT Hub", layout="wide", initial_sidebar_state="collapsed")

def inject_custom_css():
    st.markdown("""
        <style>
        .stApp { background-color: #f4f6f9; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .question-box { background-color: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; font-size: 18px; }
        .top-bar { background-color: #1e3a8a; color: white; padding: 15px; border-radius: 5px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;}
        .topic-card { background-color: white; padding: 20px; border-radius: 10px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1); cursor: pointer; border: 2px solid transparent; transition: 0.3s;}
        .topic-card:hover { border-color: #1e3a8a; }
        </style>
    """, unsafe_allow_html=True)

# --- 2. SESSION STATE MANAGEMENT ---
def initialize_state():
    if 'page' not in st.session_state: st.session_state.page = "home"
    if 'selected_topic_file' not in st.session_state: st.session_state.selected_topic_file = None
    if 'quiz_data' not in st.session_state: st.session_state.quiz_data = []
    if 'current_q_index' not in st.session_state: st.session_state.current_q_index = 0
    if 'user_answers' not in st.session_state: st.session_state.user_answers = {}
    if 'time_per_question' not in st.session_state: st.session_state.time_per_question = 60
    if 'max_questions' not in st.session_state: st.session_state.max_questions = 10
    if 'app_lang' not in st.session_state: st.session_state.app_lang = "Bilingual"

# --- 3. CACHED PDF PARSER ---
@st.cache_data
def parse_pdf_to_quiz(file_path):
    extracted_text = ""
    try:
        if not os.path.exists(file_path):
            return []
            
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text: extracted_text += text + "\n"
        
        # Clean headers specifically for Gagan Pratap Sir sheets
        clean_text = re.sub(r'INDIAN\s*RAILWAY FOUNDATION BATCH\s*.*?(?=\n)', '', extracted_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'Maths by Gagan Pratap Sir', '', clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'Bagan Pratap Sir', '', clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'Maths\n', '', clean_text, flags=re.IGNORECASE)
        
        parts = re.split(r'Answer\s+key', clean_text, flags=re.IGNORECASE)
        main_questions_text = parts[0]
        answer_key_text = parts[1] if len(parts) > 1 else ""
        
        correct_answers_dict = {}
        if answer_key_text:
            ans_matches = re.findall(r'(\d+)\.\s*\(([a-d])\)', answer_key_text, re.IGNORECASE)
            for qnum, ans in ans_matches:
                correct_answers_dict[int(qnum)] = ans.upper()
        
        raw_splits = re.split(r'(?:^|\n)\s*(\d+)\.\s+', "\n" + main_questions_text)
        quiz_data = []
        
        for i in range(1, len(raw_splits), 2):
            q_id = int(raw_splits[i])
            q_content = raw_splits[i+1]
            
            opt_a_match = re.search(r'\[A\](.*?)(?=\[B\]|\[C\]|\[D\]|$)', q_content, re.DOTALL | re.IGNORECASE)
            opt_b_match = re.search(r'\[B\](.*?)(?=\[A\]|\[C\]|\[D\]|$)', q_content, re.DOTALL | re.IGNORECASE)
            opt_c_match = re.search(r'\[C\](.*?)(?=\[A\]|\[B\]|\[D\]|$)', q_content, re.DOTALL | re.IGNORECASE)
            opt_d_match = re.search(r'\[D\](.*?)(?=\[A\]|\[B\]|\[C\]|$)', q_content, re.DOTALL | re.IGNORECASE)
            
            opt_a = opt_a_match.group(1).strip() if opt_a_match else "Option A"
            opt_b = opt_b_match.group(1).strip() if opt_b_match else "Option B"
            opt_c = opt_c_match.group(1).strip() if opt_c_match else "Option C"
            opt_d = opt_d_match.group(1).strip() if opt_d_match else "Option D"
            
            first_opt_idx = len(q_content)
            for tag in ['[A]', '[B]', '[C]', '[D]', '[a]', '[b]', '[c]', '[d]']:
                idx = q_content.find(tag)
                if idx != -1 and idx < first_opt_idx:
                    first_opt_idx = idx
                    
            question_text = q_content[:first_opt_idx].strip()
            
            correct_letter = correct_answers_dict.get(q_id, 'A') 
            if correct_letter == 'A': correct_text = opt_a
            elif correct_letter == 'B': correct_text = opt_b
            elif correct_letter == 'C': correct_text = opt_c
            elif correct_letter == 'D': correct_text = opt_d
            else: correct_text = opt_a
            
            if question_text:
                quiz_data.append({
                    "id": q_id,
                    "question": question_text,
                    "options": [opt_a, opt_b, opt_c, opt_d],
                    "answer": correct_text,
                    "explanation": f"Based on the Answer Key, the correct option is [{correct_letter}]."
                })
        return quiz_data
    except Exception as e:
        return []

# --- 4. LANGUAGE FILTER (UPDATED WITH SMART DEDUPLICATION) ---
def filter_text(text, lang):
    if not text or lang == "Bilingual": return text
    lines = text.split('\n')
    filtered_lines = []
    seen_normalized = set()
    
    for l in lines:
        if not l.strip(): continue
        has_hindi = bool(re.search(r'[\u0900-\u097F]', l))
        eng_word_count = len(re.findall(r'\b[a-zA-Z]{2,}\b', l))
        
        processed_line = ""
        
        if lang == "English":
            if has_hindi:
                # Drop the Hindi line completely to prevent leftover math variables showing up
                continue
            else:
                processed_line = l
        elif lang == "Hindi":
            # Keep lines with Hindi, OR lines with very few English words (which are usually math formulas)
            if has_hindi or eng_word_count < 3:
                processed_line = l
                
        if processed_line:
            # Normalize the line by removing spaces and symbols to check for PDF shadow text duplicates
            norm = re.sub(r'\W+', '', processed_line).lower()
            
            # If the line is substantial (more than 3 characters), check if we've already seen it
            if norm and len(norm) > 3:
                if norm in seen_normalized:
                    continue # Skip this duplicate shadow text!
                seen_normalized.add(norm)
            
            filtered_lines.append(processed_line)
            
    res = '\n'.join(filtered_lines).strip()
    return res if res else text 

# --- 5. TIMER INJECTION ---
def inject_timer(seconds):
    html_code = f"""
    <div id="timer" style="font-size: 24px; font-weight: bold; color: #ef4444; text-align: right;"></div>
    <script>
        var timeLeft = {seconds};
        var timerElem = document.getElementById('timer');
        var timerId = setInterval(countdown, 1000);
        function countdown() {{
            if (timeLeft == 0) {{
                clearTimeout(timerId);
                var buttons = window.parent.document.querySelectorAll('button');
                buttons.forEach(function(btn) {{
                    if(btn.innerText === 'Next' || btn.innerText === 'Submit Test') btn.click();
                }});
            }} else {{
                timerElem.innerHTML = "Time Left: " + timeLeft + "s";
                timeLeft--;
            }}
        }}
    </script>
    """
    st.components.v1.html(html_code, height=50)

# --- 6. SETUP POPUP (DIALOG) ---
@st.dialog("⚙️ Quiz Setup")
def setup_dialog(file_name, total_available):
    st.write(f"**Topic:** {file_name.replace('.pdf', '')}")
    st.write(f"Total questions available: {total_available}")
    
    selected_qs = st.slider("How many questions to attempt?", min_value=1, max_value=total_available, value=min(20, total_available))
    timer_sec = st.number_input("Time per question (seconds)", min_value=10, max_value=300, value=60)
    
    if st.button("🚀 Start Quiz", type="primary", use_container_width=True):
        st.session_state.max_questions = selected_qs
        st.session_state.time_per_question = timer_sec
        st.session_state.quiz_data = st.session_state.quiz_data[:selected_qs]
        st.session_state.page = "quiz"
        st.rerun()

# --- 7. RENDER VIEWS ---
def render_home():
    st.markdown('<div class="top-bar"><h2>📚 CBT Topic Hub</h2></div>', unsafe_allow_html=True)
    st.write("Select a topic below to start practicing.")
    
    # Updated list containing all 21 PDF files exactly as named
    topics = {
        "Percentage Part 1": "percent1 (1).pdf",
        "Percentage Part 2": "perceentage2.pdf",
        "Ratio & Proportion": "RATIO_(1).pdf",
        "Problems on Ages": "ages_sheet.pdf",
        "Profit & Loss": "PROFIT_AND_LOSS_SHEET_-_01.pdf",
        "Time & Work": "TIME_AND_WORK_sheet_01.pdf",
        "Discount": "DISCOUNT_SHEET-01.pdf",
        "Pipe & Cistern": "pipe and christen.pdf",
        "Partnership": "Partnership.pdf",
        "Mixture & Alligation Part 1": "mixture and aligation (1).pdf",
        "Mixture & Alligation Part 2": "mixture and aligation (2).pdf",
        "Simple Interest": "simple interest.pdf",
        "Compound Interest": "Compound intrest.pdf",
        "Mensuration 2D (Triangle)": "Mensuration_2D_Triangle_sheet (1).pdf",
        "Mensuration 2D (Quadrilateral)": "Mensuration_2D_(quadrilateral).pdf",
        "Mensuration 2D (Circle)": "circle.pdf",
        "Polygon": "polygon_sheet.pdf",
        "Mensuration 3D (Cone)": "Mensuration 3d Cone Sheet.pdf",
        "Mensuration 3D (Cube & Cuboid)": "Mensuration_3D_cube_and_cuboid_Sheet_01.pdf",
        "Mensuration 3D (Cylinder)": "Mensuration_3D_Cylinder.pdf",
        "Mensuration 3D (Sphere & Hemisphere)": "3D SPARE AND HEMISPHERE Sheet.pdf"
    }
    
    cols = st.columns(2)
    for idx, (topic_name, file_name) in enumerate(topics.items()):
        with cols[idx % 2]:
            if st.button(topic_name, use_container_width=True, icon="📄"):
                st.session_state.selected_topic_file = file_name
                with st.spinner(f"Loading {topic_name}..."):
                    parsed_data = parse_pdf_to_quiz(file_name)
                    if parsed_data:
                        st.session_state.quiz_data = parsed_data
                        setup_dialog(file_name, len(parsed_data))
                    else:
                        st.error(f"Could not load {file_name}. Ensure it is uploaded to your GitHub repository!")

def render_quiz():
    q_index = st.session_state.current_q_index
    q_data = st.session_state.quiz_data[q_index]
    total_qs = len(st.session_state.quiz_data)

    col_sect, col_lang, col_qnum = st.columns([2, 1, 1], vertical_alignment="center")
    with col_sect: st.markdown(f"##### {st.session_state.selected_topic_file.replace('.pdf', '')}")
    with col_lang:
        st.session_state.app_lang = st.selectbox("Language", ["Bilingual", "English", "Hindi"], label_visibility="collapsed")
    with col_qnum: st.markdown(f"##### Q {q_index + 1} / {total_qs}")
    st.divider()

    inject_timer(st.session_state.time_per_question)

    filtered_question = filter_text(q_data["question"], st.session_state.app_lang)
    st.markdown(f'<div class="question-box"><b>Q{q_index + 1}.</b><br><br> {filtered_question}</div>', unsafe_allow_html=True)
    
    selected_option = st.radio("Select an option:", q_data["options"], format_func=lambda x: filter_text(x, st.session_state.app_lang), key=f"q_{q_index}", index=None)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col3:
        if q_index < total_qs - 1:
            if st.button("Next", type="primary", use_container_width=True):
                if selected_option: st.session_state.user_answers[q_index] = selected_option
                st.session_state.current_q_index += 1
                st.rerun()
        else:
            if st.button("Submit Test", type="primary", use_container_width=True):
                if selected_option: st.session_state.user_answers[q_index] = selected_option
                st.session_state.page = "analysis"
                st.rerun()

def render_analysis():
    st.title("📊 Exam Analysis")
    total_qs = len(st.session_state.quiz_data)
    correct_count = sum(1 for i, q in enumerate(st.session_state.quiz_data) if st.session_state.user_answers.get(i) == q["answer"])
            
    accuracy = (correct_count / total_qs) * 100 if total_qs > 0 else 0
    st.metric("Total Score", f"{correct_count} / {total_qs}", f"{accuracy:.1f}% Accuracy")
    
    if st.button("🏠 Go to Home Page", type="primary"):
        st.session_state.clear()
        st.rerun()
        
    st.write("### Detailed Review")
    st.session_state.app_lang = st.radio("Review Language", ["Bilingual", "English", "Hindi"], horizontal=True)
    
    for i, q in enumerate(st.session_state.quiz_data):
        disp_q = filter_text(q['question'], st.session_state.app_lang)
        disp_ans = filter_text(q['answer'], st.session_state.app_lang)
        disp_user = filter_text(st.session_state.user_answers.get(i, 'Not Attempted'), st.session_state.app_lang)
        
        with st.expander(f"Q{i+1}: {disp_q[:40]}..."):
            st.markdown(f"**Question:**\n {disp_q}")
            st.write(f"**Your Answer:** {disp_user}")
            st.write(f"**Correct Answer:** {disp_ans}")
            st.info(q['explanation'])

def main():
    inject_custom_css()
    initialize_state()

    if st.session_state.page == "home":
        render_home()
    elif st.session_state.page == "quiz":
        render_quiz()
    elif st.session_state.page == "analysis":
        render_analysis()

if __name__ == "__main__":
    main()
    
