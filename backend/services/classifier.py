import os
import logging
import requests
from typing import Dict, Any

from utils.supabase_client import supabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
USE_ML = True               # Set False to fallback to rule-based
IMPORTANCE_THRESHOLD = 0.6
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Rule-based categories
RULES = {
    "interview": {
        "keywords": ["interview", "invitation", "schedule", "meeting"],
        "importance": 0.9,
        "action_required": True
    },
    "deadline": {
        "keywords": ["deadline", "due", "expiration", "closing"],
        "importance": 0.8,
        "action_required": True
    },
    "selection": {
        "keywords": ["selected", "shortlisted", "congratulations", "offer", "acceptance"],
        "importance": 0.95,
        "action_required": True
    },
    "academic": {
        "keywords": ["assignment", "exam", "grade", "course", "lecture"],
        "importance": 0.7,
        "action_required": False
    },
    "job": {
        "keywords": ["job", "career", "opportunity", "hiring", "position"],
        "importance": 0.85,
        "action_required": True
    },
    "promotion": {
        "keywords": ["newsletter", "offer", "sale", "discount"],
        "importance": 0.2,
        "action_required": False
    }
}

def rule_classify(email_record: Dict[str, Any]) -> Dict[str, Any]:
    """Classify email based on rule-based keywords."""
    subject = email_record['subject'].lower()
    sender = email_record['sender'].lower()
    snippet = email_record['snippet'].lower()
    text = f"{subject} {sender} {snippet}"

    best_category = "other"
    best_score = 0.0
    action_required = False
    for category, rule in RULES.items():
        if any(kw in text for kw in rule["keywords"]):
            if rule["importance"] > best_score:
                best_score = rule["importance"]
                best_category = category
                action_required = rule["action_required"]

    summary = f"{email_record['subject']} – {email_record['snippet'][:100]}..."
    return {
        "category": best_category,
        "importance_score": best_score,
        "summary": summary,
        "action_required": action_required,
        "method": "rule"
    }

def ml_classify(email_record: Dict[str, Any]) -> Dict[str, Any]:
    """Use ML (Hugging Face) for classification and summarization."""
    try:
        from services.ml_classifier import classify_with_ml, summarize_with_ml
        classification = classify_with_ml(email_record)
        if classification:
            summary = summarize_with_ml(email_record)
            classification['summary'] = summary
            return classification
        else:
            logger.warning("ML classification returned None, falling back to rule.")
            return rule_classify(email_record)
    except Exception as e:
        logger.error(f"Error in ML classification: {e}, falling back to rule.")
        return rule_classify(email_record)

def classify_email(email_record: Dict[str, Any]) -> Dict[str, Any]:
    """Main classification function, switches between ML and rule."""
    if USE_ML:
        return ml_classify(email_record)
    else:
        return rule_classify(email_record)

def send_telegram_alert(chat_id: str, email_record: Dict[str, Any], classification: Dict[str, Any]):
    """Send notification via Telegram bot."""
    emoji_map = {
        "interview": "📅",
        "deadline": "⏰",
        "selection": "🎉",
        "academic": "📚",
        "job": "💼",
        "promotion": "📢",
        "other": "📧"
    }
    emoji = emoji_map.get(classification["category"], "📧")
    message = f"{emoji} *{email_record['subject']}*\n"
    message += f"From: {email_record['sender']}\n"
    message += f"Summary: {classification['summary']}\n"
    if classification["action_required"]:
        message += "⚠️ *Action Required*"
    else:
        message += "ℹ️ Info"
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logger.info(f"Alert sent to {chat_id} for email {email_record['id']}")
        supabase.table("notifications").insert({
            "user_id": email_record["user_id"],
            "email_id": email_record["id"],
            "telegram_message_id": response.json()["result"]["message_id"],
            "status": "sent"
        }).execute()
    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")

def process_unclassified_emails():
    """Find unprocessed emails, classify, send alerts, and trigger attachment analysis."""
    emails = supabase.table("emails").select("*").eq("processed", False).execute()
    for email in emails.data:
        # Classify email
        classification = classify_email(email)
        
        # Store classification
        supabase.table("classifications").insert({
            "email_id": email["id"],
            "category": classification["category"],
            "importance_score": classification["importance_score"],
            "summary": classification["summary"],
            "action_required": classification["action_required"],
            "method": classification["method"]
        }).execute()
        
        # Mark email as processed
        supabase.table("emails").update({"processed": True}).eq("id", email["id"]).execute()
        
        # If important, send Telegram alert
        if classification["importance_score"] >= IMPORTANCE_THRESHOLD:
            user = supabase.table("profiles").select("telegram_chat_id").eq("id", email["user_id"]).execute()
            if user.data and user.data[0]["telegram_chat_id"]:
                send_telegram_alert(user.data[0]["telegram_chat_id"], email, classification)
        
        # Process attachments (if any) – this may update classification or send additional alert
        if email.get("has_attachments"):
            try:
                from services.attachment_analyzer import process_attachments
                process_attachments(email)
            except Exception as e:
                logger.error(f"Error processing attachments for email {email['id']}: {e}")

if __name__ == "__main__":
    process_unclassified_emails()