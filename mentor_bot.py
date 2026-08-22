# mentor_bot_simple.py - SIMPLIFIED VERSION (NO SYS IMPORT)
# Copy-paste seluruh file ini

import discord
import requests
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

# File attachment config
SUPPORTED_TEXT_EXTENSIONS = {
    ".py", ".txt", ".md", ".json", ".csv", ".js", ".ts",
    ".sql", ".yaml", ".yml", ".html", ".css", ".log"
}
MAX_FILE_SIZE_BYTES = 500_000  # 500 KB per file, cukup untuk source code / dataset kecil
MAX_TOTAL_FILE_CHARS = 30_000  # batas total karakter isi file yang dikirim ke LLM


def extract_attachments_text(attachments):
    """
    Download dan baca isi setiap attachment Discord yang bertipe teks.
    Mengembalikan (combined_text, warnings) — combined_text siap disisipkan
    ke prompt, warnings berisi pesan untuk ditampilkan ke user bila ada file
    yang dilewati (terlalu besar / tipe tidak didukung).
    """
    parts = []
    warnings = []
    total_chars = 0

    for att in attachments:
        filename = att.filename
        ext = os.path.splitext(filename)[1].lower()

        if ext not in SUPPORTED_TEXT_EXTENSIONS:
            warnings.append(f"⚠️ `{filename}` dilewati (tipe .{ext.lstrip('.')} belum didukung)")
            continue

        if att.size > MAX_FILE_SIZE_BYTES:
            warnings.append(f"⚠️ `{filename}` dilewati (ukuran {att.size} bytes > batas {MAX_FILE_SIZE_BYTES})")
            continue

        try:
            resp = requests.get(att.url, timeout=30)
            resp.raise_for_status()
            content = resp.content.decode("utf-8", errors="replace")
        except Exception as e:
            warnings.append(f"⚠️ Gagal download `{filename}`: {type(e).__name__}")
            continue

        if total_chars + len(content) > MAX_TOTAL_FILE_CHARS:
            remaining = max(MAX_TOTAL_FILE_CHARS - total_chars, 0)
            content = content[:remaining] + "\n... (dipotong, terlalu panjang)"
            warnings.append(f"⚠️ `{filename}` dipotong karena total isi file melebihi batas")

        total_chars += len(content)
        parts.append(f"=== FILE: {filename} ===\n{content}")

        if total_chars >= MAX_TOTAL_FILE_CHARS:
            break

    combined_text = "\n\n".join(parts)
    return combined_text, warnings

# Setup Discord client
intents = discord.Intents.default()
intents.message_content = True  # CRITICAL: Allow bot to read message content

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    """Called when bot connects"""
    print("\n" + "="*70)
    print("✓ BOT READY")
    print("="*70)
    print(f"Connected as: {client.user}")
    print(f"Listening to channel: {DISCORD_CHANNEL_ID}")
    print("Waiting for messages...\n")

@client.event
async def on_message(message):
    """Called when any message is received"""
    
    print("\n" + "-"*70)
    print("📨 MESSAGE DETECTED")
    print("-"*70)
    print(f"Author: {message.author}")
    print(f"Channel ID: {message.channel.id}")
    print(f"Message: {message.content[:50]}...")
    print(f"Attachments: {len(message.attachments)}")
    
    # FILTER 1: Ignore own messages
    if message.author == client.user:
        print("⚠️  Skipping: Own message")
        print("-"*70 + "\n")
        return
    
    # FILTER 2: Only respond in specific channel
    if message.channel.id != DISCORD_CHANNEL_ID:
        print(f"⚠️  Skipping: Wrong channel (expected {DISCORD_CHANNEL_ID})")
        print("-"*70 + "\n")
        return
    
    # FILTER 3: Skip empty messages (kecuali ada attachment yang menyertainya)
    if not message.content.strip() and not message.attachments:
        print("⚠️  Skipping: Empty message (no text, no attachments)")
        print("-"*70 + "\n")
        return
    
    # FILTER 4: Skip command messages (start with !)
    if message.content.startswith('!'):
        print("⚠️  Skipping: Command message (starts with !)")
        print("-"*70 + "\n")
        return
    
    print("✓ Message passed all filters - PROCESSING")
    
    try:
        # Step 1: Send loading message
        print("\n[1/5] Sending loading message...")
        loading_msg = await message.reply("⏳ Mentor Agent analyzing your question...")
        print("      ✓ Loading message sent")
        
        # Step 2: Extract attachments (if any)
        file_context = ""
        file_warnings = []
        if message.attachments:
            print(f"\n[2a/5] Extracting {len(message.attachments)} attachment(s)...")
            file_context, file_warnings = extract_attachments_text(message.attachments)
            print(f"      ✓ Extracted {len(file_context)} chars of file content")
            if file_warnings:
                for w in file_warnings:
                    print(f"      {w}")

        # Step 2b: Prepare payload
        print("\n[2/5] Preparing payload...")
        payload = {
            "text": message.content,
            "channel_id": str(message.channel.id),
            "user_id": str(message.author.id),
            "author_name": str(message.author),
            "file_context": file_context,
            "attachments": [
                {"filename": a.filename, "url": a.url, "size": a.size}
                for a in message.attachments
            ],
        }
        print(f"      ✓ Payload ready")

        if file_warnings:
            await message.channel.send("\n".join(file_warnings))

        # Step 3: POST to n8n webhook
        print(f"\n[3/5] POSTing to webhook...")
        print(f"      URL: {N8N_WEBHOOK_URL}")
        
        try:
            response = requests.post(
                N8N_WEBHOOK_URL,
                json=payload,
                timeout=120
            )
            print(f"      ✓ Status: {response.status_code}")
        except requests.exceptions.Timeout:
            print("      ❌ TIMEOUT: Webhook took too long")
            await loading_msg.edit(content="⏱️ Request timed out (Groq API slow, try again)")
            print("-"*70 + "\n")
            return
        except requests.exceptions.ConnectionError as e:
            print(f"      ❌ CONNECTION ERROR")
            await loading_msg.edit(content=f"❌ Cannot connect to n8n webhook")
            print("-"*70 + "\n")
            return
        except Exception as e:
            print(f"      ❌ REQUEST ERROR: {type(e).__name__}")
            await loading_msg.edit(content=f"❌ Request error")
            print("-"*70 + "\n")
            return
        
        # Step 4: Parse response
        print(f"\n[4/5] Parsing response...")
        try:
            response_data = response.json()
            print(f"      ✓ JSON parsed")
        except Exception as e:
            print(f"      ❌ JSON PARSE ERROR")
            print(f"      Raw: {response.text[:100]}")
            await loading_msg.edit(content=f"❌ Parse error")
            print("-"*70 + "\n")
            return
        
        # Step 5: Extract mentor response
        print(f"\n[5/5] Extracting response...")
        mentor_response = response_data.get("mentor_response")
        
        if not mentor_response:
            print(f"      ❌ NO MENTOR_RESPONSE in data!")
            print(f"      Keys: {list(response_data.keys())}")
            await loading_msg.edit(content="❌ No response from mentor")
            print("-"*70 + "\n")
            return
        
        print(f"      ✓ Got response ({len(mentor_response)} chars)")
        
        # Step 6: Send response
        print(f"\n[6/6] Updating Discord...")
        
        if len(mentor_response) > 1900:
            # Split into multiple messages
            messages = []
            for i in range(0, len(mentor_response), 1900):
                messages.append(mentor_response[i:i+1900])
            
            await loading_msg.edit(content=messages[0])
            print(f"      ✓ Main message updated")
            
            for i, msg_part in enumerate(messages[1:], 1):
                await message.channel.send(msg_part)
                print(f"      ✓ Additional message {i} sent")
        else:
            await loading_msg.edit(content=mentor_response)
            print(f"      ✓ Message updated")
        
        print("\n" + "="*70)
        print("✅ SUCCESS - Response sent to Discord!")
        print("="*70 + "\n")
    
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {type(e).__name__}: {e}")
        try:
            await loading_msg.edit(content=f"❌ Error: {str(e)[:100]}")
        except:
            await message.reply(f"❌ Error")
        print("-"*70 + "\n")

# Start bot
print("🚀 Connecting to Discord...\n")
try:
    client.run(DISCORD_BOT_TOKEN)
except Exception as e:
    print(f"❌ FATAL ERROR: {e}")
    exit(1)