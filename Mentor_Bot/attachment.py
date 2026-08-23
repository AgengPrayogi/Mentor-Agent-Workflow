"""
attachment.py
Tanggung jawab: deteksi tipe file, download, dan ekstraksi isi attachment
Discord menjadi teks yang siap dikirim ke LLM (file_context).

Fungsi utama yang dipakai dari luar:
    extract_attachments_text(attachments) -> (combined_text, warnings)
"""

import json
import os
import requests

# --- Konfigurasi tipe file ---

SUPPORTED_TEXT_EXTENSIONS = {
    ".py", ".txt", ".md", ".json", ".csv", ".js", ".ts",
    ".sql", ".yaml", ".yml", ".html", ".css", ".log",
}

SUPPORTED_NOTEBOOK_EXTENSIONS = {".ipynb"}

MAX_FILE_SIZE_BYTES = 500_000   # 500 KB per file
MAX_TOTAL_FILE_CHARS = 30_000   # batas total karakter isi file yang dikirim ke LLM


# --- Helper ---

def get_extension(filename):
    return os.path.splitext(filename)[1].lower()


def _download(attachment):
    """Download isi attachment sebagai text (raise kalau gagal)."""
    resp = requests.get(attachment.url, timeout=30)
    resp.raise_for_status()
    return resp.content.decode("utf-8", errors="replace")


# --- Extractor per tipe file ---

def extract_text_file(attachment):
    """
    Extract file source-code / text biasa (.py, .md, .json, .csv, dst).
    Return dict: {status, filename, type, content} atau {status: 'error', ...}
    """
    try:
        content = _download(attachment)
    except Exception as e:
        return {
            "status": "error",
            "filename": attachment.filename,
            "type": "text",
            "error": f"Gagal download: {type(e).__name__}",
        }

    return {
        "status": "extracted",
        "filename": attachment.filename,
        "type": "text",
        "content": content,
    }


def extract_notebook(attachment):
    """
    Extract .ipynb menjadi teks ternormalisasi: markdown cells, code cells,
    dan outputnya, urut sesuai posisi cell di notebook.
    """
    try:
        raw = _download(attachment)
    except Exception as e:
        return {
            "status": "error",
            "filename": attachment.filename,
            "type": "notebook",
            "error": f"Gagal download: {type(e).__name__}",
        }

    try:
        notebook = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "status": "error",
            "filename": attachment.filename,
            "type": "notebook",
            "error": "File .ipynb tidak valid (bukan JSON yang benar)",
        }

    parts = [f"=== NOTEBOOK: {attachment.filename} ==="]

    for i, cell in enumerate(notebook.get("cells", []), start=1):
        cell_type = cell.get("cell_type")
        source = "".join(cell.get("source", []))

        if cell_type == "markdown":
            parts.append(f"\n[MARKDOWN CELL {i}]\n{source}")

        elif cell_type == "code":
            parts.append(f"\n[CODE CELL {i}]\n{source}")

            for output in cell.get("outputs", []):
                output_text = _extract_notebook_output_text(output)
                if output_text:
                    parts.append(f"\n[OUTPUT CELL {i}]\n{output_text}")

    content = "\n".join(parts)

    return {
        "status": "extracted",
        "filename": attachment.filename,
        "type": "notebook",
        "content": content,
    }


def _extract_notebook_output_text(output):
    """Ambil teks dari satu output cell notebook (stream, execute_result, error)."""
    output_type = output.get("output_type")

    if output_type == "stream":
        return "".join(output.get("text", []))

    if output_type in ("execute_result", "display_data"):
        data = output.get("data", {})
        if "text/plain" in data:
            return "".join(data["text/plain"])
        return None

    if output_type == "error":
        ename = output.get("ename", "")
        evalue = output.get("evalue", "")
        return f"{ename}: {evalue}"

    return None


def unsupported_file(attachment):
    return {
        "status": "unsupported",
        "filename": attachment.filename,
        "type": "unknown",
        "error": f"Tipe file .{get_extension(attachment.filename).lstrip('.')} belum didukung",
    }


def extract_file(attachment):
    """Router: pilih extractor berdasarkan ekstensi file."""
    ext = get_extension(attachment.filename)

    if ext in SUPPORTED_TEXT_EXTENSIONS:
        return extract_text_file(attachment)

    if ext in SUPPORTED_NOTEBOOK_EXTENSIONS:
        return extract_notebook(attachment)

    return unsupported_file(attachment)


# --- Entry point yang dipakai mentor_bot.py ---

def extract_attachments_text(attachments):
    """
    Download dan ekstrak isi setiap attachment Discord yang didukung
    (.py, .ipynb, .json, .csv, dll — lihat SUPPORTED_TEXT_EXTENSIONS
    dan SUPPORTED_NOTEBOOK_EXTENSIONS).

    Return: (combined_text, warnings)
        combined_text -> siap disisipkan ke prompt / payload n8n
        warnings      -> list pesan untuk ditampilkan ke user (file dilewati,
                          dipotong, atau gagal diproses)
    """
    parts = []
    warnings = []
    total_chars = 0

    for att in attachments:
        if att.size > MAX_FILE_SIZE_BYTES:
            warnings.append(
                f"⚠️ `{att.filename}` dilewati (ukuran {att.size} bytes > batas {MAX_FILE_SIZE_BYTES})"
            )
            continue

        result = extract_file(att)

        if result["status"] == "unsupported":
            warnings.append(f"⚠️ `{att.filename}` dilewati ({result['error']})")
            continue

        if result["status"] == "error":
            warnings.append(f"⚠️ `{att.filename}` gagal diproses: {result['error']}")
            continue

        content = result["content"]

        if total_chars + len(content) > MAX_TOTAL_FILE_CHARS:
            remaining = max(MAX_TOTAL_FILE_CHARS - total_chars, 0)
            content = content[:remaining] + "\n... (dipotong, terlalu panjang)"
            warnings.append(f"⚠️ `{att.filename}` dipotong karena total isi file melebihi batas")

        total_chars += len(content)

        if result["type"] == "notebook":
            parts.append(content)  # sudah punya header sendiri dari extract_notebook
        else:
            parts.append(f"=== FILE: {att.filename} ===\n{content}")

        if total_chars >= MAX_TOTAL_FILE_CHARS:
            break

    combined_text = "\n\n".join(parts)
    return combined_text, warnings
