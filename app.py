from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3, os, uuid, re, requests, datetime, smtplib, random, string
from gtts import gTTS
import logging
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "krishi_secret_key")

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Email Configuration
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Handle storage for Serverless environments (like Vercel)
IS_VERCEL = os.getenv("VERCEL") == "1"

if IS_VERCEL:
    # Use /tmp for writable files in serverless
    BASE_DIR = "/tmp"
    DB_PATH = os.path.join(BASE_DIR, "krishi.db")
    UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
    VOICES_DIR = os.path.join(BASE_DIR, "voices")
else:
    # Use local directory for traditional hosting
    BASE_DIR = os.getcwd()
    DB_PATH = "krishi.db"
    UPLOADS_DIR = "static/uploads"
    VOICES_DIR = "static/voices"

# Ensure folders exist
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(VOICES_DIR, exist_ok=True)
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS users
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     email TEXT UNIQUE,
                     username TEXT,
                     password TEXT,
                     is_verified INTEGER DEFAULT 0,
                     verification_code TEXT)''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS chat_sessions
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     username TEXT,
                     session_name TEXT DEFAULT 'Chat Session',
                     created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                     updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                     FOREIGN KEY (username) REFERENCES users (username))''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS chat_messages
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     session_id INTEGER,
                     message_type TEXT,
                     message_text TEXT,
                     response_text TEXT,
                     image_filename TEXT,
                     voice_filename TEXT,
                     language TEXT,
                     timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                     FOREIGN KEY (session_id) REFERENCES chat_sessions (id))''')
    conn.close()
init_db()

# LLM configuration (OpenRouter)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")

SYSTEM_PROMPT = (
    "You are Krishi Mitra — an AI assistant for Indian farmers. "
    "Always reply in the same language as the user (Kannada, Hindi, English, Telugu, Malayalam, or Tamil). "
    "Give short, clear, and helpful answers about farming, weather, fertilizers, and crop diseases. "
    "If the user uploads an image, describe possible crop diseases or pests and suggest remedies. "
    "Do not include any symbols or markdown formatting — reply in plain text only."
)

# Email verification functions
def generate_verification_code():
    """Generate a 6-digit verification code"""
    return ''.join(random.choices(string.digits, k=6))

def send_verification_email(email, username, verification_code):
    """Send verification email to user"""
    try:
        if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
            logging.error("EMAIL_ADDRESS/EMAIL_PASSWORD are not configured.")
            return False

        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = email
        msg['Subject'] = "Verify Your Email - Krishi Mitra"
        
        body = f"""
        <html>
        <body>
            <h2>Welcome to Krishi Mitra!</h2>
            <p>Hello {username},</p>
            <p>Your verification code is: <strong>{verification_code}</strong></p>
            <p>Enter this code in the verification page to complete registration.</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        logging.info(f"Verification email sent to {email}")
        return True
    except Exception as e:
        logging.error(f"Failed to send verification email: {e}")
        return False

def clean_text(text):
    return text.strip()

def text_to_speech_simple(text, lang="en"):
    """Simple Google TTS without pydub dependencies"""
    try:
        language_map = {
            "kn": "kn", "hi": "hi", "en": "en", "te": "te", "ml": "ml", "ta": "ta"
        }
        
        lang_code = language_map.get(lang, "en")
        filename = f"{uuid.uuid4().hex}.mp3"
        filepath = os.path.join(VOICES_DIR, filename)
        
        text = text.strip()
        if not text:
            text = "ಸಂದೇಶ ಲಭ್ಯವಿಲ್ಲ"
        
        slow_speed = lang != "en"
        
        try:
            tts = gTTS(text=text, lang=lang_code, slow=slow_speed, lang_check=False)
            tts.save(filepath)
            
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                return filename
            else:
                return None
                
        except Exception as gtts_error:
            logging.error(f"gTTS error: {gtts_error}")
            try:
                tts = gTTS(text=text, lang=lang_code, slow=False)
                tts.save(filepath)
                if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                    return filename
            except Exception:
                return None
            
    except Exception as e:
        logging.error(f"Google TTS Error: {str(e)}")
        return None

def text_to_speech(text, lang="en"):
    return text_to_speech_simple(text, lang)

def generate_reply(prompt, lang="en"):
    """Get AI-generated response from OpenRouter model."""
    if not OPENROUTER_API_KEY:
        if lang == "kn":
            return "AI ಸೇವೆಯನ್ನು ಈಗ ಬಳಸಲು ಆಗುತ್ತಿಲ್ಲ. ದಯವಿಟ್ಟು ನಿರ್ವಾಹಕರನ್ನು ಸಂಪರ್ಕಿಸಿ."
        elif lang == "hi":
            return "AI सेवा अभी उपलब्ध नहीं है। कृपया व्यवस्थापक से संपर्क करें।"
        return "AI service is not configured. Please contact the administrator."

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "google/gemini-2.0-flash-001",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
    }
    try:
        r = requests.post(OPENROUTER_URL, headers=headers, json=data, timeout=30)
        if r.status_code == 200:
            reply = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            return clean_text(reply if reply else "ಕ್ಷಮಿಸಿ, ಉತ್ತರ ಸಿಗಲಿಲ್ಲ.")
        else:
            logging.error(f"OpenRouter API Error: {r.status_code} - {r.text}")
            if lang == "kn":
                return "ಕ್ಷಮಿಸಿ, ಸೇವೆಯೊಂದಿಗೆ ಸಂಪರ್ಕ ಸಾಧಿಸಲು ಸಾಧ್ಯವಾಗುತ್ತಿಲ್ಲ. ದಯವಿಟ್ಟು ಕೆಲವು ನಿಮಿಷಗಳ ನಂತರ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ."
            elif lang == "hi":
                return "क्षमा करें, सेवा से कनेक्ट नहीं हो पा रहा है। कृपया कुछ मिनटों बाद पुनः प्रयास करें।"
            else:
                return "Sorry, unable to connect to the service. Please try again after some time."
    except Exception as e:
        logging.error(f"Request Error: {e}")
        if lang == "kn":
            return "ನೆಟ್ವರ್ಕ್ ದೋಷ ಸಂಭವಿಸಿದೆ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ."
        elif lang == "hi":
            return "नेटवर्क त्रुटि हुई। कृपया पुनः प्रयास करें।"
        else:
            return "Network error occurred. Please try again."

def get_or_create_session(username, session_id=None):
    """Get existing session or create new one."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if session_id:
        cursor.execute("SELECT id, session_name FROM chat_sessions WHERE id = ? AND username = ?", 
                      (session_id, username))
        session = cursor.fetchone()
        if session:
            conn.close()
            return session[0], session[1]
    
    session_name = f"Chat {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
    cursor.execute("INSERT INTO chat_sessions (username, session_name) VALUES (?, ?)", 
                  (username, session_name))
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id, session_name

def save_chat_message(session_id, message_type, message_text, response_text, image_filename=None, voice_filename=None, language="en"):
    """Save chat message to database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute('''INSERT INTO chat_messages 
                        (session_id, message_type, message_text, response_text, image_filename, voice_filename, language)
                        VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (session_id, message_type, message_text, response_text, image_filename, voice_filename, language))
        conn.execute("UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (session_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("Error saving chat message:", e)
        return False

def get_chat_sessions(username):
    """Get all chat sessions for a user."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''SELECT id, session_name, created_at, updated_at 
                         FROM chat_sessions 
                         WHERE username = ? 
                         ORDER BY updated_at DESC''', (username,))
        sessions = cursor.fetchall()
        conn.close()
        return sessions
    except Exception as e:
        print("Error retrieving chat sessions:", e)
        return []

def get_chat_messages(session_id):
    """Get all messages for a chat session."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''SELECT message_type, message_text, response_text, image_filename, voice_filename, language, timestamp
                         FROM chat_messages 
                         WHERE session_id = ? 
                         ORDER BY timestamp ASC''', (session_id,))
        messages = cursor.fetchall()
        conn.close()
        return messages
    except Exception as e:
        print("Error retrieving chat messages:", e)
        return []

def delete_chat_session(session_id, username):
    """Delete a chat session and all its messages."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM chat_sessions WHERE id = ? AND username = ?", (session_id, username))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("Error deleting chat session:", e)
        return False

# ---------------- ROUTES ----------------

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        if not email or not username or not password:
            return render_template("register.html", error="Fill all fields.")
        
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return render_template("register.html", error="Enter valid email.")
        
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM users WHERE email = ? OR username = ?", (email, username))
            if cursor.fetchone():
                conn.close()
                return render_template("register.html", error="Email/Username exists.")
            
            verification_code = generate_verification_code()
            
            cursor.execute("INSERT INTO users (email, username, password, verification_code) VALUES (?, ?, ?, ?)", 
                          (email, username, password, verification_code))
            conn.commit()
            conn.close()
            
            if send_verification_email(email, username, verification_code):
                session['pending_email'] = email
                return redirect(url_for('verify_email'))
            else:
                return render_template("register.html", error="Failed to send email.")
                
        except Exception as e:
            return render_template("register.html", error="Registration failed.")
    
    return render_template('register.html')

@app.route('/verify-email', methods=['GET', 'POST'])
def verify_email():
    if 'pending_email' not in session:
        return redirect(url_for('register'))
    
    if request.method == 'POST':
        verification_code = request.form['verification_code'].strip()
        email = session['pending_email']
        
        if not verification_code:
            return render_template("verify_email.html", error="Enter code", email=email)
        
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM users WHERE email = ? AND verification_code = ?", 
                          (email, verification_code))
            user = cursor.fetchone()
            
            if user:
                cursor.execute("UPDATE users SET is_verified = 1, verification_code = NULL WHERE email = ?", (email,))
                conn.commit()
                conn.close()
                session.pop('pending_email', None)
                return redirect(url_for('login'))
            else:
                conn.close()
                return render_template("verify_email.html", error="Invalid code", email=email)
                
        except Exception as e:
            return render_template("verify_email.html", error="Verification failed", email=email)
    
    return render_template("verify_email.html", email=session.get('pending_email'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password'].strip()
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            if user[4] == 1:  # is_verified
                session['user'] = user[2]  # username
                session_id, session_name = get_or_create_session(user[2])
                session['current_session_id'] = session_id
                session['current_session_name'] = session_name
                return redirect(url_for('index'))
            else:
                session['pending_email'] = email
                return redirect(url_for('verify_email'))
        else:
            return render_template("login.html", error="Invalid email or password.")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

@app.route('/index')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    if 'current_session_id' not in session:
        session_id, session_name = get_or_create_session(session['user'])
        session['current_session_id'] = session_id
        session['current_session_name'] = session_name
    
    current_messages = get_chat_messages(session['current_session_id'])
    chat_sessions = get_chat_sessions(session['user'])
    
    return render_template('index.html', 
                         user=session['user'],
                         current_messages=current_messages,
                         chat_sessions=chat_sessions,
                         current_session_id=session['current_session_id'],
                         current_session_name=session['current_session_name'])

@app.route("/new_chat", methods=["POST"])
def new_chat():
    if 'user' not in session:
        return jsonify({"success": False, "error": "Not logged in"})
    
    session_id, session_name = get_or_create_session(session['user'])
    session['current_session_id'] = session_id
    session['current_session_name'] = session_name
    
    return jsonify({
        "success": True,
        "session_id": session_id,
        "session_name": session_name,
        "messages": []
    })

@app.route("/switch_session/<int:session_id>")
def switch_session(session_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    session_id, session_name = get_or_create_session(session['user'], session_id)
    session['current_session_id'] = session_id
    session['current_session_name'] = session_name
    
    return redirect(url_for('index'))

@app.route("/chat", methods=["POST"])
def chat():
    if 'user' not in session or 'current_session_id' not in session:
        return jsonify({"reply": "Please login first.", "voice": None})
    
    user_message = request.form.get("message", "").strip()
    lang = request.form.get("lang", "en")

    if not user_message:
        return jsonify({"reply": "ದಯವಿಟ್ಟು ಸಂದೇಶವನ್ನು ನಮೂದಿಸಿ.", "voice": None})

    reply = generate_reply(user_message, lang)
    
    voice_filename = None
    def generate_voice():
        nonlocal voice_filename
        voice_filename = text_to_speech(reply, lang)
    
    voice_thread = threading.Thread(target=generate_voice)
    voice_thread.start()
    voice_thread.join(timeout=10)
    
    voice_url = f"/voices/{voice_filename}" if voice_filename else None

    save_chat_message(
        session_id=session['current_session_id'],
        message_type="text",
        message_text=user_message,
        response_text=reply,
        voice_filename=voice_filename,
        language=lang
    )

    return jsonify({
        "reply": reply,
        "voice": voice_url
    })

@app.route("/upload", methods=["POST"])
def upload_image():
    if 'user' not in session or 'current_session_id' not in session:
        return jsonify({"reply": "Please login first.", "voice": None})
    
    image = request.files.get("image")
    lang = request.form.get("lang", "en")

    if not image:
        return jsonify({"reply": "ದಯವಿಟ್ಟು ಚಿತ್ರವನ್ನು ಅಪ್‌ಲೋಡ್ ಮಾಡಿ.", "voice": None})

    filename = f"{uuid.uuid4().hex}_{image.filename}"
    filepath = os.path.join(UPLOADS_DIR, filename)
    image.save(filepath)

    prompt = f"A farmer uploaded a crop image named {image.filename}. Analyze this image and describe what crop it may be, identify any visible diseases or pests, and suggest remedies in {lang} language."

    reply = generate_reply(prompt, lang)
    
    voice_filename = None
    def generate_voice():
        nonlocal voice_filename
        voice_filename = text_to_speech(reply, lang)
    
    voice_thread = threading.Thread(target=generate_voice)
    voice_thread.start()
    voice_thread.join(timeout=10)
    
    voice_url = f"/voices/{voice_filename}" if voice_filename else None

    save_chat_message(
        session_id=session['current_session_id'],
        message_type="image",
        message_text=f"Image: {image.filename}",
        response_text=reply,
        image_filename=filename,
        voice_filename=voice_filename,
        language=lang
    )

    return jsonify({
        "reply": reply,
        "voice": voice_url
    })

@app.route("/delete_session/<int:session_id>", methods=["DELETE"])
def delete_session(session_id):
    if 'user' not in session:
        return jsonify({"success": False, "error": "Not logged in"})
    
    success = delete_chat_session(session_id, session['user'])
    
    if success and session.get('current_session_id') == session_id:
        new_session_id, new_session_name = get_or_create_session(session['user'])
        session['current_session_id'] = new_session_id
        session['current_session_name'] = new_session_name
    
    return jsonify({"success": success})

@app.route("/rename_session/<int:session_id>", methods=["POST"])
def rename_session(session_id):
    if 'user' not in session:
        return jsonify({"success": False, "error": "Not logged in"})
    
    new_name = request.json.get('new_name', '').strip()
    if not new_name:
        return jsonify({"success": False, "error": "Name cannot be empty"})
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE chat_sessions SET session_name = ? WHERE id = ? AND username = ?", 
                    (new_name, session_id, session['user']))
        conn.commit()
        conn.close()
        
        if session.get('current_session_id') == session_id:
            session['current_session_name'] = new_name
            
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/uploads/<filename>')
def serve_upload(filename):
    from flask import send_from_directory
    return send_from_directory(UPLOADS_DIR, filename)

@app.route('/voices/<filename>')
def serve_voice(filename):
    from flask import send_from_directory
    return send_from_directory(VOICES_DIR, filename)

# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(debug=True)



#adding comments