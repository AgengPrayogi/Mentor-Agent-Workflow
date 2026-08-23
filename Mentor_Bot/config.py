"""
config.py
Tanggung jawab: load .env, validasi, dan expose konstanta konfigurasi.
File lain (mentor_bot.py, attachment.py, main.py) tinggal:
    from config import DISCORD_BOT_TOKEN, N8N_WEBHOOK_URL, DISCORD_CHANNEL_ID
"""

import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

print("\n" + "=" * 70)
print("LOADING CONFIG")
print("=" * 70)

if not DISCORD_BOT_TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN tidak ditemukan di .env")

if not N8N_WEBHOOK_URL:
    raise RuntimeError("N8N_WEBHOOK_URL tidak ditemukan di .env")

if not DISCORD_CHANNEL_ID:
    raise RuntimeError("DISCORD_CHANNEL_ID tidak ditemukan di .env")

try:
    DISCORD_CHANNEL_ID = int(DISCORD_CHANNEL_ID)
except ValueError:
    raise RuntimeError(
        f"DISCORD_CHANNEL_ID harus berupa angka, ditemukan: {DISCORD_CHANNEL_ID}"
    )

print("✓ Config loaded:")
print("  - Bot Token: configured")
print(f"  - Webhook URL: {N8N_WEBHOOK_URL}")
print(f"  - Channel ID: {DISCORD_CHANNEL_ID}")
print("=" * 70 + "\n")
