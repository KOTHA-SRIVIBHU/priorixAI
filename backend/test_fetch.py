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

print(f"Found account: {account['email_address']}")

# Build credentials
creds = Credentials(
    token=account['access_token'],
    refresh_token=account['refresh_token'],
    token_uri="https://oauth2.googleapis.com/token",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    scopes=["https://www.googleapis.com/auth/gmail.readonly"]
)

# Refresh if expired
if creds.expired:
    print("Token expired, refreshing...")
    creds.refresh(Request())
    print("Token refreshed")

# Build service
service = build("gmail", "v1", credentials=creds)

# List recent messages (without after filter)
response = service.users().messages().list(userId='me', maxResults=10).execute()
messages = response.get('messages', [])
print(f"Found {len(messages)} messages in inbox")

# Print details of first message
if messages:
    msg = service.users().messages().get(userId='me', id=messages[0]['id'], format='metadata').execute()
    headers = {h['name']: h['value'] for h in msg['payload']['headers']}
    print("First email subject:", headers.get('Subject', 'No subject'))