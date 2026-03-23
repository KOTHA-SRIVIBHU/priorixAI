import os
import base64
import io
import logging
import pandas as pd
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from services.email_fetcher import refresh_gmail_token  # reuse token refresh

from utils.supabase_client import supabase
import requests

logger = logging.getLogger(__name__)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")

def download_attachment(service, message_id, attachment_id):
    """Download an attachment from Gmail."""
    try:
        attachment = service.users().messages().attachments().get(
            userId='me', messageId=message_id, id=attachment_id
        ).execute()
        data = attachment['data']
        file_data = base64.urlsafe_b64decode(data.encode('UTF-8'))
        return file_data
    except Exception as e:
        logger.error(f"Error downloading attachment: {e}")
        return None

def analyze_excel(file_data, user_id_to_detect):
    """Search for user ID in Excel/CSV data."""
    try:
        # Try reading as Excel first, then CSV
        try:
            df = pd.read_excel(io.BytesIO(file_data))
        except:
            # fallback to CSV
            df = pd.read_csv(io.BytesIO(file_data))
        
        # Convert all cells to string and check if any contain the user ID
        found = df.astype(str).apply(lambda x: x.str.contains(user_id_to_detect, case=False, na=False)).any().any()
        if found:
            # Find the matching rows for context
            mask = df.astype(str).apply(lambda x: x.str.contains(user_id_to_detect, case=False, na=False)).any(axis=1)
            matched_rows = df[mask]
            context = matched_rows.to_string()
            return True, context
        return False, ""
    except Exception as e:
        logger.error(f"Error parsing attachment: {e}")
        return False, ""

def send_telegram_selection_alert(chat_id, email_subject, context):
    """Send a special selection alert via Telegram."""
    message = (f"🎉 *Selection Alert!*\n"
               f"Your ID was found in the attachment of email:\n"
               f"*{email_subject}*\n\n"
               f"*Matched rows:*\n{context}")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logger.info(f"Selection alert sent to {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send selection alert: {e}")

def process_attachments(email_record):
    """Process attachments for a given email."""
    # Get user's ID detection string
    user = supabase.table("profiles").select("user_id_detection").eq("id", email_record["user_id"]).execute()
    if not user.data or not user.data[0]["user_id_detection"]:
        return
    user_id_to_detect = user.data[0]["user_id_detection"]
    
    # Get the email account to retrieve Gmail service
    account = supabase.table("email_accounts").select("*").eq("id", email_record["email_account_id"]).execute()
    if not account.data:
        logger.warning(f"No email account found for email {email_record['id']}")
        return
    
    account_record = account.data[0]
    # Refresh token and build service (reuse function from email_fetcher)
    creds = refresh_gmail_token(account_record)
    service = build("gmail", "v1", credentials=creds)
    
    # Get full message to access attachment parts
    try:
        msg = service.users().messages().get(userId='me', id=email_record["message_id"]).execute()
    except Exception as e:
        logger.error(f"Could not fetch full message {email_record['message_id']}: {e}")
        return
    
    # Extract parts
    parts = msg.get('payload', {}).get('parts', [])
    for part in parts:
        if part.get('filename') and part.get('body', {}).get('attachmentId'):
            filename = part['filename'].lower()
            if filename.endswith(('.xlsx', '.xls', '.csv')):
                attachment_id = part['body']['attachmentId']
                file_data = download_attachment(service, email_record["message_id"], attachment_id)
                if file_data:
                    found, context = analyze_excel(file_data, user_id_to_detect)
                    if found:
                        # Get Telegram chat_id
                        profile = supabase.table("profiles").select("telegram_chat_id").eq("id", email_record["user_id"]).execute()
                        if profile.data and profile.data[0]["telegram_chat_id"]:
                            send_telegram_selection_alert(
                                profile.data[0]["telegram_chat_id"],
                                email_record["subject"],
                                context
                            )
                            # Optionally update the classification for this email to mark it as selection
                            supabase.table("classifications").update({
                                "category": "selection",
                                "importance_score": 0.95,
                                "action_required": True
                            }).eq("email_id", email_record["id"]).execute()
                            logger.info(f"Updated classification for email {email_record['id']} to selection")