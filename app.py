import streamlit as st
import re
import time
import json

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="Professional RRB/OJEE CBT", layout="wide", initial_sidebar_state="expanded")

# --- 2. ADVANCED CSS INJECTION (The "Exact UI") ---
# We inject comprehensive CSS to handle fixed positioning, coloring, and specific CBT component styling.
def inject_cbt_css():
    st.markdown("""
        <style>
        /* Base styles */
        .stApp { background-color: #f0f2f5; font-family: 'Open Sans', 'Helvetica Neue', Helvetica, Arial, sans-serif; margin: 0; padding: 0;}
        header { visibility: hidden; } # Main streamlit header hide
        [data-testid="stSidebar"] { background-color: white; border-right: 1px solid #ddd; padding-top: 60px; } /* Adjust for top bar */

        /* TOP HEADER ZONE (Fixed) */
        .cbt-top-header { position: fixed; top: 0; left: 0; right: 0; height: 50px; background-color: #1e3a8a; color: white; display: flex; align-items: center; padding: 0 20px; z-index: 1000; box-shadow: 0 2px 4px rgba(0,0,0,0.1); font-weight: bold;}
        .top-timer { margin-left: auto; color: #ef4444; font-size: 1.2em;}
        
        /* SECTION TABS ZONE (Fixed below header) */
        .cbt-sections { position: fixed; top: 50px; left: 0; right: 0; height: 40px; background-color: white; display: flex; align-items: center; padding: 0 20px; z-index: 999; border-bottom: 1px solid #ddd;}
        .section-tab { padding: 8px 15px; cursor: pointer; border-bottom: 3px solid transparent; color: #555; font-weight: 500;}
        .section-tab.active { border-bottom: 3px solid #ef4444; color: #ef4444; font-weight: 700;}

        /* MAIN CONTENT AREA (Scrollable) */
        [data-testid="block-container"] { padding-top: 100px; padding-bottom: 60px; padding-left: 20px; padding-right: 20px;} /* Spacing for fixed header/footer */
        .question-meta { display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 0.9em; color: #666; font-weight: bold;}
        .mark-positive { color: #16a34a; } .mark-negative { color: #dc2626; }
        .question-box { background-color: white; padding: 25px; border-radius: 5px; border: 1px solid #ddd; }
        .bilingual-eng { font-weight: bold; font-size: 1.1em; color: black; margin-bottom: 15px;}
        .bilingual-hindi { color: #444; font-size: 1.05em;}

        /* QUESTION PALETTE (Sidebar) */
        .sidebar-title { font-weight: bold; color: #333; margin-bottom: 15px; display: block; padding: 0 10px;}
        .palette-container { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; padding: 10px;}
        
        .q-tile { display: flex; align-items: center; justify-content: center; width: 40px; height: 40px; border-radius: 50% 50% 0 0; background-color: #e5e7eb; color: #555; font-weight: bold; cursor: pointer; font-size: 0.9em;}
        /* Status Colors per picture */
        .q-tile.answered { background-color: #22c55e; color: white; border-radius: 50%;} /* Round green */
        .q-tile.marked { background-color: #a855f7; color: white; border-radius: 50% 50% 0 0;} /* Purple shape */
        .q-tile.marked-answered { background-color: #a855f7; color: white; border-radius: 50% 50% 0 0; position: relative;} 
        .q-tile.marked-answered::after { content: '✓'; color: #22c55e; position: absolute; bottom: -5px; right: 0px; font-weight: bold; font-size: 1.2em;}
        .q-tile.not-answered { background-color: #ef4444; color: white; border-radius: 0 0 50% 50%;} /* Red shape */
        .q-tile.active-q { border: 3px solid #1e3a8a; } /* Blue highlight for current Q */

        /* BOTTOM NAV ZONE (Fixed) */
        .cbt-bottom-nav { position: fixed; bottom: 0; left: 0; right: 0; height: 55px; background-color: white; display: flex; align-items: center; padding: 0 20px; z-index: 1000; border-top: 1px solid #ddd;}
        /* Force Streamlit buttons to look like CBT buttons in this footer */
        div[data-testid="stColumn"] button { width: 100%; border-radius: 3px;}
        
        </style>
    """, unsafe_allow_html=True)

# --- 3. INITIALIZE COMPLEX STATE ---
def initialize_state():
    if 'test_data' not in st.session_state:
        # Complex data structure: Sections containing questions
        st.session_state.test_data = {
            "Arithmetic": [
                {"id": 1, "marks": "+1.0, -0.25", "q_eng": "Question 1 in English", "q_hindi": "प्रश्न 1 हिंदी में", "options": ["A", "B", "C", "D"], "correct": "A"},
                {"id": 2, "marks": "+1.0, -0.25", "q_eng": "Question 2 in English", "q_hindi": "प्रश्न 2 हिंदी में", "options": ["A", "B", "C", "D"], "correct": "B"},
                # ... add more to make 20
            ],
            "General Awareness": [
                {"id": 3, "marks": "+1.0, -0.25", "q_eng": "GA Question 3 English", "q_hindi": "जीए प्रश्न 3 हिंदी", "options": ["A", "B", "C", "D"], "correct": "C"}
            ]
        }
        # Status Map: Stores user state for every single question number
        # Possible states: 'Not Visited', 'Answered', 'Not Answered', 'Marked for Review', 'Marked & Answered'
        # We also need a reverse map from global QID to section index
        st.session_state.status_map = {}
        st.session_state.section_map = {} # To find which section Q1 belongs to
        counter = 1
        for sec_name, questions in st.session_state.test_data.items():
            for i, q in enumerate(questions):
                st.session_state.status_map[counter] = 'Not Visited'
                st.session_state.section_map[counter] = {"section": sec_name, "index_in_section": i}
                counter += 1
        st.session_state.total_questions = counter - 1
        
    if 'current_global_q' not in st.session_state: st.session_state.current_global_q = 1
    if 'user_responses' not in st.session_state: st.session_state.user_responses = {}
    if 'test_active' not in st.session_state: st.session_state.test_active = True
    if 'remaining_time' not in st.session_state: st.session_state.remaining_time = 3600 # 1 hour dummy

# --- 4. RENDER UI COMPONENTS ---

def render_fixed_header():
    # Renders the absolute top bar with test name, icons, and timer snippet
    timer_text = time.strftime('%H:%M:%S', time.gmtime(st.session_state.remaining_time))
    st.markdown(f'''
        <div class="cbt-top-header">
            <div>RRB ALP Mock Test 1</div>
            <div style="margin-left: 20px;">⏱ Total Time: 60 min</div>
            <div class="top-timer">{timer_text}</div>
            <div style="margin-left: 15px; cursor:pointer;">💾</div>
            <div style="margin-left: 15px; cursor:pointer;">➕➖</div>
        </div>
    ''', unsafe_allow_html=True)

def render_section_tabs():
    # Renders section tabs below header. Detects active section.
    current_q_info = st.session_state.section_map[st.session_state.current_global_q]
    active_section = current_q_info["section"]
    
    tabs_html = '<div class="cbt-sections">'
    for sec_name in st.session_state.test_data.keys():
        active_class = "active" if sec_name == active_section else ""
        tabs_html += f'<div class="section-tab {active_class}">{sec_name}</div>'
    tabs_html += '</div>'
    st.markdown(tabs_html, unsafe_allow_html=True)

def render_sidebar_palette():
    # Renders the complex 1-20 palette in the sidebar with dynamic coloring
    with st.sidebar:
        st.markdown('<span class="sidebar-title">Question Palette</span>', unsafe_allow_html=True)
        
        # Legend (as seen in picture)
        # Note: Implementing specific shape/color CSS in legend too if wanted. Simple legend for now.
        st.write("🟩 Answered | 🟥 Not Answered | ⬜ Not Visited | 🟪 Marked")
        
        st.divider()
        
        palette_html = '<div class="palette-container">'
        for qid in range(1, st.session_state.total_questions + 1):
            status = st.session_state.status_map[qid]
            active_class = "active-q" if qid == st.session_state.current_global_q else ""
            
            # Match class from inject_cbt_css based on state
            css_class = ""
            if status == 'Answered': css_class = "answered"
            elif status == 'Not Answered': css_class = "not-answered"
            elif status == 'Marked for Review': css_class = "marked"
            elif status == 'Marked & Answered': css_class = "marked-answered"
            # Not Visited stays default light gray
            
            palette_html += f'<div class="q-tile {css_class} {active_class}">{qid}</div>'
        palette_html += '</div>'
        
        st.markdown(palette_html, unsafe_allow_html=True)
        
        st.divider()
        if st.button("Submit Group"):
            st.session_state.test_active = False
            st.rerun()

def render_main_question_area():
    # Main content zone with bilingual stacked questions
    qid = st.session_state.current_global_q
    q_info = st.session_state.section_map[qid]
    q_data = st.session_state.test_data[q_info["section"]][q_info["index_in_section"]]
    
    # Meta row (Marks, Q Number)
    col_meta1, col_meta2 = st.columns([1,1])
    with col_meta1:
        st.markdown(f"**Q {qid}**")
    with col_meta2:
        st.markdown(f'<div style="text-align:right;">Marks: <span class="mark-positive">{q_data["marks"].split(",")[0]}</span>, <span class="mark-negative">{q_data["marks"].split(",")[1]}</span> | <span style="color:#1e3a8a; cursor:pointer;">⚠️ Report</span></div>', unsafe_allow_html=True)
    
    st.divider()

    # Question Box (Bilingual Stacked)
    question_html = f'''
        <div class="question-box">
            <div class="bilingual-eng">Question:<br>{q_data["q_eng"]}</div>
            <div class="bilingual-hindi">प्रश्न:<br>{q_data["q_hindi"]}</div>
        </div>
    '''
    st.markdown(question_html, unsafe_allow_html=True)
    
    # Options (Radio Buttons below question box)
    options = q_data["options"]
    current_response = st.session_state.user_responses.get(qid, None)
    
    st.write("##### Choose Answer:")
    selected = st.radio("Options", options, index=options.index(current_response) if current_response else None, label_visibility="collapsed", key=f"global_radio_{qid}")
    
    # Update state temporarily while they are on the question
    if selected:
        st.session_state.user_responses[qid] = selected

def render_fixed_footer_nav():
    # Renders the bottom fixed bar with action buttons
    qid = st.session_state.current_global_q
    total_qs = st.session_state.total_questions
    
    st.markdown('<div class="cbt-bottom-nav">', unsafe_allow_html=True)
    
    # Use Streamlit columns inside the fixed footer via specific positioning hacks in CSS
    nav_cols = st.columns([2, 1, 1, 1, 1, 1]) # Adjust spacing
    
    # Logic for button clicks to update the Palette status map
    with nav_cols[2]:
        if st.button("Clear Response"):
            if qid in st.session_state.user_responses:
                del st.session_state.user_responses[qid]
                st.session_state.status_map[qid] = 'Not Answered'
                st.rerun()
                
    with nav_cols[3]:
        if st.button("Mark for Review"):
            has_answered = qid in st.session_state.user_responses
            st.session_state.status_map[qid] = 'Marked & Answered' if has_answered else 'Marked for Review'
            
            # Auto save & next logic after marking
            if qid < total_qs: st.session_state.current_global_q += 1
            st.rerun()
            
    with nav_cols[5]:
        # Identify as "Save & Next" per picture
        if st.button("Save & Next", type="primary"):
            has_answered = qid in st.session_state.user_responses
            
            # Update status map color
            st.session_state.status_map[qid] = 'Answered' if has_answered else 'Not Answered'
            
            # Move to next global question
            if qid < total_qs:
                st.session_state.current_global_q += 1
            else:
                st.toast("Last Question reached")
            st.rerun()
            
    st.markdown('</div>', unsafe_allow_html=True)

# --- 5. MAIN EXECUTION FLOW ---

def main():
    inject_cbt_css()
    initialize_state()
    
    if st.session_state.test_active:
        # Mandatory zones per CBT picture
        render_fixed_header()
        render_section_tabs()
        render_sidebar_palette()
        
        render_main_question_area()
        
        render_fixed_footer_nav() # NAVIGATION CONTROL CENTER
        
    else:
        st.title("Test Submitted")
        st.metric("Total Score (Mock)", f"{len(st.session_state.user_responses)} / {st.session_state.total_questions}")
        st.write("Analysis dashboard would load here.")
        if st.button("Restart"):
            st.session_state.clear()
            st.rerun()

if __name__ == "__main__":
    main()
    
