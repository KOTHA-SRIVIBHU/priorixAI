import time
from services.email_fetcher import run_fetcher
# Actually, we want to integrate both: fetch, then classify, then sleep.
# We'll create a loop that does both.

if __name__ == "__main__":
    while True:
        # Fetch new emails
        from services.email_fetcher import fetch_new_emails, get_active_accounts
        # But we need to rework to handle multiple accounts properly
        # For simplicity, we'll just run the fetcher loop (it already loops)
        # And then after each fetch cycle, run the classifier.
        # However, the fetcher already has its own loop.
        # Better: run classifier after each fetch, but within the same script.
        # Let's adapt.