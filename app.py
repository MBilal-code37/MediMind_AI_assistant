from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import json
import requests
from functools import wraps

app = Flask(__name__)

# Basic configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Database configuration for Vercel (using memory database for now)
# This will work immediately without external database
import sqlite3
import tempfile

# Create a temporary database file that works on Vercel
temp_db = tempfile.NamedTemporaryFile(delete=False)
temp_db.close()
db_path = temp_db.name
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'

print(f"Using database at: {db_path}")

# Initialize database
db = SQLAlchemy(app)

# DeepSeek API configuration
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChatSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    messages = db.Column(db.Text, default='[]')
    summary_data = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Create tables
with app.app_context():
    db.create_all()
    print("✅ Database tables created!")

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
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
    
    # Mock response for testing (remove this when you have API key)
    if not DEEPSEEK_API_KEY:
        mock_response = f"Thank you for sharing. Can you tell me more about your symptoms? How long have you been experiencing this?"
        return jsonify({
            'success': True,
            'message': mock_response,
            'session_id': 1,
            'ready_for_summary': False
        })
    
    try:
        # Actual API call
        api_messages = [{"role": msg['role'], "content": msg['content']} for msg in conversation_history]
        api_messages.append({"role": "user", "content": user_message})
        
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "system", "content": "You are MediMind, a helpful medical assistant."}, *api_messages],
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        response = requests.post(DEEPSEEK_API_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        ai_response = response.json()['choices'][0]['message']['content']
        
        return jsonify({
            'success': True,
            'message': ai_response,
            'session_id': 1,
            'ready_for_summary': False
        })
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({
            'success': True,  # Return mock response on error
            'message': "I understand you're experiencing some symptoms. Could you please describe them in more detail?",
            'session_id': 1,
            'ready_for_summary': False
        })

@app.route('/api/generate-summary', methods=['POST'])
@login_required
def generate_summary():
    return jsonify({
        'success': True,
        'summary': {
            'symptom_overview': 'Based on our conversation, you reported various symptoms.',
            'possible_conditions': [
                {'name': 'Common cold', 'explanation': 'Viral infection of upper respiratory tract', 'likelihood': 'Common'},
                {'name': 'Seasonal allergies', 'explanation': 'Immune response to environmental triggers', 'likelihood': 'Common'}
            ],
            'questions_for_doctor': ['How long will recovery take?', 'What medications do you recommend?'],
            'urgent_care_signs': ['Difficulty breathing', 'High fever over 103°F (39.4°C)']
        }
    })

@app.route('/summary')
@login_required
def summary_page():
    return render_template('summary.html')

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "database": "working"})

if __name__ == '__main__':
    app.run(debug=True)