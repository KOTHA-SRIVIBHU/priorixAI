import os
from dotenv import load_dotenv

# Load environment variables BEFORE importing other modules
load_dotenv()  # This will look for .env in the current directory (backend/)

from fastapi import FastAPI
from auth import gmail

app = FastAPI(title="Email Alert System Backend")

app.include_router(gmail.router)

@app.get("/")
async def root():
    return {"message": "Email Alert System Backend is running"}