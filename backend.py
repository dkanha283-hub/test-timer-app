import streamlit as st
import pdfplumber
import re
import os
import json

def inject_custom_css():
    st.markdown("""
        <style>
        /* 1. SMOOTH ANIMATIONS */
        @keyframes slideUpFade {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        /* 2. DYNAMIC GEOMETRIC BACKGROUND */
        .stApp { 
            font-family: 'Inter', '-apple-system', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; 
            background-color: var(--background-color);
            background-image: radial-gradient(var(--faded-text-color) 1px, transparent 1px);
            background-size: 30px 30px;
        }
        
        /* 3. GORGEOUS TOP BAR */
        .top-bar { 
            background: linear-gradient(135deg, var(--primary-color), #6366f1); 
            color: white; padding: 25px; border-radius: 16px; 
            display: flex; justify-content: space-between; align-items: center; 
            margin-bottom: 25px; box-shadow: 0 10px 30px rgba(99, 102, 241, 0.3);
            animation: slideUpFade 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
        .top-bar h2 { margin: 0; font-weight: 800; letter-spacing: -0.5px; }
        
        /* Hide defaults */
        header {visibility: hidden;}
        div[data-testid="stTextInput"] { display: none; }
        .stTextInput { display: block !important; }
        
        /* 4. MODERN QUESTION BOX WITH ANIMATION */
        .question-box { 
            background-color: var(--secondary-background-color); color: var(--text-color); 
            padding: 35px; border-radius: 16px; box-shadow: 0 8px 25px rgba(0,0,0,0.05); 
            margin-bottom: 25px; font-size: 18px; white-space: pre-wrap; line-height: 1.8; 
            border: 1px solid var(--faded-text-color);
            animation: slideUpFade 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
        
        /* 5. SMOOTH BUTTON HOVER EFFECTS */
        button[data-testid="baseButton-secondary"], button[data-testid="baseButton-primary"] {
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
            border-radius: 10px !important;
        }
        button[data-testid="baseButton-secondary"]:hover, button[data-testid="baseButton-primary"]:hover {
            transform: translateY(-3px);
            box-shadow: 0 6px 15px rgba(0,0,0,0.1) !important;
        }
        
        /* Smooth Expander Animation */
        div[data-testid="stExpander"] {
            animation: slideUpFade 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
            border-radius: 12px !important;
            border: 1px solid var(--faded-text-color) !important;
        }
        </style>
    """, unsafe_allow_html=True)

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

@st.cache_data 
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

def inject_timer(seconds, q_index, is_paused, pin):
    paused_str = "true" if is_paused else "false"
    html_code = f"""
    <div id="timer_display_{q_index}" style="font-size: 24px; font-weight: bold; text-align: right; animation: slideUpFade 0.5s ease forwards;"></div>
    <script>
        var current_q = {q_index}; var isPaused = {paused_str};
        var stored_q = sessionStorage.getItem('active_q_pin_{pin}');
        var timeLeft = (stored_q == current_q.toString() && sessionStorage.getItem('timeLeft_pin_{pin}')) ? parseInt(sessionStorage.getItem('timeLeft_pin_{pin}')) : {seconds};
        if(stored_q != current_q.toString()) {{ sessionStorage.setItem('active_q_pin_{pin}', current_q); sessionStorage.setItem('timeLeft_pin_{pin}', timeLeft); }}
        
        var timerElem = document.getElementById('timer_display_{q_index}');
        
        // Timer icon integration
        const pauseIcon = `<span style="font-size: 20px; vertical-align: middle;">⏸️</span>`;
        const activeIcon = `<span style="font-size: 20px; vertical-align: middle;">⏳</span>`;
        
        timerElem.innerHTML = (isPaused ? pauseIcon : activeIcon) + " Time Left: " + timeLeft + "s";
        timerElem.style.color = isPaused ? "#f59e0b" : "#ef4444"; 
        
        var timerId = setInterval(function() {{
            if (isPaused) return; 
            if (timeLeft <= 0) {{
                clearTimeout(timerId);
                window.parent.document.querySelectorAll('button').forEach(btn => {{ if(btn.innerText === 'Next' || btn.innerText === 'Submit Test') btn.click(); }});
            }} else {{
                timeLeft--; timerElem.innerHTML = activeIcon + " Time Left: " + timeLeft + "s";
                sessionStorage.setItem('timeLeft_pin_{pin}', timeLeft);
            }}
        }}, 1000);
    </script>
    """
    st.components.v1.html(html_code, height=50)
