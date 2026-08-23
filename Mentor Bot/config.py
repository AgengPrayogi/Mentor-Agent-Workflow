import os
from dotenv import load_dotenv

# Load .env
load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

# Validation
print("\n" + "="*70)
print("STARTING MENTOR AGENT BOT")
print("="*70)

if not DISCORD_BOT_TOKEN:
    print("❌ ERROR: DISCORD_BOT_TOKEN not found in .env")
    exit(1)

if not N8N_WEBHOOK_URL:
    print("❌ ERROR: N8N_WEBHOOK_URL not found in .env")
    exit(1)

if not DISCORD_CHANNEL_ID:
    print("❌ ERROR: DISCORD_CHANNEL_ID not found in .env")
    exit(1)

try:
    DISCORD_CHANNEL_ID = int(DISCORD_CHANNEL_ID)
except ValueError:
    print(f"❌ ERROR: DISCORD_CHANNEL_ID must be number, got: {DISCORD_CHANNEL_ID}")
    exit(1)

print(f"\n✓ Config loaded:")
print(f"  - Bot Token: {DISCORD_BOT_TOKEN[:30]}...")
print(f"  - Webhook URL: {N8N_WEBHOOK_URL}")
print(f"  - Channel ID: {DISCORD_CHANNEL_ID}")
print("="*70 + "\n")