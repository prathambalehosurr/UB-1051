# 🌾 Krishi Mitra (Krishi Samparka)

**Krishi Mitra** is an AI-powered digital companion designed specifically for Indian farmers. It leverages state-of-the-art Generative AI (Google Gemini 2.0 Flash) to provide instant, localized advice on crop management, pest control, weather guidance, and market information.

The platform is built to be accessible, supporting multiple regional languages and offering both text and voice-mased interactions to bridge the digital divide in agriculture.
 
---

## 🚀 Key Features

### 1. **Multilingual AI Chat**
- Interact in **Kannada, Hindi, English, Telugu, Malayalam, or Tamil**.
- AI responses are tailored to the specific language and regional agricultural context.

### 2. **AI Vision: Crop Disease Detection**
- Upload a photo of an infected crop or a pest.
- The AI analyzes the image to identify the issue and suggests organic or chemical remedies.

### 3. **Voice-Enabled Assistance**
- Automated **Text-to-Speech (TTS)** for every AI response.
- Helps farmers who prefer listening over reading to receive vital information.

### 4. **Secure User Management**
- **Email Verification**: Secure registration system with OTP-based email verification.
- **Persistent Chat History**: Maintains multiple chat sessions so farmers can refer back to previous advice (e.g., "What did I do for my tomato plants last month?").

### 5. **Localized Information**
- Real-time advice on fertilizers, soil health, and weather-appropriate farming techniques.

---

## 🛠️ Tech Stack

### **Backend**
- **Python & Flask**: Core application logic and routing.
- **SQLite**: lightweight database for user profiles and chat history.
- **OpenRouter API**: Interface for **Google Gemini 2.0 Flash**, the primary LLM.
- **gTTS (Google Text-to-Speech)**: For generating localized audio responses.
- **smtplib**: For sending verification emails.

### **Frontend**
- **Jinja2**: Server-side templating.
- **Tailwind CSS & Bootstrap 5**: For a modern, responsive, and mobile-friendly UI.
- **Vanilla JavaScript**: Real-time chat interactivity and browser-side voice handling.
- **Font Awesome & Google Fonts**: For enhanced visual design.

---

## 📋 Prerequisites

- **Python 3.8+**
- An **OpenRouter API Key** (for Gemini 2.0)
- A **Gmail account** (with App Password enabled) for sending verification emails.

---

## ⚙️ Setup & Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd hackathon-final-boss
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install flask gtts requests
   ```

4. **Configure Environment Variables:**
   Create a `.env` file (or set them in your terminal):
   ```bash
   export OPENROUTER_API_KEY="your_api_key_here"
   export EMAIL_ADDRESS="your-gmail@gmail.com"
   export EMAIL_PASSWORD="your-app-password" # Not your regular password
   export FLASK_SECRET_KEY="your_random_secret_key"
   ```

5. **Initialize the Database:**
   The database (`krishi.db`) initializes automatically when you first run the app.

6. **Run the application:**
   ```bash
   python app.py
   ```
   The app will be available at `http://127.0.0.1:5000`.

---

## 📂 Project Structure

```text
├── app.py              # Main Flask application & AI logic
├── templates/          # HTML templates (Jinja2)
│   ├── landing.html    # Home/Landing page
│   ├── login.html      # Authentication
│   ├── register.html   # User signup
│   └── index.html      # Main Chat Interface
├── static/             # Assets (Generated at runtime)
│   ├── uploads/        # Farmer-uploaded images
│   └── voices/         # AI-generated audio files
├── krishi.db           # SQLite Database (Git ignored)
└── README.md           # Documentation
```

---

## 🛡️ Future Roadmap
- [ ] **Offline Mode**: Integration of low-data models for areas with poor connectivity.
- [ ] **Market Price Tracker**: Real-time integration with APMC market pricing.
- [ ] **Weather API**: Proactive alerts for heavy rain or drought based on farmer location.
- [ ] **Government Schemes**: A dedicated section for finding and applying for agricultural subsidies.

---

## 📄 License
This project is licensed under the MIT License - see the LICENSE file for details.

---

**Built with ❤️ for Indian Farmers.**
