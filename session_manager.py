import json
import os
import time
import random

SESSION_FILE = "active_sessions.json"

def _load_all():
    """Loads all active sessions from the physical hard drive."""
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r") as f:
                return json.load(f)
        except: return {}
    return {}

def _save_all(data):
    """Saves all active sessions to the physical hard drive."""
    with open(SESSION_FILE, "w") as f:
        json.dump(data, f)

def generate_pin():
    """Generates a random 4-digit PIN."""
    return str(random.randint(1000, 9999))

def save_session(pin, state_dict):
    """Saves the user's exact quiz progress for 24 hours."""
    sessions = _load_all()
    state_dict['timestamp'] = time.time()
    sessions[pin] = state_dict
    _save_all(sessions)

def load_session(pin):
    """Loads a quiz session if the PIN is correct and within 24 hours."""
    cleanup_sessions() # Clean old sessions first
    sessions = _load_all()
    return sessions.get(pin, None)

def delete_session(pin):
    """Deletes the session after the user submits the test."""
    sessions = _load_all()
    if pin in sessions:
        del sessions[pin]
        _save_all(sessions)

def cleanup_sessions():
    """Automatically deletes any session older than 24 hours (86,400 seconds)."""
    sessions = _load_all()
    now = time.time()
    active_sessions = {k: v for k, v in sessions.items() if (now - v.get('timestamp', 0)) < 86400}
    
    if len(active_sessions) != len(sessions):
        _save_all(active_sessions)
      
