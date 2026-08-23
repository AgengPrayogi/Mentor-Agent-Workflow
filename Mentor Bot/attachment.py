import requests
import os
# File attachment config
SUPPORTED_TEXT_EXTENSIONS = {
    ".py", ".txt", ".md", ".json", ".csv", ".js", ".ts",
    ".sql", ".yaml", ".yml", ".html", ".css", ".log"
}

SUPPORTED_NOTEBOOK_EXTENSIONS = {
    ".ipynb"
}

MAX_FILE_SIZE_BYTES = 500_000  # 500 KB per file, cukup untuk source code / dataset kecil
MAX_TOTAL_FILE_CHARS = 500_000  # batas total karakter isi file yang dikirim ke LLM

def extract_file(attachment):
    ext = get_extension(attachment.filename)

    if ext in SUPPORTED_TEXT_EXTENSIONS:
        return extract_text_file(attachment)

    if ext == ".ipynb":
        return extract_notebook(attachment)

    return unsupported_file(attachment)

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