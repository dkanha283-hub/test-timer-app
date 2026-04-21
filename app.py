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

# --- 2. GITHUB CLOUD SYNC ENGINE ---
def sync_to_github(file_name, json_data):
    """Automatically pushes the JSON database to your GitHub Repository."""
    try:
        if "GITHUB_TOKEN" not in st.secrets or "GITHUB_REPO" not in st.secrets:
            st.toast("⚠️ GitHub Secrets not found. Saved locally, but not pushed to cloud.")
            return False
            
        from github import Github
        g = Github(st.secrets["GITHUB_TOKEN"])
        repo = g.get_repo(st.secrets["GITHUB_REPO"])
        
        json_str = json.dumps(json_data, indent=4, ensure_ascii=False)
        
        try:
            contents = repo.get_contents(file_name)
            repo.update_file(contents.path, f"Auto-sync updated {file_name}", json_str, contents.sha)
            st.toast("☁️ Successfully synced updates to GitHub!")
        except:
            repo.create_file(file_name, f"Auto-sync created {file_name}", json_str)
            st.toast("☁️ New JSON Database successfully created in GitHub!")
        return True
    except Exception as e:
        st.toast(f"❌ GitHub Sync Error: Ensure secrets are correct. Error: {e}")
        return False

# --- 3. GLOBAL CLOUD SESSION STORE ---
@st.cache_resource
def get_global_sessions():
    return {}

def save_state_to_cloud():
    sessions = get_global_sessions()
    now = time.time()
    expired = [pin for pin, data in sessions.items() if (now - data['timestamp']) > 18000]
    for pin in expired: del sessions[pin]
        
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

# --- 4. SESSION STATE MANAGEMENT ---
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

# --- 5. BACKEND CONVERTER ENGINE (PDF -> DICT) ---
def parse_pdf_to_raw_data(file_input):
    extracted_text = ""
    try:
        if isinstance(file_input, str):
            if not os.path.exists(file_input): return []
            pdf_source = file_input
        else:
            pdf_source = file_input

        with pdfplumber.open(pdf_source) as pdf:
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
        st.error(f"Parsing error: {e}")
        return []

# --- 6. AUTOMATIC JSON MANAGER ---
def load_and_auto_save_quiz_data(filename):
    if filename.endswith('.json'):
        json_filename = filename
        pdf_filename = filename.replace('.json', '.pdf')
    else:
        json_filename = filename.replace('.pdf', '.json')
        pdf_filename = filename
    
    if os.path.exists(json_filename):
        with open(json_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data, True
        
    data = parse_pdf_to_raw_data(pdf_filename)
    if data:
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        sync_to_github(json_filename, data)
        
    return data, False

def update_question_in_database(file_name, updated_q):
    json_filename = file_name.replace('.pdf', '.json')
    try:
        with open(json_filename, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
            
        for i, q in enumerate(all_data):
            if q['id'] == updated_q['id']:
                all_data[i] = updated_q
                break
                
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=4, ensure_ascii=False)
            
        sync_to_github(json_filename, all_data)
        return True
    except Exception as e:
        st.error(f"Failed to update database: {e}")
        return False

# --- 7. SURGICAL LANGUAGE FILTER ---
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

# --- 8. SMART TIMER INJECTION (Supports Pausing and Memory) ---
def inject_timer(seconds, q_index, is_paused, pin):
    paused_str = "true" if is_paused else "false"
    html_code = f"""
    <div id="timer_display_{q_index}" style="font-size: 24px; font-weight: bold; text-align: right;"></div>
    <script>
        var current_q = {q_index};
        var isPaused = {paused_str};
        
        // Use sessionStorage so the timer survives Streamlit reruns
        var stored_q = sessionStorage.getItem('active_q_pin_{pin}');
        var timeLeft;
        
        if (stored_q == current_q.toString()) {{
            // If we are on the same question, resume exactly where we left off
            var savedTime = sessionStorage.getItem('timeLeft_pin_{pin}');
            timeLeft = savedTime !== null ? parseInt(savedTime) : {seconds};
        }} else {{
            // If this is a new question, start the timer fresh
            timeLeft = {seconds};
            sessionStorage.setItem('active_q_pin_{pin}', current_q);
            sessionStorage.setItem('timeLeft_pin_{pin}', timeLeft);
        }}

        var timerElem = document.getElementById('timer_display_{q_index}');
        if (isPaused) {{
            timerElem.innerHTML = "Time Left: " + timeLeft + "s ⏸️";
            timerElem.style.color = "#f59e0b"; // Orange when paused
        }} else {{
            timerElem.innerHTML = "Time Left: " + timeLeft + "s";
            timerElem.style.color = "#ef4444"; // Red when active
        }}

        var timerId = setInterval(countdown, 1000);
        function countdown() {{
            if (isPaused) return; // FREEZE TIMER IF PAUSED
            
            if (timeLeft <= 0) {{
                clearTimeout(timerId);
                var buttons = window.parent.document.querySelectorAll('button');
                buttons.forEach(function(btn) {{
                    if(btn.innerText === 'Next' || btn.innerText === 'Submit Test') btn.click();
                }});
            }} else {{
                timeLeft--;
                timerElem.innerHTML = "Time Left: " + timeLeft + "s";
                sessionStorage.setItem('timeLeft_pin_{pin}', timeLeft);
            }}
        }}
    </script>
    """
    st.components.v1.html(html_code, height=50)

# --- 9. SETUP POPUP (DIALOG WITH SHUFFLE) ---
@st.dialog("⚙️ Quiz Setup")
def setup_dialog(file_name, total_available, is_json):
    st.write(f"**Topic:** {file_name.replace('.pdf', '').replace('.json', '')}")
    if is_json:
        st.success("⚡ Loaded instantly from Database!")
    else:
        st.info("📄 PDF Scanned. New JSON Database automatically saved to your GitHub!")

    st.write(f"Total questions available: {total_available}")
    
    # Feature: Sequence vs Shuffle Selection
    order_choice = st.radio("Question Order:", ["In Sequence", "Shuffled"], horizontal=True)
    
    selected_qs = st.slider("How many questions to attempt?", min_value=1, max_value=total_available, value=min(20, total_available))
    timer_sec = st.number_input("Time per question (seconds)", min_value=10, max_value=300, value=60)
    
    if st.button("🚀 Start Quiz", type="primary", use_container_width=True):
        st.session_state.max_questions = selected_qs
        st.session_state.time_per_question = timer_sec
        
        if order_choice == "Shuffled":
            st.session_state.quiz_data = random.sample(st.session_state.raw_parsed_data, selected_qs)
        else:
            st.session_state.quiz_data = st.session_state.raw_parsed_data[:selected_qs]
            
        st.session_state.resume_pin = str(random.randint(1000, 9999))
        st.session_state.page = "quiz"
        st.rerun()

# --- 10. RENDER VIEWS ---
def render_home():
    st.markdown('<div class="top-bar"><h2>📚 CBT Topic Hub</h2></div>', unsafe_allow_html=True)
    
    with st.expander("🛠️ Admin: Add New Topic (Upload PDF)", expanded=False):
        st.write("Upload a new PDF. The app will convert it to a database, push it to GitHub, and instantly delete the PDF from memory!")
        new_pdf = st.file_uploader("Upload PDF Sheet", type="pdf")
        new_topic_name = st.text_input("Enter Topic Name (e.g., Geometry Part 2)")
        
        if st.button("Convert & Save to Cloud", type="primary"):
            if new_pdf and new_topic_name:
                with st.spinner("Extracting data and generating database..."):
                    raw_data = parse_pdf_to_raw_data(new_pdf)
                    if raw_data:
                        json_filename = new_topic_name.replace(" ", "_") + ".json"
                        with open(json_filename, 'w', encoding='utf-8') as f:
                            json.dump(raw_data, f, indent=4, ensure_ascii=False)
                        sync_to_github(json_filename, raw_data)
                        st.success(f"✅ Success! Database created and uploaded. PDF deleted from memory.")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("Failed to parse PDF. Ensure the format is correct.")
            else:
                st.warning("Please upload a PDF and enter a topic name.")
    
    with st.expander("🔄 Did you accidentally close the app? Resume Quiz Here", expanded=False):
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
    
    for f in os.listdir('.'):
        if f.endswith('.json'):
            is_legacy = False
            for t_name, t_file in topics.items():
                if t_file.replace('.pdf', '.json') == f:
                    is_legacy = True
                    break
            if not is_legacy:
                display_name = f.replace('.json', '').replace('_', ' ')
                topics[display_name] = f

    cols = st.columns(2)
    for idx, (topic_name, file_name) in enumerate(topics.items()):
        with cols[idx % 2]:
            icon = "⚡" if file_name.endswith('.json') or os.path.exists(file_name.replace('.pdf', '.json')) else "📄"
            if st.button(topic_name, use_container_width=True, icon=icon):
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
    
    # Check if Edit Mode is active to Pause Timer
    edit_mode = st.session_state.get('edit_toggle', False)

    col_sect, col_lang, col_qnum = st.columns([2, 1, 1], vertical_alignment="center")
    with col_sect: 
        display_title = st.session_state.selected_topic_file.replace('.pdf', '').replace('.json', '').replace('_', ' ')
        st.markdown(f"##### {display_title}")
        st.markdown(f"<span style='color:#ef4444; font-weight:bold;'>Save this PIN to resume if closed: {st.session_state.resume_pin}</span>", unsafe_allow_html=True)
    with col_lang:
        st.session_state.app_lang = st.selectbox("Language", ["Bilingual", "English", "Hindi"], label_visibility="collapsed")
    with col_qnum: 
        st.markdown(f"##### Q {q_index + 1} / {total_qs}")
    st.divider()

    # Inject smart timer with pause support
    inject_timer(st.session_state.time_per_question, q_index, is_paused=edit_mode, pin=st.session_state.resume_pin)

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
    
    # --- LIVE EDITOR WITH PAUSE TOGGLE ---
    st.toggle("✏️ Admin: Notice a mistake? Edit this Question (PAUSES TIMER)", key="edit_toggle")
    
    if st.session_state.edit_toggle:
        st.warning("Fixes made here will automatically be uploaded and saved to your GitHub repo!")
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
        
        if st.button("💾 Save Fixes & Sync to Cloud", type="primary"):
            updated_q = {
                "id": q_data["id"],
                "question": new_q,
                "options": [new_opt_a, new_opt_b, new_opt_c, new_opt_d],
                "answer": new_ans,
                "explanation": new_exp
            }
            st.session_state.quiz_data[q_index] = updated_q
            if update_question_in_database(st.session_state.selected_topic_file, updated_q):
                st.success("✅ Fix saved! The database is permanently updated in GitHub.")
                st.session_state.edit_toggle = False # Turn off edit mode
                time.sleep(1.5)
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
        disp_q = filter_text(q['question'], st.session_state.app_lang, is_option=False).replace('<', '&lt;').replace('>', '&gt;')
        disp_ans = filter_text(q['answer'], st.session_state.app_lang, is_option=True).replace('<', '&lt;').replace('>', '&gt;')
        disp_user = filter_text(st.session_state.user_answers.get(i, 'Not Attempted'), st.session_state.app_lang, is_option=True).replace('<', '&lt;').replace('>', '&gt;')
        
        with st.expander(f"Q{i+1} (Database Q{q['id']})"):
            st.markdown(f"**Question:**\n\n {disp_q}")
            st.write(f"**Your Answer:** {disp_user}")
            st.write(f"**Correct Answer:** {disp_ans}")
            st.success(q['explanation'])

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
