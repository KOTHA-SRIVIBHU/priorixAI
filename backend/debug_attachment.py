import os
from dotenv import load_dotenv
load_dotenv()

from utils.supabase_client import supabase
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# Get first active email account
result = supabase.table('email_accounts').select('*').eq('is_active', True).execute()
if not result.data:
    print("No active email accounts found")
    exit()
account = result.data[0]

print(f"Using account: {account['email_address']}")

# Build credentials
creds = Credentials(
    token=account['access_token'],
    refresh_token=account['refresh_token'],
    token_uri="https://oauth2.googleapis.com/token",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    scopes=["https://www.googleapis.com/auth/gmail.readonly"]
)

if creds.expired:
    creds.refresh(Request())

service = build("gmail", "v1", credentials=creds)

# Get recent messages
response = service.users().messages().list(userId='me', maxResults=10).execute()
messages = response.get('messages', [])

for msg in messages:
    # Get full message
    full_msg = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
    payload = full_msg.get('payload', {})
    
    print(f"\nMessage ID: {msg['id']}")
    print(f"Subject: {next((h['value'] for h in payload.get('headers', []) if h['name'] == 'Subject'), 'No subject')}")
    
    # Recursive function to find attachments
    def find_attachments(part):
        if part.get('filename'):
            print(f"  Attachment: {part['filename']} (MIME: {part['mimeType']})")
        if 'parts' in part:
            for subpart in part['parts']:
                find_attachments(subpart)
    
    # Check main payload
    if 'parts' in payload:
        for part in payload['parts']:
            find_attachments(part)
    else:
        find_attachments(payload)