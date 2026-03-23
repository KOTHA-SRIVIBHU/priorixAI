import os
import sys
from dotenv import load_dotenv
load_dotenv()

from services.email_fetcher import fetch_new_emails
from services.classifier import process_unclassified_emails
from utils.supabase_client import supabase

def main():
    accounts = supabase.table('email_accounts').select('*').eq('is_active', True).execute()
    for acc in accounts.data:
        fetch_new_emails(acc)
    process_unclassified_emails()

if __name__ == "__main__":
    main()