"""
mentor_bot.py
Tanggung jawab: Discord client — terima pesan, panggil attachment extractor,
POST ke n8n webhook, kirim balik response ke Discord.
Konfigurasi dan ekstraksi file sudah dipindah ke config.py dan attachment.py.
"""

import discord
import requests

from config import DISCORD_BOT_TOKEN, N8N_WEBHOOK_URL, DISCORD_CHANNEL_ID
from attachment import extract_attachments_text

intents = discord.Intents.default()
intents.message_content = True  # CRITICAL: bot perlu baca isi pesan

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print("\n" + "=" * 70)
    print("✓ BOT READY")
    print("=" * 70)
    print(f"Connected as: {client.user}")
    print(f"Listening to channel: {DISCORD_CHANNEL_ID}")
    print("Waiting for messages...\n")


@client.event
async def on_message(message):
    print("\n" + "-" * 70)
    print("📨 MESSAGE DETECTED")
    print("-" * 70)
    print(f"Author: {message.author}")
    print(f"Channel ID: {message.channel.id}")
    print(f"Message: {message.content[:50]}...")
    print(f"Attachments: {len(message.attachments)}")

    # FILTER 1: Ignore own messages
    if message.author == client.user:
        print("⚠️  Skipping: Own message")
        print("-" * 70 + "\n")
        return

    # FILTER 2: Only respond in specific channel
    if message.channel.id != DISCORD_CHANNEL_ID:
        print(f"⚠️  Skipping: Wrong channel (expected {DISCORD_CHANNEL_ID})")
        print("-" * 70 + "\n")
        return

    # FILTER 3: Skip empty messages (kecuali ada attachment)
    if not message.content.strip() and not message.attachments:
        print("⚠️  Skipping: Empty message (no text, no attachments)")
        print("-" * 70 + "\n")
        return

    # FILTER 4: Skip command messages
    if message.content.startswith("!"):
        print("⚠️  Skipping: Command message (starts with !)")
        print("-" * 70 + "\n")
        return

    print("✓ Message passed all filters - PROCESSING")

    try:
        # Step 1: Loading message
        print("\n[1/6] Sending loading message...")
        loading_msg = await message.reply("⏳ Mentor Agent analyzing your question...")
        print("      ✓ Loading message sent")

        # Step 2: Extract attachments
        file_context = ""
        file_warnings = []
        if message.attachments:
            print(f"\n[2/6] Extracting {len(message.attachments)} attachment(s)...")
            file_context, file_warnings = extract_attachments_text(message.attachments)
            print(f"      ✓ Extracted {len(file_context)} chars of file content")
            for w in file_warnings:
                print(f"      {w}")

        if file_warnings:
            await message.channel.send("\n".join(file_warnings))

        # Step 3: Build payload
        print("\n[3/6] Preparing payload...")
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
        print("      ✓ Payload ready")

        # Step 4: POST to n8n
        print(f"\n[4/6] POSTing to webhook...")
        print(f"      URL: {N8N_WEBHOOK_URL}")

        try:
            response = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=120)
            print(f"      ✓ Status: {response.status_code}")
        except requests.exceptions.Timeout:
            print("      ❌ TIMEOUT: Webhook took too long")
            await loading_msg.edit(content="⏱️ Request timed out (Groq API slow, try again)")
            print("-" * 70 + "\n")
            return
        except requests.exceptions.ConnectionError:
            print("      ❌ CONNECTION ERROR")
            await loading_msg.edit(content="❌ Cannot connect to n8n webhook")
            print("-" * 70 + "\n")
            return
        except Exception:
            print("      ❌ REQUEST ERROR")
            await loading_msg.edit(content="❌ Request error")
            print("-" * 70 + "\n")
            return

        # Step 5: Parse response
        print("\n[5/6] Parsing response...")
        try:
            response_data = response.json()
            print("      ✓ JSON parsed")
        except Exception:
            print("      ❌ JSON PARSE ERROR")
            print(f"      Raw: {response.text[:100]}")
            await loading_msg.edit(content="❌ Parse error")
            print("-" * 70 + "\n")
            return

        mentor_response = response_data.get("mentor_response")

        if not mentor_response:
            print("      ❌ NO MENTOR_RESPONSE in data!")
            print(f"      Keys: {list(response_data.keys())}")
            await loading_msg.edit(content="❌ No response from mentor")
            print("-" * 70 + "\n")
            return

        print(f"      ✓ Got response ({len(mentor_response)} chars)")

        # Step 6: Send response (split kalau > 1900 char)
        print("\n[6/6] Updating Discord...")
        if len(mentor_response) > 1900:
            chunks = [mentor_response[i:i + 1900] for i in range(0, len(mentor_response), 1900)]
            await loading_msg.edit(content=chunks[0])
            print("      ✓ Main message updated")
            for i, chunk in enumerate(chunks[1:], 1):
                await message.channel.send(chunk)
                print(f"      ✓ Additional message {i} sent")
        else:
            await loading_msg.edit(content=mentor_response)
            print("      ✓ Message updated")

        print("\n" + "=" * 70)
        print("✅ SUCCESS - Response sent to Discord!")
        print("=" * 70 + "\n")

    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {type(e).__name__}: {e}")
        try:
            await loading_msg.edit(content=f"❌ Error: {str(e)[:100]}")
        except Exception:
            await message.reply("❌ Error")
        print("-" * 70 + "\n")


def run_bot():
    print("🚀 Connecting to Discord...\n")
    client.run(DISCORD_BOT_TOKEN)