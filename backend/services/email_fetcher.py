import os
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
import traceback
from email.utils import parsedate_to_datetime

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from utils.supabase_client import supabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FETCH_INTERVAL = 300

def refresh_gmail_token(account_record: Dict[str, Any]) -> Credentials:
    creds = Credentials(
        token=account_record['access_token'],
        refresh_token=account_record['refresh_token'],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        scopes=["https://www.googleapis.com/auth/gmail.readonly"]
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())
        supabase.table("email_accounts").update({
            "access_token": creds.token,
            "token_expires_at": creds.expiry.isoformat()
        }).eq("id", account_record['id']).execute()
    return creds

def fetch_new_emails(account_record: Dict[str, Any]):
    creds = refresh_gmail_token(account_record)
    service = build("gmail", "v1", credentials=creds)

    last_fetch = account_record.get('last_fetch_at')
    if last_fetch:
        if isinstance(last_fetch, str):
            last_fetch = datetime.fromisoformat(last_fetch)
    else:
        last_fetch = datetime.now() - timedelta(hours=1)

    query = f"after:{int(last_fetch.timestamp())}"
    print(f"Query: {query}")

    results = []
    inbox_results = list_emails(service, 'INBOX', query)
    print(f"Found {len(inbox_results)} emails in INBOX")
    results.extend(inbox_results)
    spam_results = list_emails(service, 'SPAM', query)
    print(f"Found {len(spam_results)} emails in SPAM")
    results.extend(spam_results)

    for msg in results:
        print(f"Storing email: {msg['id']}")
        store_email(account_record['user_id'], account_record['id'], msg)

    supabase.table("email_accounts").update({
        "last_fetch_at": datetime.now().isoformat()
    }).eq("id", account_record['id']).execute()

def list_emails(service, folder: str, query: str):
    """List emails from a specific folder (INBOX or SPAM)."""
    try:
        response = service.users().messages().list(
            userId='me',
            q=query,
            labelIds=[folder],
            maxResults=50
        ).execute()
        messages = response.get('messages', [])
        print(f"List {folder} returned {len(messages)} messages")
        results = []
        for msg in messages:
            # Fetch full message to get attachments
            full_msg = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='full'   # ← changed from 'metadata'
            ).execute()
            results.append(full_msg)
        return results
    except HttpError as e:
        logger.error(f"Error fetching emails from {folder}: {e}")
        return []


def store_email(user_id, account_id, msg):
    """Store email metadata in Supabase."""
    headers = {h['name']: h['value'] for h in msg['payload']['headers']}
    subject = headers.get('Subject', '')
    sender = headers.get('From', '')
    date_str = headers.get('Date', '')
    snippet = msg.get('snippet', '')

    # Parse date
    try:
        if date_str:
            parsed_date = parsedate_to_datetime(date_str)
            received_at = parsed_date.isoformat()
        else:
            received_at = datetime.now().isoformat()
    except Exception as e:
        logger.warning(f"Could not parse date '{date_str}': {e}")
        received_at = datetime.now().isoformat()

    # Recursively find attachments
    def extract_attachments(part, attachment_list):
        if part.get('filename'):
            attachment_list.append({
                'filename': part['filename'],
                'mimeType': part.get('mimeType'),
                'attachmentId': part.get('body', {}).get('attachmentId')
            })
        if 'parts' in part:
            for subpart in part['parts']:
                extract_attachments(subpart, attachment_list)

    attachment_list = []
    if 'parts' in msg['payload']:
        for part in msg['payload']['parts']:
            extract_attachments(part, attachment_list)
    else:
        extract_attachments(msg['payload'], attachment_list)

    print(f"📎 Attachments found: {attachment_list}")   # debug
    has_attachments = len(attachment_list) > 0

    data = {
        'user_id': user_id,
        'email_account_id': account_id,
        'message_id': msg['id'],
        'subject': subject,
        'sender': sender,
        'received_at': received_at,
        'snippet': snippet,
        'has_attachments': has_attachments,
        'attachment_info': attachment_list,
        'folder': 'inbox',  # refine later
        'processed': False
    }
    try:
        supabase.table('emails').upsert(data, on_conflict='user_id,message_id').execute()
        logger.info(f"Stored email {msg['id']} for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to store email {msg['id']}: {e}")





def run_fetcher():
    logger.info("Starting email fetcher service...")
    while True:
        try:
            accounts = supabase.table('email_accounts').select('*').eq('is_active', True).execute()
            for acc in accounts.data:
                fetch_new_emails(acc)
                time.sleep(1)
            time.sleep(FETCH_INTERVAL)
        except Exception as e:
            logger.error(f"Error in fetcher main loop: {e}")
            logger.error(traceback.format_exc())
            time.sleep(60)

if __name__ == "__main__":
    run_fetcher()