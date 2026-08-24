"""
config.py
Tanggung jawab: load .env, validasi, dan expose konstanta konfigurasi.
File lain (mentor_bot.py, attachment.py, main.py) tinggal:
    from config import DISCORD_BOT_TOKEN, N8N_WEBHOOK_URL, DISCORD_CHANNEL_ID

.env dicari relatif dari lokasi file ini (config.py), naik satu folder
ke root repo -- jadi tidak masalah dari direktori mana kamu menjalankan
`python main.py`.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# config.py ada di: Mentor-Agent-Workflow/Mentor Bot/config.py
# .env ada di:      Mentor-Agent-Workflow/.env
# jadi naik satu folder dari config.py untuk sampai ke root repo.
BASE_DIR = Path(__file__).resolve().parent          # .../Mentor Bot
ROOT_DIR = BASE_DIR.parent                          # .../Mentor-Agent-Workflow
ENV_PATH = ROOT_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

print("\n" + "=" * 70)
print("LOADING CONFIG")
print("=" * 70)
print(f"Mencari .env di: {ENV_PATH}")

if not DISCORD_BOT_TOKEN:
    raise RuntimeError(
        f"DISCORD_BOT_TOKEN tidak ditemukan. Pastikan file .env ada di: {ENV_PATH}"
    )

if not N8N_WEBHOOK_URL:
    raise RuntimeError(
        f"N8N_WEBHOOK_URL tidak ditemukan. Pastikan file .env ada di: {ENV_PATH}"
    )

if not DISCORD_CHANNEL_ID:
    raise RuntimeError(
        f"DISCORD_CHANNEL_ID tidak ditemukan. Pastikan file .env ada di: {ENV_PATH}"
    )

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