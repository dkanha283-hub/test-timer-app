import streamlit as st
import time
import os
import random
import json
import backend as bk 
import session_manager as sm # Imports your new 24-hour code system

# --- 1. SETUP & SESSION STATE ---
st.set_page_config(page_title="Pro CBT Hub", layout="wide", initial_sidebar_state="collapsed")
bk.inject_custom_css()

# Sync current progress with the 24-hour session manager
def update_24h_session():
    if 'resume_pin' in st.session_state and st.session_state.get('page') == 'quiz':
        state_data = {
            "file": st.session_state.selected_topic_file, "q_index": st.session_state.current_q_index,
            "answers": st.session_state.user_answers.copy(), "time": st.session_state.time_per_question,
            "max_qs": st.session_state.max_questions, "quiz_data": st.session_state.quiz_data
        }
        sm.save_session(st.session_state.resume_pin, state_data)

defaults = {
    'page': "home", 'selected_topic_file': None, 'quiz_data': [], 
    'current_q_index': 0, 'user_answers': {}, 'time_per_question': 60, 
    'max_questions': 10, 'app_lang': "Bilingual",
    'clipboard': None, 'active_menu_file': None, 'confirm_delete': False
}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# --- 2. POPUPS / DIALOGS ---
@st.dialog("⚙️ Options Menu")
def file_options_dialog(file_path, library):
    filename_display = os.path.basename(file_path).replace('.json', '').replace('_', ' ')
    st.markdown(f"### 📄 {filename_display}")
    st.write("---")

    with st.expander("✏️ Rename", expanded=False):
        new_name = st.text_input("New Name:", value=filename_display)
        if st.button("Save Rename", type="primary", use_container_width=True):
            new_path = os.path.join(os.path.dirname(file_path), new_name.replace(" ", "_") + ".json")
            if file_path != new_path:
                with open(file_path, 'r', encoding='utf-8') as f: data = json.load(f)
                with open(new_path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)
                os.remove(file_path); bk.github_save(new_path, data); bk.github_delete(file_path)
                st.cache_data.clear() 
                st.session_state.active_menu_file = None
                bk.play_feedback('success'); st.rerun()

    if st.button("📋 Copy to Clipboard", use_container_width=True):
        st.session_state.clipboard = file_path
        st.session_state.active_menu_file = None
        bk.play_feedback('success'); st.toast(f"Copied!"); st.rerun()

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
                    os.remove(file_path); bk.github_save(new_path, data); bk.github_delete(file_path)
                    st.cache_data.clear()
                    st.session_state.active_menu_file = None
                    bk.play_feedback('success'); st.rerun()

    st.write("---")
    if not st.session_state.confirm_delete:
        if st.button("🗑️ Delete", use_container_width=True):
            st.session_state.confirm_delete = True
            bk.play_feedback('warning')
            st.rerun()
            
    if st.session_state.confirm_delete:
        st.error("⚠️ Are you sure? This will delete the file from the Cloud permanently.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Cancel"): st.session_state.confirm_delete = False; st.rerun()
        with col2:
            if st.button("🚨 YES, DELETE", type="primary"):
                os.remove(file_path); bk.github_delete(file_path)
                st.cache_data.clear()
                st.session_state.active_menu_file = None
                st.session_state.confirm_delete = False
                bk.play_feedback('success'); st.rerun()

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
        
        # Generate and save a new PIN to the 24-hour physical file
        st.session_state.resume_pin = sm.generate_pin()
        st.session_state.page = "quiz"
        st.rerun()

# --- 3. VIEWS ---
def render_home():
    library = bk.get_library()
    
    action = st.text_input("JS_ACTION_BRIDGE", key="js_action_bridge", label_visibility="hidden")
    if action.startswith("MENU:"):
        st.session_state.js_action_bridge = "" 
        raw_text = action.replace("MENU:", "")
        clean_action = re.sub(r'[⚡📄\s]', '', raw_text).lower()
        
        target_path = None
        for folder, files in library.items():
            for name, path in files.items():
                if re.sub(r'[\s]', '', name).lower() == clean_action: 
                    target_path = path; break
            if target_path: break
        
        if target_path:
            st.session_state.active_menu_file = target_path
            st.session_state.confirm_delete = False
        st.rerun()

    if st.session_state.get('active_menu_file'):
        file_options_dialog(st.session_state.active_menu_file, library)

    st.markdown('<div class="top-bar"><h2 style="margin:0; font-weight:800;">📚 Pro CBT Hub</h2></div>', unsafe_allow_html=True)
    
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
                    raw_data = bk.parse_pdf_to_raw_data(new_pdf)
                    if raw_data:
                        os.makedirs(selected_folder, exist_ok=True)
                        file_path = os.path.join(selected_folder, new_topic_name.replace(" ", "_") + ".json")
                        with open(file_path, 'w', encoding='utf-8') as f: json.dump(raw_data, f, indent=4, ensure_ascii=False)
                        bk.github_save(file_path, raw_data)
                        st.cache_data.clear()
                        bk.play_feedback('success'); st.success("✅ Success!"); time.sleep(1); st.rerun()
                    else: st.error("Failed to parse PDF.")
            else: st.warning("Please complete all fields.")
    
    with st.expander("🔄 Resume Active Quiz (Valid 24h)", expanded=False):
        col1, col2 = st.columns([1, 2])
        with col1:
            entered_pin = st.text_input("Enter 4-Digit PIN", max_chars=4)
            if st.button("Resume My Quiz"):
                saved_session = sm.load_session(entered_pin)
                if saved_session:
                    st.session_state.selected_topic_file = saved_session['file']
                    st.session_state.current_q_index = saved_session['q_index']
                    # Convert string keys back to int for user_answers
                    st.session_state.user_answers = {int(k): v for k, v in saved_session['answers'].items()}
                    st.session_state.time_per_question = saved_session['time']
                    st.session_state.max_questions = saved_session['max_qs']
                    st.session_state.quiz_data = saved_session['quiz_data'] 
                    st.session_state.resume_pin = entered_pin
                    st.session_state.page = "quiz"; st.rerun()
                else: st.error("PIN not found or expired (over 24 hours).")

    st.write("---")
    
    if not library:
        st.info("Welcome to your Hub! Upload your first PDF above.")
    else:
        st.info("💡 **Pro Tip:** Press and Hold (or Right-Click) any topic to Rename, Copy, Move, or Delete it!")
        tabs = st.tabs(list(library.keys()))
        for idx, folder_name in enumerate(library.keys()):
            with tabs[idx]:
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
                            bk.github_save(new_path, data)
                            st.cache_data.clear()
                        st.session_state.clipboard = None 
                        bk.play_feedback('success'); st.rerun()
                
                st.markdown("<br>", unsafe_allow_html=True)
                cols = st.columns(3) 
                for c_idx, (topic_name, file_path) in enumerate(library[folder_name].items()):
                    with cols[c_idx % 3]:
                        icon = "⚡" if file_path.endswith('.json') else "📄"
                        if st.button(f"{icon} {topic_name}", key=f"start_{file_path}", use_container_width=True):
                            setup_dialog(file_path)
    
    bk.inject_long_press_bridge()

def render_quiz():
    # Save the current state to the 24-hour file!
    update_24h_session()
    
    q_index = st.session_state.current_q_index
    q_data = st.session_state.quiz_data[q_index]
    total_qs = len(st.session_state.quiz_data)
    edit_mode = st.session_state.get('edit_toggle', False)

    # VERY OBVIOUS 4-DIGIT PIN DISPLAY AT THE TOP!
    st.success(f"🔑 **YOUR RESUME PIN IS:** `{st.session_state.resume_pin}` (Valid for 24 Hours)")

    col_sect, col_lang, col_qnum = st.columns([2, 1, 1], vertical_alignment="center")
    with col_sect: 
        st.markdown(f"##### {os.path.basename(st.session_state.selected_topic_file).replace('.json', '').replace('_', ' ')}")
    with col_lang:
        st.session_state.app_lang = st.selectbox("Language", ["Bilingual", "English", "Hindi"], label_visibility="collapsed")
    with col_qnum: 
        st.markdown(f"##### Q {q_index + 1} / {total_qs}")
    st.divider()

    bk.inject_timer(st.session_state.time_per_question, q_index, is_paused=edit_mode, pin=st.session_state.resume_pin)

    safe_question = bk.filter_text(q_data["question"], st.session_state.app_lang, is_option=False).replace('<', '&lt;').replace('>', '&gt;')
    st.markdown(f'<div class="question-box"><b>Q{q_index + 1}.</b> *(DB Q{q_data["id"]})*<br><br>{safe_question}</div>', unsafe_allow_html=True)
    
    current_response = st.session_state.user_answers.get(q_index, None)
    selected_option = st.radio("Select an option:", q_data["options"], 
                               format_func=lambda x: bk.filter_text(x, st.session_state.app_lang, is_option=True).replace('<', '&lt;').replace('>', '&gt;'), 
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
                # Delete the PIN after completing the test
                sm.delete_session(st.session_state.resume_pin)
                st.session_state.page = "analysis"; bk.play_feedback('success'); st.rerun()

    st.divider()
    st.toggle("✏️ Edit this Question (PAUSES TIMER)", key="edit_toggle")
    if st.session_state.edit_toggle:
        st.info("Fixes made here will automatically be uploaded and saved to your GitHub repo!")
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
        
        if st.button("Save Fixes & Sync", type="primary", icon=":material/cloud_sync:"):
            updated_q = {"id": q_data["id"], "question": new_q, "options": [new_opt_a, new_opt_b, new_opt_c, new_opt_d], "answer": new_ans, "explanation": q_data["explanation"]}
            st.session_state.quiz_data[q_index] = updated_q
            with open(st.session_state.selected_topic_file, 'r', encoding='utf-8') as f: all_data = json.load(f)
            for i, q in enumerate(all_data):
                if q['id'] == updated_q['id']: all_data[i] = updated_q; break
            with open(st.session_state.selected_topic_file, 'w', encoding='utf-8') as f: json.dump(all_data, f, indent=4, ensure_ascii=False)
            bk.github_save(st.session_state.selected_topic_file, all_data)
            
            # --- THE FIX: Delete the memory so the toggle naturally resets ---
            del st.session_state['edit_toggle']
            bk.play_feedback('success')
            time.sleep(1)
            st.rerun()

def render_analysis():
    st.title("📊 Exam Analysis")
    total_qs = len(st.session_state.quiz_data)
    correct_count = sum(1 for i, q in enumerate(st.session_state.quiz_data) if st.session_state.user_answers.get(i) == q["answer"])
    accuracy = (correct_count / total_qs) * 100 if total_qs > 0 else 0
    st.metric("Total Score", f"{correct_count} / {total_qs}", f"{accuracy:.1f}% Accuracy")
    if st.button("🏠 Go to Home", type="primary"): st.session_state.clear(); st.rerun()
        
    st.session_state.app_lang = st.radio("Review Language", ["Bilingual", "English", "Hindi"], horizontal=True)
    for i, q in enumerate(st.session_state.quiz_data):
        disp_q = bk.filter_text(q['question'], st.session_state.app_lang, is_option=False).replace('<', '&lt;').replace('>', '&gt;')
        disp_ans = bk.filter_text(q['answer'], st.session_state.app_lang, is_option=True).replace('<', '&lt;').replace('>', '&gt;')
        disp_user = bk.filter_text(st.session_state.user_answers.get(i, 'Not Attempted'), st.session_state.app_lang, is_option=True).replace('<', '&lt;').replace('>', '&gt;')
        with st.expander(f"Q{i+1} (Database Q{q['id']})"):
            st.markdown(f"**Question:**\n\n {disp_q}"); st.write(f"**Your Answer:** {disp_user}"); st.write(f"**Correct Answer:** {disp_ans}"); st.success(q['explanation'])

if st.session_state.page == "home": render_home()
elif st.session_state.page == "quiz": render_quiz()
elif st.session_state.page == "analysis": render_analysis()
        
