"""
mentor_bot.py
Tanggung jawab: Discord client — terima pesan, panggil attachment extractor,
POST ke n8n webhook, kirim balik response ke Discord.
Konfigurasi dan ekstraksi file sudah dipindah ke config.py dan attachment.py.
"""

import discord
import requests

from config import DISCORD_BOT_TOKEN, N8N_WEBHOOK_URL, DISCORD_CHANNEL_ID
from attachment import process_attachments, build_file_context

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

    loading_msg = None

    try:
        # Step 1: Loading message
        print("\n[1/6] Sending loading message...")
        loading_msg = await message.reply("⏳ Mentor Agent analyzing your question...")
        print("      ✓ Loading message sent")

        # Step 2: Extract attachments (structured)
        attachment_results = []
        file_context = ""
        file_warnings = []

        if message.attachments:
            print(f"\n[2/6] Extracting {len(message.attachments)} attachment(s)...")
            attachment_results = process_attachments(message.attachments)
            file_context, file_warnings = build_file_context(attachment_results)

            extracted_count = sum(
                1 for r in attachment_results if r["extraction_status"] == "extracted"
            )
            print(f"      ✓ {extracted_count}/{len(attachment_results)} file(s) extracted "
                  f"({len(file_context)} chars total)")
            for w in file_warnings:
                print(f"      {w}")

        # Kirim warning ke user SEBELUM proses lanjut, supaya mereka tahu
        # file mana yang benar-benar diproses walau nanti request gagal.
        if file_warnings:
            await message.channel.send("\n".join(file_warnings))

        # Kalau user upload attachment tapi SEMUA gagal/unsupported/kosong,
        # dan tidak ada teks pesan sama sekali -> tidak ada yang bisa dikirim
        # ke mentor. Beri tahu user secara eksplisit alih-alih lanjut dengan
        # payload kosong yang membingungkan di sisi n8n/LLM.
        if message.attachments and not file_context and not message.content.strip():
            print("      ❌ Semua attachment gagal diproses, tidak ada teks pesan")
            await loading_msg.edit(
                content="❌ Tidak ada file yang berhasil diproses, dan tidak ada teks "
                        "pesan yang menyertainya. Coba kirim ulang dengan format yang "
                        "didukung, atau sertakan pertanyaan sebagai teks."
            )
            print("-" * 70 + "\n")
            return

        # Step 3: Build payload
        print("\n[3/6] Preparing payload...")
        payload = {
            "text": message.content,
            "channel_id": str(message.channel.id),
            "user_id": str(message.author.id),
            "author_name": str(message.author),
            "file_context": file_context,
            "attachments": [
                {
                    "filename": r["filename"],
                    "file_type": r["file_type"],
                    "extraction_status": r["extraction_status"],
                    "metadata": r.get("metadata"),
                }
                for r in attachment_results
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
            await loading_msg.edit(
                content="⏱️ Mentor butuh waktu terlalu lama untuk merespons "
                        "(kemungkinan API LLM sedang lambat). Coba kirim lagi sebentar lagi."
            )
            print("-" * 70 + "\n")
            return
        except requests.exceptions.ConnectionError:
            print("      ❌ CONNECTION ERROR")
            await loading_msg.edit(
                content="❌ Tidak bisa terhubung ke server mentor (n8n). "
                        "Kemungkinan service n8n sedang down — cek dari sisi server."
            )
            print("-" * 70 + "\n")
            return
        except Exception as e:
            print(f"      ❌ REQUEST ERROR: {type(e).__name__}")
            await loading_msg.edit(content=f"❌ Terjadi error saat mengirim request: {type(e).__name__}")
            print("-" * 70 + "\n")
            return

        if response.status_code >= 400:
            print(f"      ❌ HTTP ERROR: {response.status_code}")
            await loading_msg.edit(
                content=f"❌ Server mentor merespons dengan error (HTTP {response.status_code}). "
                        "Cek execution history di n8n untuk detail."
            )
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
            await loading_msg.edit(
                content="❌ Response dari server mentor tidak valid (bukan JSON). "
                        "Kemungkinan ada error di workflow n8n."
            )
            print("-" * 70 + "\n")
            return

        mentor_response = response_data.get("mentor_response")

        if not mentor_response:
            print("      ❌ NO MENTOR_RESPONSE in data!")
            print(f"      Keys: {list(response_data.keys())}")
            await loading_msg.edit(
                content="❌ Server mentor tidak mengembalikan jawaban "
                        "(field 'mentor_response' kosong/tidak ada). Cek node output di n8n."
            )
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
        error_text = f"❌ Terjadi error tak terduga: {type(e).__name__}: {str(e)[:150]}"
        try:
            if loading_msg is not None:
                await loading_msg.edit(content=error_text)
            else:
                await message.reply(error_text)
        except Exception:
            pass  # kalau Discord API sendiri yang error, tidak ada lagi yang bisa dilakukan
        print("-" * 70 + "\n")


def run_bot():
    print("🚀 Connecting to Discord...\n")
    client.run(DISCORD_BOT_TOKEN)