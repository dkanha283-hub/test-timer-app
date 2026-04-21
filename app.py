import streamlit as st
import pdfplumber
import re
import time
import os
import random
import json

# --- 1. PAGE CONFIGURATION & MODERN UI/UX CSS ---
st.set_page_config(page_title="Pro CBT Hub", layout="wide", initial_sidebar_state="collapsed")

def inject_custom_css():
    st.markdown("""
        <style>
        /* Modern App Background & Typography */
        .stApp { font-family: 'Inter', '-apple-system', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
        
        /* Gorgeous Gradient Top Bar */
        .top-bar { 
            background: linear-gradient(135deg, var(--primary-color), #6366f1); 
            color: white; 
            padding: 20px; 
            border-radius: 16px; 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            margin-bottom: 20px;
            box-shadow: 0 10px 25px rgba(99, 102, 241, 0.2);
        }

        /* Hide default Streamlit elements */
        header {visibility: hidden;}
        div[data-testid="stTextInput"] { display: none; } /* Hide the JS Bridge */
        .stTextInput { display: block !important; } /* Keep normal text inputs visible */

        /* Modern Question Box */
        .question-box { 
            background-color: var(--secondary-background-color); 
            color: var(--text-color); 
            padding: 30px; 
            border-radius: 16px; 
            box-shadow: 0 4px 20px rgba(0,0,0,0.05); 
            margin-bottom: 20px; 
            font-size: 18px; 
            white-space: pre-wrap; 
            line-height: 1.7; 
            border: 1px solid var(--faded-text-color);
        }
        </style>
    """, unsafe_allow_html=True)

# --- 2. HAPTICS & RIGHT-CLICK / LONG-PRESS BRIDGE ---
def inject_long_press_bridge():
    """Listens for Desktop Right-Click OR Mobile Long-Press and triggers the Popup."""
    js_code = """
    <script>
        const inputs = window.parent.document.querySelectorAll('input');
        let actionBridge;
        inputs.forEach(i => { if(i.getAttribute('aria-label') === 'JS_ACTION_BRIDGE') actionBridge = i; });

        function triggerMenu(fileName) {
            if(actionBridge) {
                if(navigator.vibrate) navigator.vibrate(50); // Haptic Pop
                let nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                nativeInputValueSetter.call(actionBridge, "MENU:" + fileName);
                actionBridge.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }

        const buttons = window.parent.document.querySelectorAll('button');
        buttons.forEach(btn => {
            if(btn.innerText.includes('📄') || btn.innerText.includes('⚡')) {
                // Prevent default browser right-click menu
                btn.addEventListener('contextmenu', (e) => {
                    e.preventDefault();
                    triggerMenu(btn.innerText);
                });
                
                // Mobile Long Press Logic
                let timer;
                let isLongPress = false;
                
                btn.addEventListener('touchstart', (e) => {
                    isLongPress = false;
                    timer = setTimeout(() => {
                        isLongPress = true;
                        triggerMenu(btn.innerText);
                    }, 500); // 0.5 seconds hold
                }, {passive: true});
                
                btn.addEventListener('touchend', (e) => {
                    clearTimeout(timer);
                    if(isLongPress) {
                        e.preventDefault(); // Stop it from opening the quiz
                        e.stopPropagation();
                    }
                });
                btn.addEventListener('touchmove', () => clearTimeout(timer));
            }
        });
    </script>
    """
    st.components.v1.html(js_code, height=0)

def play_feedback(ftype="success"):
    js_code = f"""
    <script>
        try {{
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator(); const gain = ctx.createGain();
            osc.connect(gain); gain.connect(ctx.destination);
            if ('{ftype}' === 'success') {{
                if(navigator.vibrate) navigator.vibrate([100, 50, 100]);
                osc.frequency.setValueAtTime(400, ctx.currentTime); osc.frequency.exponentialRampToValueAtTime(800, ctx.currentTime + 0.15);
                gain.gain.setValueAtTime(0.2, ctx.currentTime); gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);
                osc.start(); osc.stop(ctx.currentTime + 0.15);
            }} else if ('{ftype}' === 'warning') {{
                if(navigator.vibrate) navigator.vibrate([50, 100, 50, 100]);
                osc.type = 'square'; osc.frequency.setValueAtTime(200, ctx.currentTime); osc.frequency.exponentialRampToValueAtTime(150, ctx.currentTime + 0.2);
                gain.gain.setValueAtTime(0.1, ctx.currentTime); gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.2);
                osc.start(); osc.stop(ctx.currentTime + 0.2);
            }}
        }} catch(e) {{}}
    </script>
    """
    st.components.v1.html(js_code, height=0)

# --- 3. GITHUB CLOUD SYNC ENGINE ---
def get_github_repo():
    if "GITHUB_TOKEN" not in st.secrets or "GITHUB_REPO" not in st.secrets: return None
    from github import Github
    return Github(st.secrets["GITHUB_TOKEN"]).get_repo(st.secrets["GITHUB_REPO"])

def github_save(file_path, json_data):
    repo = get_github_repo()
    if not repo: return False
    git_path = file_path.replace("\\", "/")
    json_str = json.dumps(json_data, indent=4, ensure_ascii=False)
    try:
        contents = repo.get_contents(git_path)
        repo.update_file(contents.path, f"Update {git_path}", json_str, contents.sha)
    except:
        repo.create_file(git_path, f"Create {git_path}", json_str)
    return True

def github_delete(file_path):
    repo = get_github_repo()
    if not repo: return False
    git_path = file_path.replace("\\", "/")
    try:
        contents = repo.get_contents(git_path)
        repo.delete_file(contents.path, f"Delete {git_path}", contents.sha)
        return True
    except: return False

# --- 4. DYNAMIC LIBRARY SCANNER ---
def get_library():
    library = {}
    ignore_dirs = {'.git', '.streamlit', 'venv', '__pycache__'}
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
        folder = os.path.basename(root)
        if root == '.': folder = "Uncategorized"
        for f in files:
            if f.endswith('.json'):
                if folder not in library: library[folder] = {}
                topic_name = f.replace('.json', '').replace('_', ' ')
                library[folder][topic_name] = os.path.join(root, f)
                
    sorted_library = {k: library[k] for k in sorted(library.keys()) if k != "Uncategorized"}
    if "Uncategorized" in library: sorted_library["Uncategorized"] = library["Uncategorized"]
    return sorted_library

# --- 5. SESSION INIT & CLOUD STORE ---
@st.cache_resource
def get_global_sessions(): return {}

def save_state_to_cloud():
    sessions = get_global_sessions()
    now = time.time()
    expired = [pin for pin, data in sessions.items() if (now - data['timestamp']) > 18000]
    for pin in expired: del sessions[pin]
    if 'resume_pin' in st.session_state:
        sessions[st.session_state.resume_pin] = {
            "file": st.session_state.selected_topic_file, "q_index": st.session_state.current_q_index,
            "answers": st.session_state.user_answers.copy(), "time": st.session_state.time_per_question,
            "max_qs": st.session_state.max_questions, "quiz_data": st.session_state.quiz_data, "timestamp": now
        }

def initialize_state():
    defaults = {
        'page': "home", 'selected_topic_file': None, 'quiz_data': [], 
        'current_q_index': 0, 'user_answers': {}, 'time_per_question': 60, 
        'max_questions': 10, 'app_lang': "Bilingual",
        'resume_pin': str(random.randint(1000, 9999)),
        'active_menu_file': None, 'clipboard': None, 'confirm_delete': False
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v

# --- 6. PDF TO JSON ENGINE ---
def parse_pdf_to_raw_data(pdf_source):
    extracted_text = ""
    try:
        if isinstance(pdf_source, str):
            if not os.path.exists(pdf_source): return []
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
            main_questions_text = clean_text; answer_key_text = ""
        
        correct_answers_dict = {}
        if answer_key_text:
            ak_text = answer_key_text.lower().replace('α', 'a')
            ans_matches = re.findall(r'(\d+)\s*\.?\s*[\(\[]\s*([a-d])\s*[\)\]]', ak_text)
            nums = re.findall(r'\b(\d+)\s*\.', ak_text)
            opts = re.findall(r'[\(\[]\s*([a-d])\s*[\)\]]', ak_text)
            if len(ans_matches) < len(opts) * 0.5: ans_matches = list(zip(nums, opts))
            for qnum, ans in ans_matches: correct_answers_dict[int(qnum)] = ans.upper()
        
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
            correct_text = locals().get(f"opt_{correct_letter.lower()}", opt_a)
            
            if question_text:
                quiz_data.append({"id": q_id, "question": question_text, "options": [opt_a, opt_b, opt_c, opt_d], "answer": correct_text, "explanation": f"Correct option is [{correct_letter}]."})
        return quiz_data
    except Exception as e: return []

def load_and_auto_save_quiz_data(filename):
    json_filename = filename.replace('.pdf', '.json') if filename.endswith('.pdf') else filename
    if os.path.exists(json_filename):
        with open(json_filename, 'r', encoding='utf-8') as f: return json.load(f), True
    data = parse_pdf_to_raw_data(filename)
    if data:
        with open(json_filename, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)
        github_save(json_filename, data)
    return data, False

def filter_text(text, lang, is_option=False):
    if not text or lang == "Bilingual": return text
    lines = text.split('\n'); filtered_lines = []
    for l in lines:
        if not l.strip(): continue
        has_hindi = bool(re.search(r'[\u0900-\u097F]', l))
        if lang == "English":
            if has_hindi:
                if is_option:
                    clean_l = re.sub(r'[\u0900-\u097F।]+', '', l).strip()
                    clean_l = re.sub(r'[\/\-\|\,]\s*$', '', clean_l).strip() 
                    if clean_l: filtered_lines.append(clean_l)
            else: filtered_lines.append(l)
        elif lang == "Hindi":
            if has_hindi or len(re.findall(r'\b[a-zA-Z]{3,}\b', l)) < 4: filtered_lines.append(l)
    return '\n'.join(filtered_lines).strip()

# --- 7. SMART TIMER INJECTION ---
def inject_timer(seconds, q_index, is_paused, pin):
    paused_str = "true" if is_paused else "false"
    html_code = f"""
    <div id="timer_display_{q_index}" style="font-size: 24px; font-weight: bold; text-align: right;"></div>
    <script>
        var current_q = {q_index}; var isPaused = {paused_str};
        var stored_q = sessionStorage.getItem('active_q_pin_{pin}');
        var timeLeft = (stored_q == current_q.toString() && sessionStorage.getItem('timeLeft_pin_{pin}')) ? parseInt(sessionStorage.getItem('timeLeft_pin_{pin}')) : {seconds};
        if(stored_q != current_q.toString()) {{ sessionStorage.setItem('active_q_pin_{pin}', current_q); sessionStorage.setItem('timeLeft_pin_{pin}', timeLeft); }}
        
        var timerElem = document.getElementById('timer_display_{q_index}');
        timerElem.innerHTML = "Time Left: " + timeLeft + "s" + (isPaused ? " ⏸️" : "");
        timerElem.style.color = isPaused ? "#f59e0b" : "#ef4444"; 
        
        var timerId = setInterval(function() {{
            if (isPaused) return; 
            if (timeLeft <= 0) {{
                clearTimeout(timerId);
                window.parent.document.querySelectorAll('button').forEach(btn => {{ if(btn.innerText === 'Next' || btn.innerText === 'Submit Test') btn.click(); }});
            }} else {{
                timeLeft--; timerElem.innerHTML = "Time Left: " + timeLeft + "s";
                sessionStorage.setItem('timeLeft_pin_{pin}', timeLeft);
            }}
        }}, 1000);
    </script>
    """
    st.components.v1.html(html_code, height=50)

# --- 8. POPUPS (LONG PRESS CONTEXT MENU & QUIZ SETUP) ---
@st.dialog("⚙️ Options Menu")
def file_options_dialog(file_path, library):
    """The Desktop-Style Popup that appears on Long Press / Right Click."""
    filename_display = os.path.basename(file_path).replace('.json', '').replace('_', ' ')
    st.markdown(f"### 📄 {filename_display}")
    st.write("---")

    # 1. RENAME
    with st.expander("✏️ Rename", expanded=False):
        new_name = st.text_input("New Name:", value=filename_display)
        if st.button("Save Rename", type="primary", use_container_width=True):
            new_path = os.path.join(os.path.dirname(file_path), new_name.replace(" ", "_") + ".json")
            if file_path != new_path:
                with open(file_path, 'r', encoding='utf-8') as f: data = json.load(f)
                with open(new_path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)
                os.remove(file_path); github_save(new_path, data); github_delete(file_path)
                st.session_state.active_menu_file = None
                play_feedback('success'); st.rerun()

    # 2. COPY
    if st.button("📋 Copy to Clipboard", use_container_width=True):
        st.session_state.clipboard = file_path
        st.session_state.active_menu_file = None
        play_feedback('success'); st.toast(f"Copied {filename_display}!"); st.rerun()

    # 3. MOVE
    with st.expander("📁 Move to Folder", expanded=False):
        folders = list(library.keys())
        if "Uncategorized" in folders: folders.remove("Uncategorized")
        folders.append("+ Create New Folder")
        target_folder = st.selectbox("Select Destination", folders)
        if target_folder == "+ Create New Folder": target_folder = st.text_input("New Folder Name").strip()
        
        if st.button("Confirm Move", type="primary", use_container_width=True):
            if target_folder:
                save_dir = "." if target_folder == "Uncategorized" else target_folder
                os.makedirs(save_dir, exist_ok=True)
                new_path = os.path.join(save_dir, os.path.basename(file_path))
                if file_path != new_path:
                    with open(file_path, 'r', encoding='utf-8') as f: data = json.load(f)
                    with open(new_path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)
                    os.remove(file_path); github_save(new_path, data); github_delete(file_path)
                    st.session_state.active_menu_file = None
                    play_feedback('success'); st.rerun()

    st.write("---")
    # 4. DELETE (With Warning State)
    if not st.session_state.confirm_delete:
        if st.button("🗑️ Delete", use_container_width=True):
            st.session_state.confirm_delete = True
            play_feedback('warning')
            st.rerun()
            
    if st.session_state.confirm_delete:
        st.error("⚠️ Are you sure? This will delete the file from the Cloud permanently.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Cancel"): 
                st.session_state.confirm_delete = False; st.rerun()
        with col2:
            if st.button("🚨 YES, DELETE", type="primary"):
                os.remove(file_path); github_delete(file_path)
                st.session_state.active_menu_file = None
                st.session_state.confirm_delete = False
                play_feedback('pop'); st.rerun()

@st.dialog("🚀 Quiz Setup")
def setup_dialog(file_path):
    st.write(f"**Topic:** {os.path.basename(file_path).replace('.json', '').replace('_', ' ')}")
    with open(file_path, 'r', encoding='utf-8') as f: raw_data = json.load(f)
    total_available = len(raw_data)
    
    order_choice = st.radio("Question Order:", ["In Sequence", "Shuffled"], horizontal=True)
    selected_qs = st.slider("How many questions to attempt?", min_value=1, max_value=total_available, value=min(20, total_available))
    timer_sec = st.number_input("Time per question (seconds)", min_value=10, max_value=300, value=60)
    
    if st.button("Start Quiz", type="primary", use_container_width=True):
        st.session_state.max_questions = selected_qs
        st.session_state.time_per_question = timer_sec
        st.session_state.quiz_data = random.sample(raw_data, selected_qs) if order_choice == "Shuffled" else raw_data[:selected_qs]
        st.session_state.selected_topic_file = file_path
        st.session_state.resume_pin = str(random.randint(1000, 9999))
        st.session_state.page = "quiz"; st.rerun()

# --- 9. RENDER VIEWS ---
def render_home():
    library = get_library()
    
    # --- CATCH JAVASCRIPT RIGHT-CLICK / LONG-PRESS EVENT ---
    action = st.text_input("JS_ACTION_BRIDGE", key="js_action_bridge", label_visibility="hidden")
    if action.startswith("MENU:"):
        topic_clean = re.sub(r'^[⚡📄]\s*', '', action.replace("MENU:", "")).strip()
        # Find path
        target_path = None
        for folder, files in library.items():
            for name, path in files.items():
                if name == topic_clean: target_path = path
        
        if target_path:
            st.session_state.active_menu_file = target_path
            st.session_state.confirm_delete = False # Reset delete warning
            # Clear the input so it doesn't loop
            st.components.v1.html("<script>window.parent.document.querySelector('input[aria-label=\"JS_ACTION_BRIDGE\"]').value = '';</script>", height=0)
            st.rerun()

    # Render the Context Menu Dialog if a file was held/right-clicked
    if st.session_state.get('active_menu_file'):
        file_options_dialog(st.session_state.active_menu_file, library)

    st.markdown('<div class="top-bar"><h2 style="margin:0; font-weight:800;">📚 Pro CBT Hub</h2></div>', unsafe_allow_html=True)
    
    # --- ADMIN UPLOAD PANEL ---
    with st.expander("📤 Upload New PDF to Hub", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            folder_options = list(library.keys()) if library else []
            if "Uncategorized" in folder_options: folder_options.remove("Uncategorized")
            folder_options.append("+ Create New Folder")
            selected_folder = st.selectbox("Select Target Folder", folder_options)
            if selected_folder == "+ Create New Folder": selected_folder = st.text_input("Enter New Folder Name").strip()
        with c2:
            new_topic_name = st.text_input("Enter Topic Name").strip()
            
        new_pdf = st.file_uploader("Upload PDF Sheet", type="pdf")
        if st.button("Convert & Save", type="primary"):
            if new_pdf and new_topic_name and selected_folder:
                with st.spinner("Generating database..."):
                    raw_data = parse_pdf_to_raw_data(new_pdf)
                    if raw_data:
                        os.makedirs(selected_folder, exist_ok=True)
                        file_path = os.path.join(selected_folder, new_topic_name.replace(" ", "_") + ".json")
                        with open(file_path, 'w', encoding='utf-8') as f: json.dump(raw_data, f, indent=4, ensure_ascii=False)
                        github_save(file_path, raw_data)
                        play_feedback('success'); st.success(f"✅ Success!"); time.sleep(1); st.rerun()
                    else: st.error("Failed to parse PDF.")
            else: st.warning("Please complete all fields.")
    
    # --- RESUME PIN ---
    with st.expander("🔄 Resume Active Quiz", expanded=False):
        col1, col2 = st.columns([1, 2])
        with col1:
            entered_pin = st.text_input("Enter 4-Digit PIN", max_chars=4)
            if st.button("Resume My Quiz"):
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
                    st.session_state.page = "quiz"; st.rerun()
                else: st.error("PIN not found or expired.")

    st.write("---")
    
    # --- LIBRARY DISPLAY ---
    if not library:
        st.info("Welcome to your Hub! Upload your first PDF above.")
    else:
        st.info("💡 **Pro Tip:** Right-Click (or Press and Hold) any topic to Rename, Copy, Move, or Delete it!")
        tabs = st.tabs(list(library.keys()))
        for idx, folder_name in enumerate(library.keys()):
            with tabs[idx]:
                # --- PASTE FUNCTIONALITY ---
                if st.session_state.clipboard:
                    cb_path = st.session_state.clipboard
                    cb_name = os.path.basename(cb_path).replace('.json', '').replace('_', ' ')
                    st.success(f"📋 **Ready to Paste:** {cb_name}")
                    if st.button(f"📥 Paste Here", key=f"paste_{folder_name}"):
                        save_dir = "." if folder_name == "Uncategorized" else folder_name
                        new_path = os.path.join(save_dir, os.path.basename(cb_path))
                        if cb_path != new_path:
                            with open(cb_path, 'r', encoding='utf-8') as f: data = json.load(f)
                            with open(new_path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)
                            github_save(new_path, data)
                        st.session_state.clipboard = None 
                        play_feedback('success'); st.rerun()
                
                st.markdown("<br>", unsafe_allow_html=True)
                cols = st.columns(3) 
                for c_idx, (topic_name, file_path) in enumerate(library[folder_name].items()):
                    with cols[c_idx % 3]:
                        icon = "⚡" if file_path.endswith('.json') else "📄"
                        if st.button(f"{icon} {topic_name}", key=f"start_{file_path}", use_container_width=True):
                            setup_dialog(file_path)
    
    # Inject JS to enable long-press and right-click
    inject_long_press_bridge()

def render_quiz():
    save_state_to_cloud()
    q_index = st.session_state.current_q_index
    q_data = st.session_state.quiz_data[q_index]
    total_qs = len(st.session_state.quiz_data)
    edit_mode = st.session_state.get('edit_toggle', False)

    col_sect, col_lang, col_qnum = st.columns([2, 1, 1], vertical_alignment="center")
    with col_sect: 
        st.markdown(f"##### {os.path.basename(st.session_state.selected_topic_file).replace('.json', '').replace('_', ' ')}")
    with col_lang:
        st.session_state.app_lang = st.selectbox("Language", ["Bilingual", "English", "Hindi"], label_visibility="collapsed")
    with col_qnum: 
        st.markdown(f"##### Q {q_index + 1} / {total_qs}")
    st.divider()

    inject_timer(st.session_state.time_per_question, q_index, is_paused=edit_mode, pin=st.session_state.resume_pin)

    safe_question = filter_text(q_data["question"], st.session_state.app_lang, is_option=False).replace('<', '&lt;').replace('>', '&gt;')
    st.markdown(f'<div class="question-box"><b>Q{q_index + 1}.</b> *(DB Q{q_data["id"]})*<br><br>{safe_question}</div>', unsafe_allow_html=True)
    
    current_response = st.session_state.user_answers.get(q_index, None)
    selected_option = st.radio("Select an option:", q_data["options"], 
                               format_func=lambda x: filter_text(x, st.session_state.app_lang, is_option=True).replace('<', '&lt;').replace('>', '&gt;'), 
                               key=f"q_{q_index}", 
                               index=q_data["options"].index(current_response) if current_response in q_data["options"] else None)
    
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if q_index > 0 and st.button("Previous", use_container_width=True):
            if selected_option: st.session_state.user_answers[q_index] = selected_option
            st.session_state.current_q_index -= 1; st.rerun()
    with col3:
        if q_index < total_qs - 1:
            if st.button("Next", type="primary", use_container_width=True):
                if selected_option: st.session_state.user_answers[q_index] = selected_option
                st.session_state.current_q_index += 1; st.rerun()
        else:
            if st.button("Submit Test", type="primary", use_container_width=True):
                if selected_option: st.session_state.user_answers[q_index] = selected_option
                sessions = get_global_sessions()
                if st.session_state.resume_pin in sessions: del sessions[st.session_state.resume_pin]
                st.session_state.page = "analysis"; play_feedback('success'); st.rerun()

    st.divider()
    st.toggle("✏️ Edit this Question (PAUSES TIMER)", key="edit_toggle")
    if st.session_state.edit_toggle:
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
        
        if st.button("💾 Save Fixes & Sync", type="primary"):
            updated_q = {"id": q_data["id"], "question": new_q, "options": [new_opt_a, new_opt_b, new_opt_c, new_opt_d], "answer": new_ans, "explanation": q_data["explanation"]}
            st.session_state.quiz_data[q_index] = updated_q
            with open(st.session_state.selected_topic_file, 'r', encoding='utf-8') as f: all_data = json.load(f)
            for i, q in enumerate(all_data):
                if q['id'] == updated_q['id']: all_data[i] = updated_q; break
            with open(st.session_state.selected_topic_file, 'w', encoding='utf-8') as f: json.dump(all_data, f, indent=4, ensure_ascii=False)
            github_save(st.session_state.selected_topic_file, all_data)
            st.session_state.edit_toggle = False; play_feedback('success'); time.sleep(1); st.rerun()

def render_analysis():
    st.title("📊 Exam Analysis")
    total_qs = len(st.session_state.quiz_data)
    correct_count = sum(1 for i, q in enumerate(st.session_state.quiz_data) if st.session_state.user_answers.get(i) == q["answer"])
    accuracy = (correct_count / total_qs) * 100 if total_qs > 0 else 0
    st.metric("Total Score", f"{correct_count} / {total_qs}", f"{accuracy:.1f}% Accuracy")
    if st.button("🏠 Go to Home", type="primary"): st.session_state.clear(); st.rerun()
        
    st.session_state.app_lang = st.radio("Review Language", ["Bilingual", "English", "Hindi"], horizontal=True)
    for i, q in enumerate(st.session_state.quiz_data):
        disp_q = filter_text(q['question'], st.session_state.app_lang, is_option=False).replace('<', '&lt;').replace('>', '&gt;')
        disp_ans = filter_text(q['answer'], st.session_state.app_lang, is_option=True).replace('<', '&lt;').replace('>', '&gt;')
        disp_user = filter_text(st.session_state.user_answers.get(i, 'Not Attempted'), st.session_state.app_lang, is_option=True).replace('<', '&lt;').replace('>', '&gt;')
        with st.expander(f"Q{i+1} (Database Q{q['id']})"):
            st.markdown(f"**Question:**\n\n {disp_q}"); st.write(f"**Your Answer:** {disp_user}"); st.write(f"**Correct Answer:** {disp_ans}"); st.success(q['explanation'])

def main():
    inject_custom_css(); initialize_state()
    if st.session_state.page == "home": render_home()
    elif st.session_state.page == "quiz": render_quiz()
    elif st.session_state.page == "analysis": render_analysis()

if __name__ == "__main__": main()
