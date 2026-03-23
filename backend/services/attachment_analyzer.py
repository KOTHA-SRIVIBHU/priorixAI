import os
import base64
import io
import logging
import pandas as pd
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from services.email_fetcher import refresh_gmail_token

from utils.supabase_client import supabase
import requests

logger = logging.getLogger(__name__)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")

def download_attachment(service, message_id, attachment_id):
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

def analyze_excel(file_data, user_id_to_detect, filename):
    """Search for user ID in Excel/CSV data."""
    print(f"Analyzing file {filename} for ID: {user_id_to_detect}")
    try:
        # Determine file type from extension
        if filename.endswith('.xlsx') or filename.endswith('.xls'):
            df = pd.read_excel(io.BytesIO(file_data), engine='openpyxl')
        elif filename.endswith('.csv'):
            # Try multiple encodings for CSV
            for enc in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    df = pd.read_csv(io.BytesIO(file_data), encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise Exception("Could not decode CSV file")
        else:
            return False, ""

        # Convert all cells to string and search
        found = df.astype(str).apply(lambda x: x.str.contains(user_id_to_detect, case=False, na=False)).any().any()
        if found:
            mask = df.astype(str).apply(lambda x: x.str.contains(user_id_to_detect, case=False, na=False)).any(axis=1)
            matched_rows = df[mask]
            context = matched_rows.to_string()
            print(f"✅ ID found! Context: {context[:200]}")
            return True, context
        else:
            print("❌ ID not found.")
            return False, ""
    except Exception as e:
        print(f"Error parsing attachment: {e}")
        return False, ""


def send_telegram_selection_alert(chat_id, email_subject, context):
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
    print(f"📎 process_attachments called for email {email_record['id']}")
    # Get user's ID detection string
    user = supabase.table("profiles").select("user_id_detection").eq("id", email_record["user_id"]).execute()
    if not user.data or not user.data[0]["user_id_detection"]:
        print("No user_id_detection set for this user.")
        return
    user_id_to_detect = user.data[0]["user_id_detection"]
    
    # Get email account to build Gmail service
    account = supabase.table("email_accounts").select("*").eq("id", email_record["email_account_id"]).execute()
    if not account.data:
        print("No email account found.")
        return
    account_record = account.data[0]
    
    # Refresh token and build service
    creds = refresh_gmail_token(account_record)
    service = build("gmail", "v1", credentials=creds)
    
    # Fetch full message to get attachment parts
    try:
        msg = service.users().messages().get(userId='me', id=email_record["message_id"]).execute()
    except Exception as e:
        logger.error(f"Could not fetch full message {email_record['message_id']}: {e}")
        return
    
    # Recursively find attachments with attachmentId
    def find_attachment_parts(part):
        attachment_list = []
        if part.get('filename') and part.get('body', {}).get('attachmentId'):
            attachment_list.append({
                'filename': part['filename'],
                'attachmentId': part['body']['attachmentId']
            })
        if 'parts' in part:
            for subpart in part['parts']:
                attachment_list.extend(find_attachment_parts(subpart))
        return attachment_list
    
    all_parts = []
    if 'parts' in msg['payload']:
        for part in msg['payload']['parts']:
            all_parts.extend(find_attachment_parts(part))
    else:
        all_parts = find_attachment_parts(msg['payload'])
    
    for att in all_parts:
        if att['filename'].lower().endswith(('.xlsx', '.xls', '.csv')):
            print(f"Found Excel attachment: {att['filename']}")
            file_data = download_attachment(service, email_record["message_id"], att['attachmentId'])
            if file_data:
                found, context = analyze_excel(file_data, user_id_to_detect, att['filename'])
                if found:
                    # Get Telegram chat_id
                    profile = supabase.table("profiles").select("telegram_chat_id").eq("id", email_record["user_id"]).execute()
                    if profile.data and profile.data[0]["telegram_chat_id"]:
                        send_telegram_selection_alert(
                            profile.data[0]["telegram_chat_id"],
                            email_record["subject"],
                            context
                        )
                        # Update classification to mark as selection
                        supabase.table("classifications").update({
                            "category": "selection",
                            "importance_score": 0.95,
                            "action_required": True
                        }).eq("email_id", email_record["id"]).execute()
                        print("Updated classification to selection.")
                    break