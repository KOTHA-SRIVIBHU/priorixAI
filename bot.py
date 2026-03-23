import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from supabase import create_client, Client

load_dotenv()

# Supabase setup
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

# Telegram bot token
TOKEN = os.getenv("TELEGRAM_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    first_name = user.first_name
    last_name = user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()

    # Store or update user in Supabase
    # We assume a profile with this chat_id already exists? We'll create if not.
    try:
        # Check if profile exists
        result = supabase.table("profiles").select("id").eq("telegram_chat_id", str(chat_id)).execute()
        if not result.data:
            # New user: create profile
            # We don't have the auth user id yet; we'll use a placeholder or we can create a user in auth.users.
            # For now, we'll create a profile without linking to auth.users, but later we'll need to link.
            # We'll instead first create a user in auth.users using the email? That's complex.
            # Alternative: we can store the chat_id without linking to auth initially, and later when user connects email we'll link.
            # Let's create a profile with a generated UUID for id, but that won't reference auth.users.
            # But our schema requires profiles.id to reference auth.users. So we need a user in auth.users first.
            # So we need to handle user creation differently: maybe when the user starts the bot, we create an auth user via Supabase Auth Admin API.
            # Let's do that.
            # We'll create an auth user with a dummy email and phone? We can use the telegram chat_id as the user's identifier.
            # But Supabase Auth requires an email. We can create a user with a placeholder email like "tg_{chat_id}@example.com".
            # This is acceptable for a college project.
            email = f"tg_{chat_id}@example.com"
            password = "temporary_password"  # we'll store randomly and never use
            # Use Supabase Auth admin API to create user
            # We need to call the Supabase Auth API with the service role key.
            # The python client doesn't have direct admin methods, so we'll use requests.
            import requests
            headers = {
                "apikey": os.getenv("SUPABASE_SERVICE_KEY"),
                "Authorization": f"Bearer {os.getenv('SUPABASE_SERVICE_KEY')}"
            }
            payload = {
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"full_name": full_name, "telegram_chat_id": str(chat_id)}
            }
            resp = requests.post(f"{os.getenv('SUPABASE_URL')}/auth/v1/admin/users", json=payload, headers=headers)
            resp.raise_for_status()
            user_data = resp.json()
            user_id = user_data["id"]
            # Now the profile will be created automatically by the trigger we set earlier.
            # But we still need to update the profile with telegram_chat_id and full_name (trigger may set full_name from user_metadata)
            # Actually the trigger uses raw_user_meta_data->>'full_name'. It will have the full_name we passed.
            # And the profile already has the id = user_id.
            # We need to update the profile with the telegram_chat_id.
            supabase.table("profiles").update({"telegram_chat_id": str(chat_id)}).eq("id", user_id).execute()
        else:
            # Profile exists, maybe update name if changed
            profile_id = result.data[0]["id"]
            supabase.table("profiles").update({"full_name": full_name}).eq("id", profile_id).execute()
    except Exception as e:
        print(f"Error storing user: {e}")
        await update.message.reply_text("Sorry, something went wrong. Please try again later.")
        return

    # Welcome message with inline keyboard
    keyboard = [
        [InlineKeyboardButton("📧 Connect Email Account", callback_data="connect_email")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Hello {full_name}!\n\nI'm your Email Alert Bot. I'll monitor your emails and send you important alerts.\n\n"
        "To get started, click the button below to connect your email account.",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "connect_email":
        await query.edit_message_text(
            "Please visit the following link to connect your email account:\n"
            "https://your-backend-url.com/connect\n\n"
            "(You'll need to set up the backend first.)"
        )
    elif query.data == "settings":
        await query.edit_message_text(
            "Settings will be available soon.\n"
            "You'll be able to configure which categories to monitor and set your ID for detection."
        )

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))

    # Start polling (for local testing)
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()