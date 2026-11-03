"""Run ONCE to log in and print a SESSION_STRING.
The string = full access to your Telegram account. Never share it / commit it."""
import os
from dotenv import load_dotenv
from pyrogram import Client

load_dotenv()
api_id = int(os.getenv("API_ID") or input("API_ID: "))
api_hash = os.getenv("API_HASH") or input("API_HASH: ")

with Client("tmp", api_id=api_id, api_hash=api_hash, in_memory=True) as app:
    print("\n=== SESSION_STRING (keep secret) ===\n")
    print(app.export_session_string())
    print("\nPut it in .env as SESSION_STRING=...")
