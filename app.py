from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import jwt
import os
import json
import requests
from functools import wraps

# ============================================
# FIX: Create all necessary directories
# ============================================
os.makedirs('database', exist_ok=True)
os.makedirs('templates', exist_ok=True)
os.makedirs('static/css', exist_ok=True)
os.makedirs('static/js', exist_ok=True)

# ============================================
# FIX: Use absolute path for database
# ============================================
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'database', 'medimind.db')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# DeepSeek API configuration
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', 'your-deepseek-api-key')
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# ============================================
# Database Models
# ============================================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    chat_history = db.relationship('ChatSession', backref='user', lazy=True)

class ChatSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    messages = db.Column(db.Text, default='[]')
    summary_data = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ============================================
# FIX: Create tables with error handling
# ============================================
with app.app_context():
    try:
        db.create_all()
        print("=" * 50)
        print("✅ Database created successfully!")
        print(f"📁 Database location: {db_path}")
        print("=" * 50)
    except Exception as e:
        print(f"⚠️ Database error: {e}")
        print("Trying alternative database location...")
        
        # Fallback to current directory
        alt_db_path = os.path.join(basedir, 'medimind.db')
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{alt_db_path}'
        db = SQLAlchemy(app)  # Re-initialize with new path
        db.create_all()
        print(f"✅ Database created at: {alt_db_path}")

# ============================================
# Authentication decorator
# ============================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ============================================
# DeepSeek API call function
# ============================================
def call_deepseek_api(messages, is_summary=False):
    """Call DeepSeek API with conversation history"""
    
    system_prompt = """You are MediMind, a compassionate and intelligent medical triage assistant.
Your role is to help patients prepare for their doctor's appointment — NOT to diagnose them.

Your behavior:
- Ask one follow-up question at a time, naturally and conversationally
- Use plain, simple language — no medical jargon unless explained
- Sound warm, calm, and caring — like a knowledgeable friend, not a medical form
- After 4-6 exchanges, tell the user you have enough information and offer to generate their summary
- Never tell the user they definitely have a condition
- Never cause unnecessary alarm
- Always frame possibilities as "things worth discussing with your doctor"
- Keep responses short (2-4 sentences max) during the conversation phase

If this is a summary generation request, provide a JSON object with these exact fields:
{
    "symptom_overview": "Plain language summary of symptoms",
    "possible_conditions": [
        {"name": "Condition name", "explanation": "Plain explanation", "likelihood": "Common/Less common/Rare"}
    ],
    "questions_for_doctor": ["Question 1", "Question 2"],
    "urgent_care_signs": ["Warning sign 1", "Warning sign 2"]
}"""

    if is_summary:
        system_prompt += "\n\nIMPORTANT: Generate ONLY the JSON object for the summary, no other text."

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            *messages
        ],
        "temperature": 0.7 if not is_summary else 0.3,
        "max_tokens": 2000 if not is_summary else 3000
    }
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(DEEPSEEK_API_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"DeepSeek API error: {e}")
        raise

# ============================================
# Routes
# ============================================
@app.route('/')
def landing():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        user = User.query.filter_by(username=data.get('username')).first()
        
        if user and check_password_hash(user.password_hash, data.get('password')):
            session['user_id'] = user.id
            session['username'] = user.username
            return jsonify({'success': True, 'redirect': '/chat'})
        else:
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
    
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    if User.query.filter_by(username=data.get('username')).first():
        return jsonify({'success': False, 'message': 'Username already exists'}), 400
    
    if User.query.filter_by(email=data.get('email')).first():
        return jsonify({'success': False, 'message': 'Email already exists'}), 400
    
    hashed_password = generate_password_hash(data.get('password'))
    user = User(
        username=data.get('username'),
        email=data.get('email'),
        password_hash=hashed_password
    )
    
    db.session.add(user)
    db.session.commit()
    
    session['user_id'] = user.id
    session['username'] = user.username
    
    return jsonify({'success': True, 'redirect': '/chat'})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

@app.route('/chat')
@login_required
def chat():
    return render_template('chat.html', username=session.get('username'))

@app.route('/api/chat/message', methods=['POST'])
@login_required
def chat_message():
    data = request.get_json()
    user_message = data.get('message')
    conversation_history = data.get('history', [])
    
    session_id = data.get('session_id')
    if session_id:
        chat_session = ChatSession.query.get(session_id)
        if chat_session and chat_session.user_id == session['user_id']:
            existing_messages = json.loads(chat_session.messages)
            conversation_history = existing_messages + conversation_history
    else:
        chat_session = ChatSession(user_id=session['user_id'])
        db.session.add(chat_session)
        db.session.commit()
        session_id = chat_session.id
    
    api_messages = []
    for msg in conversation_history:
        api_messages.append({
            "role": msg['role'],
            "content": msg['content']
        })
    
    try:
        ai_response = call_deepseek_api(api_messages, is_summary=False)
        
        updated_messages = conversation_history + [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": ai_response}
        ]
        chat_session.messages = json.dumps(updated_messages)
        chat_session.updated_at = datetime.utcnow()
        db.session.commit()
        
        user_message_count = len([m for m in updated_messages if m['role'] == 'user'])
        ready_for_summary = user_message_count >= 4
        
        return jsonify({
            'success': True,
            'message': ai_response,
            'session_id': chat_session.id,
            'ready_for_summary': ready_for_summary
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Something went wrong. Please try again.'
        }), 500

@app.route('/api/generate-summary', methods=['POST'])
@login_required
def generate_summary():
    data = request.get_json()
    session_id = data.get('session_id')
    
    chat_session = ChatSession.query.filter_by(id=session_id, user_id=session['user_id']).first()
    if not chat_session:
        return jsonify({'error': 'Chat session not found'}), 404
    
    messages = json.loads(chat_session.messages)
    
    user_message_count = len([m for m in messages if m['role'] == 'user'])
    if user_message_count < 4:
        return jsonify({
            'error': 'Please chat with MediMind a little more before generating your summary.'
        }), 400
    
    try:
        api_messages = [
            {"role": "system", "content": "Based on the following conversation, generate a visit preparation summary."},
            *messages
        ]
        
        summary_json = call_deepseek_api(api_messages, is_summary=True)
        
        summary_json = summary_json.strip()
        if summary_json.startswith('```json'):
            summary_json = summary_json[7:]
        if summary_json.startswith('```'):
            summary_json = summary_json[3:]
        if summary_json.endswith('```'):
            summary_json = summary_json[:-3]
        
        summary_data = json.loads(summary_json)
        
        chat_session.summary_data = json.dumps(summary_data)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'summary': summary_data
        })
        
    except Exception as e:
        print(f"Summary generation error: {e}")
        return jsonify({
            'error': 'Something went wrong generating your summary. Please try again.'
        }), 500

@app.route('/api/get-summary/<int:session_id>')
@login_required
def get_summary(session_id):
    chat_session = ChatSession.query.filter_by(id=session_id, user_id=session['user_id']).first()
    if not chat_session or not chat_session.summary_data:
        return jsonify({'error': 'No summary found'}), 404
    
    summary_data = json.loads(chat_session.summary_data)
    return jsonify({'summary': summary_data})

@app.route('/summary')
@login_required
def summary_page():
    return render_template('summary.html')

@app.route('/api/user/sessions')
@login_required
def get_user_sessions():
    sessions = ChatSession.query.filter_by(user_id=session['user_id']).order_by(ChatSession.updated_at.desc()).all()
    return jsonify({
        'sessions': [
            {
                'id': s.id,
                'created_at': s.created_at.isoformat(),
                'has_summary': s.summary_data is not None
            }
            for s in sessions
        ]
    })

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)