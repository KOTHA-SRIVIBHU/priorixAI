
# 📧 Smart Email-to-Telegram AI Alert System

An intelligent notification platform that monitors multiple email accounts, identifies important emails using AI/ML, and sends real-time alerts via Telegram.

## 🚀 Features

- 📱 **Multi-Email Account Support** – Monitor multiple Gmail accounts from one place
- 🤖 **AI-Powered Classification** – Automatically detect interviews, deadlines, job offers, and selection notifications
- 📊 **Excel Attachment Analysis** – Scan Excel/CSV files for your name or ID and get instant selection alerts
- ⏰ **Deadline Reminders** – Automatic reminders for important deadlines
- 🔍 **Spam Folder Monitoring** – Never miss important emails misclassified as spam
- 🎯 **ID-Based Detection** – Find your roll number or registration ID in email bodies and attachments
- 📝 **Smart Summarization** – Get concise summaries of important emails
- 🔒 **Read-Only Access** – Never sends, modifies, or deletes emails

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Gmail API     │────▶│   Email Fetcher  │────▶│   Supabase DB   │
│  (Read-Only)    │     │   (Every 2 min)  │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │                          │
                               ▼                          ▼
                        ┌──────────────────┐     ┌─────────────────┐
                        │   AI Classifier  │     │  Telegram Bot   │
                        │  (ML/DeepSeek)   │────▶│   (Alerts)      │
                        └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  Excel Analyzer  │
                        │  (ID Detection)  │
                        └──────────────────┘
```

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: Supabase (PostgreSQL)
- **Email Integration**: Gmail API (read-only)
- **AI/ML**: Hugging Face Transformers / DeepSeek
- **Messaging**: Telegram Bot API
- **Deployment**: Koyeb / Render / Oracle Cloud (free tier)

## 📋 Prerequisites

- Python 3.10+
- Gmail account (for testing)
- Telegram account
- Supabase account (free tier)
- Google Cloud Platform account (for Gmail API)

## 🔧 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/email-alert-system.git
cd email-alert-system
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables

Create a `.env` file in the `backend/` directory:

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key

# Google OAuth
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/gmail/callback

# Telegram
TELEGRAM_TOKEN=your-telegram-bot-token

# Backend URL
BACKEND_URL=http://localhost:8000

# Optional: Hugging Face (for ML)
HF_API_TOKEN=your-huggingface-token
```

### 5. Set Up Supabase Database

1. Create a new Supabase project
2. Run the SQL schema from `database/schema.sql` in the Supabase SQL Editor
3. Enable Row Level Security (RLS) as defined in the schema

### 6. Configure Gmail API

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project
3. Enable Gmail API
4. Create OAuth 2.0 credentials (Web application)
5. Add authorized redirect URIs:
   - `http://localhost:8000/auth/gmail/callback`
   - `https://your-domain.com/auth/gmail/callback` (for production)
6. Copy Client ID and Client Secret to `.env`

### 7. Create Telegram Bot

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Send `/newbot` and follow instructions
3. Copy the bot token to `.env`

## 🏃 Running Locally

### Start the Backend Server

```bash
cd backend
uvicorn main:app --reload
```

The backend will be available at `http://localhost:8000`

### Start the Telegram Bot

```bash
cd bot
python bot.py
```

### Run Email Fetcher (Manual)

```bash
cd backend
python -m services.run_once
```

## 📦 Project Structure

```
email-alert-system/
├── backend/
│   ├── auth/
│   │   └── gmail.py              # OAuth endpoints
│   ├── services/
│   │   ├── email_fetcher.py      # Gmail API integration
│   │   ├── classifier.py         # AI classification
│   │   ├── attachment_analyzer.py # Excel/CSV analysis
│   │   ├── deadline_reminder.py  # Deadline extraction
│   │   └── run_once.py           # Combined fetcher + classifier
│   ├── utils/
│   │   └── supabase_client.py    # Supabase connection
│   ├── main.py                   # FastAPI app
│   └── requirements.txt
├── bot/
│   └── bot.py                    # Telegram bot
├── database/
│   └── schema.sql                # Supabase tables
├── .env                          # Environment variables
├── .gitignore
└── README.md
```

## 🚢 Deployment

### Deploy on Koyeb (Free, No Credit Card)

1. Push code to GitHub
2. Sign up at [koyeb.com](https://koyeb.com)
3. Create a new app:
   - **Web Service**: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Worker**: `cd bot && python bot.py`
   - **Cron Job**: `cd backend && python -m services.run_once` (schedule: `*/2 * * * *`)
4. Add environment variables from `.env`
5. Update Google OAuth redirect URI to your Koyeb URL

### Deploy on Render (Requires Credit Card for Cron)

1. Web service for backend
2. Background worker for bot
3. Cron job for fetcher (requires paid plan)

### Deploy on Oracle Cloud (Free VM)

1. Create Oracle Cloud Always Free VM
2. Install Python and dependencies
3. Use systemd for backend and bot
4. Use cron for fetcher

## 🎯 Usage

### Connect Email Account

1. Start the bot: `/start`
2. Click "Connect Email Account"
3. Authorize read-only access to Gmail
4. You'll receive a confirmation message

### Set Your ID for Selection Detection

Update your profile in Supabase:

```sql
UPDATE profiles 
SET user_id_detection = 'YOUR_ID' 
WHERE telegram_chat_id = 'YOUR_CHAT_ID';
```

### Receive Alerts

The system will automatically send Telegram alerts for:
- 🎉 Selection notifications (with Excel analysis)
- 📅 Interview invitations
- ⏰ Deadlines
- 💼 Job opportunities
- 📚 Academic updates

## 🔒 Security Features

- **Read-Only Email Access**: Uses Gmail API scope `https://www.googleapis.com/auth/gmail.readonly`
- **OAuth 2.0**: No password storage
- **Row Level Security**: Users can only access their own data
- **Encrypted Tokens**: OAuth tokens stored encrypted in Supabase
- **No Permanent Storage**: Email bodies are not stored (only metadata)

## 📊 Database Schema

- `profiles` – User settings and Telegram chat ID
- `email_accounts` – OAuth tokens and email addresses
- `emails` – Email metadata (subject, sender, snippet)
- `classifications` – AI classification results
- `notifications` – Sent Telegram alerts
- `deadlines` – Extracted deadlines for reminders
- `feedback` – User feedback for adaptive learning

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is for educational purposes as a college project.

## 🙏 Acknowledgments

- Google Gmail API
- Supabase
- Telegram Bot API
- Hugging Face Transformers
- FastAPI
