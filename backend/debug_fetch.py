import os
from dotenv import load_dotenv
load_dotenv()

from utils.supabase_client import supabase
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# Get the account
result = supabase.table('email_accounts').select('*').eq('is_active', True).execute()
if not result.data:
    print("No account")
    exit()
acc = result.data[0]

creds = Credentials(
    token=acc['access_token'],
    refresh_token=acc['refresh_token'],
    token_uri="https://oauth2.googleapis.com/token",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    scopes=["https://www.googleapis.com/auth/gmail.readonly"]
)
if creds.expired:
    creds.refresh(Request())
service = build("gmail", "v1", credentials=creds)

# List recent 10 messages
response = service.users().messages().list(userId='me', maxResults=10).execute()
messages = response.get('messages', [])
print(f"Found {len(messages)} recent messages")
for msg in messages:
    full = service.users().messages().get(userId='me', id=msg['id'], format='metadata').execute()
    headers = {h['name']: h['value'] for h in full['payload']['headers']}
    print(f"{full['id']}: {headers.get('Subject', 'No subject')} - {full.get('snippet', '')[:50]}")