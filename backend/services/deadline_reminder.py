import dateparser
from datetime import datetime, timedelta
import logging

def extract_deadlines(email_record):
    """Extract deadline dates from email body and subject."""
    text = f"{email_record['subject']} {email_record['snippet']}"
    # Use dateparser to find dates
    # For simplicity, we'll look for patterns like "deadline: March 25, 2026"
    import re
    patterns = [
        r'(?:deadline|due|expiration|closing)\s*:?\s*(\w+ \d{1,2},? \d{4})',
        r'(\d{1,2}/\d{1,2}/\d{4})'
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            date_str = match.group(1)
            date = dateparser.parse(date_str)
            if date:
                return date
    return None

def schedule_reminders(email_id, deadline_date):
    """Insert deadline into database."""
    supabase.table('deadlines').insert({
        'email_id': email_id,
        'deadline_date': deadline_date.isoformat(),
        'reminder_24h_sent': False,
        'reminder_6h_sent': False,
        'reminder_1h_sent': False
    }).execute()

def check_and_send_reminders():
    """Background task: check deadlines and send reminders."""
    now = datetime.now()
    deadlines = supabase.table('deadlines').select('*').execute()
    for dl in deadlines.data:
        deadline = datetime.fromisoformat(dl['deadline_date'])
        time_left = deadline - now
        if not dl['reminder_24h_sent'] and time_left <= timedelta(hours=24):
            # Send reminder
            send_reminder(dl['user_id'], dl['email_id'], "24 hours")
            supabase.table('deadlines').update({'reminder_24h_sent': True}).eq('id', dl['id']).execute()
        # Similar for 6h and 1h