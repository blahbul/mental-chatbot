# app.py - FINAL VERSION WITH MOOD TRACKER

import sys
import os
import google.generativeai as genai
import spacy
from flask import Flask, request, jsonify, render_template
from datetime import datetime
import json
import re # <-- For the "studies" fix
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# --- Initialize Libraries & Download NLTK Data ---
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("SpaCy model not found. Please run: python -m spacy download en_core_web_sm")
    sys.exit(1)
try:
    sid = SentimentIntensityAnalyzer()
except LookupError:
    print("NLTK VADER lexicon not found. Downloading...")
    nltk.download('vader_lexicon')
    sid = SentimentIntensityAnalyzer()

app = Flask(__name__)

# --- Directory Setup ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
HISTORY_DIR = os.path.join(BASE_DIR, 'history')
if not os.path.exists(HISTORY_DIR): os.makedirs(HISTORY_DIR)
JOURNAL_DIR = os.path.join(BASE_DIR, 'journals')
if not os.path.exists(JOURNAL_DIR): os.makedirs(JOURNAL_DIR)
MOOD_DIR = os.path.join(BASE_DIR, 'mood_data') # <-- For mood tracker
if not os.path.exists(MOOD_DIR): os.makedirs(MOOD_DIR)
STATIC_DIR = os.path.join(BASE_DIR, 'static')
if not os.path.exists(STATIC_DIR): os.makedirs(STATIC_DIR)

# --- Configure Gemini API ---
# ⚠️ IMPORTANT: Paste your actual API key below
API_KEY = "[YOUR_API_KEY_HERE]"
if API_KEY == "YOUR_API_KEY_HERE":
    print("ERROR: Please replace 'YOUR_API_KEY_HERE' with your actual Google AI API key in app.py")
genai.configure(api_key=API_KEY)

system_prompt = "You are a compassionate and understanding mental health support chatbot named Phoenix. You are a compassionate and understanding mental health support chatbot for students. Your purpose is to listen, provide empathetic responses, and offer helpful, non-clinical advice. You should always maintain a calm and encouraging tone. Focus your responses on common student issues like academic stress, social anxiety, burnout, and time management. Keep your responses brief, clear, and to the point. Do not give medical diagnoses or clinical advice. If a user expresses severe distress or suicidal thoughts, you must immediately refer them to a professional helpline or counselor." # (your full prompt)

# --- Core AI Logic (FIXED) ---
def generate_response(user_text):
    user_text_lower = user_text.lower()
    
    if re.search(r'\b(studies)\b', user_text_lower):
        print("DEBUG: Detected 'studies'. Bypassing safety check for 'die'.")
        try:
            model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=system_prompt)
            response = model.generate_content(user_text)
            return response.text
        except Exception as e:
            print(f"GEMINI API ERROR: {e}")
            return "I'm sorry, I'm having trouble connecting to the AI service right now."

    suicide_patterns = [
        r'\b(suicide)\b', r'\b(end my life)\b', r'\b(kill myself)\b',
        r'\b(die)\b', r'\b(hurting myself)\b', r'\b(self-harm)\b'
    ]
    for pattern in suicide_patterns:
        if re.search(pattern, user_text_lower):
            print(f"DEBUG: Triggered safety override with pattern: '{pattern}'")
            return "I'm really concerned about your safety. Please reach out immediately to a trusted friend or a counselor: 1800-599-0019"

    try:
        model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=system_prompt)
        response = model.generate_content(user_text)
        return response.text
    except Exception as e:
        print(f"GEMINI API ERROR: {e}")
        return "I'm sorry, I'm having trouble connecting to the AI service right now."

def save_mood_score(score):
    today_str = datetime.now().strftime("%Y-%m-%d")
    file_path = os.path.join(MOOD_DIR, f"{today_str}.json")
    daily_entries = []
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                daily_entries = json.load(f)
            except json.JSONDecodeError:
                daily_entries = []
    daily_entries.append({"timestamp": datetime.now().isoformat(), "score": score})
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(daily_entries, f, indent=4)

# --- API Endpoints ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    data = request.json
    user_message = data.get('message')
    if user_message:
        chat_mood_score = sid.polarity_scores(user_message)['compound']
        save_mood_score(chat_mood_score)
        bot_response = generate_response(user_message)
        return jsonify({"response": bot_response})
    return jsonify({"error": "No message provided"}), 400

# --- Mood Tracker Endpoints ---
@app.route('/log_mood', methods=['POST'])
def log_mood_endpoint():
    data = request.json
    mood = data.get('mood')
    mood_scores = {"happy": 0.8, "neutral": 0.0, "sad": -0.8}
    score = mood_scores.get(mood)
    if score is not None:
        save_mood_score(score)
        return jsonify({"status": "success"})
    return jsonify({"error": "Invalid mood"}), 400

@app.route('/get_mood_data', methods=['GET'])
def get_mood_data():
    try:
        all_files = sorted([f for f in os.listdir(MOOD_DIR) if f.endswith('.json')])
        mood_data = []
        for filename in all_files:
            file_path = os.path.join(MOOD_DIR, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                daily_entries = json.load(f)
                if not daily_entries: continue
                avg_score = sum(e['score'] for e in daily_entries) / len(daily_entries)
                date_str = filename.replace('.json', '')
                mood_data.append({"timestamp": date_str, "avg_mood": avg_score})
        return jsonify({"mood_data": mood_data})
    except Exception as e:
        print(f"Error loading mood data: {e}")
        return jsonify({"error": str(e)}), 500

# --- Chat History & Journal Endpoints ---
@app.route('/save_chat', methods=['POST'])
def save_chat_endpoint():
    data = request.json
    session_id, chat_history = data.get('session_id'), data.get('history')
    if session_id and chat_history and len(chat_history) > 1:
        first_user_message = next((msg['text'] for msg in chat_history if msg['sender'] == 'user'), "Chat History")
        title = (first_user_message[:40] + '...') if len(first_user_message) > 40 else first_user_message
        file_path = os.path.join(HISTORY_DIR, f"{session_id}.json")
        save_data = {"title": title, "history": chat_history, "timestamp": datetime.now().isoformat()}
        with open(file_path, 'w', encoding='utf-8') as f: json.dump(save_data, f, indent=4)
        return jsonify({"status": "success"})
    return jsonify({"error": "Invalid data"}), 400

@app.route('/load_chat', methods=['GET'])
def load_chat_endpoint():
    try:
        files = sorted([f for f in os.listdir(HISTORY_DIR) if f.endswith('.json')])
        history_list = []
        for f in files:
            with open(os.path.join(HISTORY_DIR, f), 'r', encoding='utf-8') as file_content:
                data = json.load(file_content)
                history_list.append({"id": f.replace('.json', ''), "title": data.get("title", "Untitled")})
        return jsonify({"history": history_list})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/get_chat_history/<session_id>', methods=['GET'])
def get_chat_history_endpoint(session_id):
    file_path = os.path.join(HISTORY_DIR, f"{session_id}.json")
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f: data = json.load(f)
        return jsonify({"history": data.get("history", [])})
    return jsonify({"error": "Not found"}), 404

@app.route('/delete_chat/<session_id>', methods=['DELETE'])
def delete_chat_endpoint(session_id):
    file_path = os.path.join(HISTORY_DIR, f"{session_id}.json")
    if os.path.exists(file_path):
        os.remove(file_path)
        return jsonify({"status": "success"})
    return jsonify({"error": "Not found"}), 404

@app.route('/save_journal', methods=['POST'])
def save_journal_endpoint():
    data = request.json
    journal_text = data.get('text')
    if journal_text:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_path = os.path.join(JOURNAL_DIR, f"journal_{timestamp}.txt")
        with open(file_path, 'w', encoding='utf-8') as f: f.write(journal_text)
        return jsonify({"status": "success"})
    return jsonify({"error": "No text"}), 400

@app.route('/load_journals', methods=['GET'])
def load_journals_endpoint():
    try:
        files = sorted([f for f in os.listdir(JOURNAL_DIR) if f.endswith('.txt')], reverse=True)
        journals = []
        for f in files:
            with open(os.path.join(JOURNAL_DIR, f), 'r', encoding='utf-8') as fc:
                preview = fc.read(100)
            journals.append({"id": f, "preview": preview})
        return jsonify({"journals": journals})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/get_journal/<journal_id>', methods=['GET'])
def get_journal_endpoint(journal_id):
    file_path = os.path.join(JOURNAL_DIR, journal_id)
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f: content = f.read()
        return jsonify({"content": content})
    return jsonify({"error": "Not found"}), 404

@app.route('/delete_journal/<journal_id>', methods=['DELETE'])
def delete_journal_endpoint(journal_id):
    if '..' in journal_id or journal_id.startswith('/'): return jsonify({"error": "Invalid filename"}), 400
    file_path = os.path.join(JOURNAL_DIR, journal_id)
    if os.path.exists(file_path):
        os.remove(file_path)
        return jsonify({"status": "success"})
    return jsonify({"error": "Not found"}), 404

if __name__ == '__main__':
    app.run(debug=True)
