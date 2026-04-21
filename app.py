import streamlit as st
import pdfplumber
import re
import time
import os
import random
import json

# --- 1. PAGE CONFIGURATION & CSS ---
st.set_page_config(page_title="Pro CBT Hub", layout="wide", initial_sidebar_state="collapsed")

def inject_custom_css():
    st.markdown("""
        <style>
        .stApp { background-color: #f4f6f9; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .question-box { background-color: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; font-size: 18px; white-space: pre-wrap; line-height: 1.6;}
        .top-bar { background-color: #1e3a8a; color: white; padding: 15px; border-radius: 5px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;}
        .topic-card { background-color: white; padding: 20px; border-radius: 10px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1); cursor: pointer; border: 2px solid transparent; transition: 0.3s;}
        .topic-card:hover { border-color: #1e3a8a; }
        </style>
    """, unsafe_allow_html=True)

# --- 2. GLOBAL CLOUD SESSION STORE ---
@st.cache_resource
def get_global_sessions():
    return {}

def save_state_to_cloud():
    sessions = get_global_sessions()
    now = time.time()
    expired = [pin for pin, data in sessions.items() if (now - data['timestamp']) > 18000]
    for pin in expired:
        del sessions[pin]
        
    if 'resume_pin' in st.session_state:
        sessions[st.session_state.resume_pin] = {
            "file": st.session_state.selected_topic_file,
            "q_index": st.session_state.current_q_index,
            "answers": st.session_state.user_answers.copy(),
            "time": st.session_state.time_per_question,
            "max_qs": st.session_state.max_questions,
            "quiz_data": st.session_state.quiz_data, 
            "timestamp": now
        }

# --- 3. SESSION STATE MANAGEMENT ---
def initialize_state():
    if 'page' not in st.session_state: st.session_state.page = "home"
    if 'selected_topic_file' not in st.session_state: st.session_state.selected_topic_file = None
    if 'quiz_data' not in st.session_state: st.session_state.quiz_data = []
    if 'current_q_index' not in st.session_state: st.session_state.current_q_index = 0
    if 'user_answers' not in st.session_state: st.session_state.user_answers = {}
    if 'time_per_question' not in st.session_state: st.session_state.time_per_question = 60
    if 'max_questions' not in st.session_state: st.session_state.max_questions = 10
    if 'app_lang' not in st.session_state: st.session_state.app_lang = "Bilingual"
    if 'resume_pin' not in st.session_state: st.session_state.resume_pin = str(random.randint(1000, 9999))

# --- 4. BACKEND CONVERTER ENGINE (PDF -> DICT) ---
def parse_pdf_to_raw_data(file_path):
    extracted_text = ""
    try:
        if not os.path.exists(file_path): return []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text(x_tolerance=2, y_tolerance=3)
                if text: extracted_text += text + "\n"
        
        clean_text = re.sub(r'INDIAN\s*RAILWAY FOUNDATION BATCH\s*.*?(?=\n)', '', extracted_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'Maths by Gagan Pratap Sir', '', clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'Bagan Pratap Sir', '', clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'Maths\n', '', clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'\[\s*([A-Da-d])\s*\]', r'[\1]', clean_text)
        clean_text = re.sub(r'\(\s*([A-Da-d])\s*\)', r'[\1]', clean_text)
        
        ak_matches = list(re.finditer(r'Answer\s*key|Answers', clean_text, flags=re.IGNORECASE))
        if ak_matches:
            last_match = ak_matches[-1]
            main_questions_text = clean_text[:last_match.start()]
            answer_key_text = clean_text[last_match.end():]
        else:
            main_questions_text = clean_text
            answer_key_text = ""
        
        correct_answers_dict = {}
        if answer_key_text:
            ak_text = answer_key_text.lower().replace('α', 'a')
            ans_matches = re.findall(r'(\d+)\s*\.?\s*[\(\[]\s*([a-d])\s*[\)\]]', ak_text)
            nums = re.findall(r'\b(\d+)\s*\.', ak_text)
            opts = re.findall(r'[\(\[]\s*([a-d])\s*[\)\]]', ak_text)
            if len(ans_matches) < len(opts) * 0.5: 
                ans_matches = list(zip(nums, opts))
            for qnum, ans in ans_matches:
                correct_answers_dict[int(qnum)] = ans.upper()
        
        raw_splits = re.split(r'(?:^|\n)\s*(\d+)[\.\)]\s+', "\n" + main_questions_text)
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
                if idx != -1 and idx < first_opt_idx: first_opt_idx = idx
                    
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

# --- 5. AUTOMATIC JSON MANAGER ---
@st.cache_data
def load_and_auto_save_quiz_data(pdf_filename):
    """Automatically loads from JSON, or creates the JSON if missing."""
    json_filename = pdf_filename.replace('.pdf', '.json')
    
    # If the JSON database already exists, load it instantly!
    if os.path.exists(json_filename):
        with open(json_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data, True
        
    # If JSON doesn't exist, read the PDF and CREATE the JSON automatically!
    data = parse_pdf_to_raw_data(pdf_filename)
    if data:
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    return data, False

def update_question_in_database(file_name, updated_q):
    """Saves edits permanently to the JSON file on the server."""
    json_filename = file_name.replace('.pdf', '.json')
    try:
        with open(json_filename, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
            
        # Find the question by its ID and replace it
        for i, q in enumerate(all_data):
            if q['id'] == updated_q['id']:
                all_data[i] = updated_q
                break
                
        # Rewrite the JSON file
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Failed to update database: {e}")
        return False

# --- 6. SURGICAL LANGUAGE FILTER ---
def filter_text(text, lang, is_option=False):
    if not text or lang == "Bilingual": return text
    lines = text.split('\n')
    filtered_lines = []
    seen_normalized = set()
    for l in lines:
        if not l.strip(): continue
        has_hindi = bool(re.search(r'[\u0900-\u097F]', l))
        eng_word_count = len(re.findall(r'\b[a-zA-Z]{3,}\b', l))
        processed_line = ""
        if lang == "English":
            if has_hindi:
                if is_option:
                    clean_l = re.sub(r'[\u0900-\u097F।]+', '', l).strip()
                    clean_l = re.sub(r'[\/\-\|\,]\s*$', '', clean_l).strip() 
                    if clean_l: filtered_lines.append(clean_l)
                else: continue
            else: filtered_lines.append(l)
        elif lang == "Hindi":
            if has_hindi: filtered_lines.append(l)
            else:
                if is_option or eng_word_count < 4: filtered_lines.append(l)
    return '\n'.join(filtered_lines).strip()

# --- 7. TIMER INJECTION ---
def inject_timer(seconds, q_index):
    html_code = f"""
    <div id="timer_display_{q_index}" style="font-size: 24px; font-weight: bold; color: #ef4444; text-align: right;"></div>
    <script>
        var timeLeft = {seconds};
        var timerElem = document.getElementById('timer_display_{q_index}');
        var timerId = setInterval(countdown, 1000);
        function countdown() {{
            if (timeLeft <= 0) {{
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

# --- 8. SETUP POPUP (DIALOG) ---
@st.dialog("⚙️ Quiz Setup")
def setup_dialog(file_name, total_available, is_json):
    st.write(f"**Topic:** {file_name.replace('.pdf', '')}")
    if is_json:
        st.success("⚡ Loaded instantly from JSON Database!")
    else:
        st.info("📄 PDF Scanned. New JSON Database automatically created!")

    st.write(f"Total questions available: {total_available}")
    selected_qs = st.slider("How many questions to attempt?", min_value=1, max_value=total_available, value=min(20, total_available))
    timer_sec = st.number_input("Time per question (seconds)", min_value=10, max_value=300, value=60)
    
    if st.button("🚀 Start Quiz", type="primary", use_container_width=True):
        st.session_state.max_questions = selected_qs
        st.session_state.time_per_question = timer_sec
        st.session_state.quiz_data = random.sample(st.session_state.raw_parsed_data, selected_qs)
        st.session_state.resume_pin = str(random.randint(1000, 9999))
        st.session_state.page = "quiz"
        st.rerun()

# --- 9. RENDER VIEWS ---
def render_home():
    st.markdown('<div class="top-bar"><h2>📚 CBT Topic Hub</h2></div>', unsafe_allow_html=True)
    
    with st.expander("🔄 Did you accidentally close the app? Resume Quiz Here", expanded=True):
        st.write("Enter the 4-digit Recovery PIN you were given during your test to restore your progress.")
        col1, col2 = st.columns([1, 2])
        with col1:
            entered_pin = st.text_input("Enter 4-Digit PIN", max_chars=4, placeholder="e.g., 4921")
            if st.button("Resume My Quiz", type="primary"):
                sessions = get_global_sessions()
                if entered_pin in sessions:
                    saved = sessions[entered_pin]
                    st.session_state.selected_topic_file = saved['file']
                    st.session_state.current_q_index = saved['q_index']
                    st.session_state.user_answers = saved['answers']
                    st.session_state.time_per_question = saved['time']
                    st.session_state.max_questions = saved['max_qs']
                    st.session_state.quiz_data = saved['quiz_data'] 
                    st.session_state.resume_pin = entered_pin
                    st.session_state.page = "quiz"
                    st.rerun()
                else:
                    st.error("PIN not found or the 5-hour session expired.")
    
    st.write("---")
    st.write("Select a topic below to start a new practice session.")
    
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
                st.session_state.current_q_index = 0
                st.session_state.user_answers = {}
                with st.spinner(f"Loading Database for {topic_name}..."):
                    parsed_data, is_json = load_and_auto_save_quiz_data(file_name)
                    if parsed_data:
                        st.session_state.raw_parsed_data = parsed_data
                        setup_dialog(file_name, len(parsed_data), is_json)
                    else:
                        st.error(f"Could not load {file_name}. Ensure it is uploaded to your GitHub repository!")

def render_quiz():
    save_state_to_cloud()
    q_index = st.session_state.current_q_index
    q_data = st.session_state.quiz_data[q_index]
    total_qs = len(st.session_state.quiz_data)

    col_sect, col_lang, col_qnum = st.columns([2, 1, 1], vertical_alignment="center")
    with col_sect: 
        st.markdown(f"##### {st.session_state.selected_topic_file.replace('.pdf', '')}")
        st.markdown(f"<span style='color:#ef4444; font-weight:bold;'>Save this PIN to resume if closed: {st.session_state.resume_pin}</span>", unsafe_allow_html=True)
    with col_lang:
        st.session_state.app_lang = st.selectbox("Language", ["Bilingual", "English", "Hindi"], label_visibility="collapsed")
    with col_qnum: 
        st.markdown(f"##### Q {q_index + 1} / {total_qs}")
    st.divider()

    inject_timer(st.session_state.time_per_question, q_index)

    filtered_question = filter_text(q_data["question"], st.session_state.app_lang, is_option=False)
    safe_question = filtered_question.replace('<', '&lt;').replace('>', '&gt;')
    st.info(f"**Q{q_index + 1}.** *(From Database Q{q_data['id']})*\n\n{safe_question}")
    
    current_response = st.session_state.user_answers.get(q_index, None)
    selected_option = st.radio("Select an option:", q_data["options"], 
                               format_func=lambda x: filter_text(x, st.session_state.app_lang, is_option=True).replace('<', '&lt;').replace('>', '&gt;'), 
                               key=f"q_{q_index}", 
                               index=q_data["options"].index(current_response) if current_response in q_data["options"] else None)
    
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if q_index > 0:
            if st.button("Previous", use_container_width=True):
                if selected_option: st.session_state.user_answers[q_index] = selected_option
                st.session_state.current_q_index -= 1
                st.rerun()
    with col3:
        if q_index < total_qs - 1:
            if st.button("Next", type="primary", use_container_width=True):
                if selected_option: st.session_state.user_answers[q_index] = selected_option
                st.session_state.current_q_index += 1
                st.rerun()
        else:
            if st.button("Submit Test", type="primary", use_container_width=True):
                if selected_option: st.session_state.user_answers[q_index] = selected_option
                sessions = get_global_sessions()
                if st.session_state.resume_pin in sessions:
                    del sessions[st.session_state.resume_pin]
                st.session_state.page = "analysis"
                st.rerun()

    st.divider()
    
    # --- LIVE EDITOR PANEL ---
    with st.expander("✏️ Admin: Notice a mistake? Edit this Question permanently"):
        st.warning("Any changes made here will be permanently saved to the .json database.")
        new_q = st.text_area("Question Text", value=q_data["question"], height=150)
        
        c_opt1, c_opt2 = st.columns(2)
        with c_opt1:
            new_opt_a = st.text_input("Option A", value=q_data["options"][0])
            new_opt_b = st.text_input("Option B", value=q_data["options"][1])
        with c_opt2:
            new_opt_c = st.text_input("Option C", value=q_data["options"][2])
            new_opt_d = st.text_input("Option D", value=q_data["options"][3])
            
        new_ans = st.selectbox("Correct Answer", [new_opt_a, new_opt_b, new_opt_c, new_opt_d], 
                               index=[new_opt_a, new_opt_b, new_opt_c, new_opt_d].index(q_data["answer"]) if q_data["answer"] in [new_opt_a, new_opt_b, new_opt_c, new_opt_d] else 0)
        new_exp = st.text_area("Explanation", value=q_data["explanation"])
        
        if st.button("💾 Save Fixes to Database", type="primary"):
            updated_q = {
                "id": q_data["id"],
                "question": new_q,
                "options": [new_opt_a, new_opt_b, new_opt_c, new_opt_d],
                "answer": new_ans,
                "explanation": new_exp
            }
            # Update memory so it changes instantly
            st.session_state.quiz_data[q_index] = updated_q
            # Permanently update the JSON file on the server
            if update_question_in_database(st.session_state.selected_topic_file, updated_q):
                st.success("✅ Fix saved! The database is permanently updated.")
                time.sleep(1)
                st.rerun()

def render_analysis():
    st.title("📊 Exam Analysis")
    total_qs = len(st.session_state.quiz_data)
    correct_count = sum(1 for i, q in enumerate(st.session_state.quiz_data) if st.session_state.user_answers.get(i) == q["answer"])
            
    accuracy = (correct_count / total_qs) * 100 if total_qs > 0 else 0
    st.metric("Total Score", f"{correct_count} / {total_qs}", f"{accuracy:.1f}% Accuracy")
    
    if st.button("🏠 Go to Home Page", type="primary"):
        st.session_s
