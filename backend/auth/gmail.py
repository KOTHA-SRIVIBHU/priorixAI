import os
import time
import traceback
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from utils.supabase_client import supabase
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/auth/gmail", tags=["gmail"])

CLIENT_CONFIG = {
    "web": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [os.getenv("GOOGLE_REDIRECT_URI")],
    }
}
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Simple in-memory store for flows (keyed by state)
flow_store = {}
FLOW_EXPIRY_SECONDS = 600  # 10 minutes

def cleanup_flow_store():
    """Remove expired flows."""
    now = time.time()
    expired = [state for state, (flow, ts) in flow_store.items() if now - ts > FLOW_EXPIRY_SECONDS]
    for state in expired:
        del flow_store[state]

@router.get("/login")
async def gmail_login(telegram_chat_id: str):
    logger.info(f"Login requested for telegram_chat_id: {telegram_chat_id}")
    cleanup_flow_store()
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
    flow.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    state = f"tg:{telegram_chat_id}"
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=state,
        prompt="consent"
    )
    # Store flow with timestamp
    flow_store[state] = (flow, time.time())
    logger.info(f"Stored flow for state {state}")
    logger.info(f"Redirecting to: {authorization_url}")
    return RedirectResponse(authorization_url)

@router.get("/callback")
async def gmail_callback(request: Request, code: str = None, state: str = None):
    try:
        logger.info(f"Callback received with code: {code[:20]}... state: {state}")
        cleanup_flow_store()

        if not state:
            raise HTTPException(status_code=400, detail="Missing state parameter")
        if not state.startswith("tg:"):
            raise HTTPException(status_code=400, detail="Invalid state format")

        # Retrieve the flow from store
        if state not in flow_store:
            raise HTTPException(status_code=400, detail="State not found. Please restart the authorization.")
        flow, _ = flow_store.pop(state)  # remove after use

        telegram_chat_id = state[3:]

        # Look up user_id from profiles
        result = supabase.table("profiles").select("id").eq("telegram_chat_id", telegram_chat_id).execute()
        logger.info(f"Profile lookup result: {result.data}")
        if not result.data:
            raise HTTPException(status_code=404, detail="User not found in profiles")
        user_id = result.data[0]["id"]

        # Fetch token using the flow
        try:
            flow.fetch_token(code=code)
        except Exception as e:
            logger.error(f"Token fetch error: {e}")
            raise HTTPException(status_code=400, detail=f"Failed to fetch token: {e}")
        credentials = flow.credentials

        # Get user's email
        service = build("gmail", "v1", credentials=credentials)
        profile = service.users().getProfile(userId="me").execute()
        email_address = profile["emailAddress"]
        logger.info(f"Email address: {email_address}")

        # Store tokens
        data = {
            "user_id": user_id,
            "email_address": email_address,
            "provider": "gmail",
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_expires_at": credentials.expiry.isoformat() if credentials.expiry else None,
            "is_active": True,
        }
        logger.info(f"Inserting data: {data}")
        supabase.table("email_accounts").upsert(data, on_conflict="user_id,email_address").execute()
        logger.info("Successfully inserted/updated email account")

        return HTMLResponse(
            "<h1>✅ Email account connected successfully!</h1>"
            "<p>You can close this window and return to Telegram.</p>"
        )
    except Exception as e:
        logger.error(f"Callback error: {e}")
        logger.error(traceback.format_exc())
        return HTMLResponse(
            f"<h1>❌ Error connecting email account</h1>"
            f"<p><strong>Error:</strong> {e}</p>"
            f"<p>Please try again or contact support.</p>",
            status_code=500
        )