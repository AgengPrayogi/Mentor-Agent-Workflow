"""
attachment.py
Tanggung jawab: deteksi tipe file, download, dan ekstraksi isi attachment
Discord menjadi teks yang siap dikirim ke LLM (file_context).

Fungsi utama yang dipakai dari luar:
    process_attachments(attachments) -> list[dict]   # structured result (baru)
    extract_attachments_text(attachments) -> (str, list[str])  # legacy string format
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


def _make_result(filename, file_type, status, content=None, error=None, metadata=None):
    """
    Bentuk standar untuk setiap hasil ekstraksi attachment.

    status salah satu dari:
        "extracted"    -> berhasil, content terisi
        "empty"        -> file berhasil didownload tapi isinya kosong
        "unsupported"  -> ekstensi tidak didukung
        "too_large"    -> melebihi MAX_FILE_SIZE_BYTES
        "error"        -> gagal download / gagal parse
    """
    result = {
        "filename": filename,
        "file_type": file_type,
        "extraction_status": status,
    }
    if content is not None:
        result["content"] = content
    if error is not None:
        result["error"] = error
    if metadata is not None:
        result["metadata"] = metadata
    return result


# --- Extractor per tipe file ---

def extract_text_file(attachment):
    """Extract file source-code / text biasa (.py, .md, .json, .csv, dst)."""
    try:
        content = _download(attachment)
    except Exception as e:
        return _make_result(
            attachment.filename, "text", "error",
            error=f"Gagal download: {type(e).__name__}",
        )

    if not content.strip():
        return _make_result(attachment.filename, "text", "empty")

    return _make_result(
        attachment.filename, "text", "extracted",
        content=content,
        metadata={"chars": len(content)},
    )


def extract_notebook(attachment):
    """
    Extract .ipynb menjadi teks ternormalisasi: markdown cells, code cells,
    dan outputnya, urut sesuai posisi cell di notebook.
    """
    try:
        raw = _download(attachment)
    except Exception as e:
        return _make_result(
            attachment.filename, "notebook", "error",
            error=f"Gagal download: {type(e).__name__}",
        )

    try:
        notebook = json.loads(raw)
    except json.JSONDecodeError:
        return _make_result(
            attachment.filename, "notebook", "error",
            error="File .ipynb tidak valid (bukan JSON yang benar)",
        )

    cells = notebook.get("cells", [])
    if not cells:
        return _make_result(attachment.filename, "notebook", "empty")

    parts = [f"=== NOTEBOOK: {attachment.filename} ==="]
    code_cells = 0
    markdown_cells = 0

    for i, cell in enumerate(cells, start=1):
        cell_type = cell.get("cell_type")
        source = "".join(cell.get("source", []))

        if cell_type == "markdown":
            markdown_cells += 1
            parts.append(f"\n[MARKDOWN CELL {i}]\n{source}")

        elif cell_type == "code":
            code_cells += 1
            parts.append(f"\n[CODE CELL {i}]\n{source}")

            for output in cell.get("outputs", []):
                output_text = _extract_notebook_output_text(output)
                if output_text:
                    parts.append(f"\n[OUTPUT CELL {i}]\n{output_text}")

    content = "\n".join(parts)

    if not content.strip():
        return _make_result(attachment.filename, "notebook", "empty")

    return _make_result(
        attachment.filename, "notebook", "extracted",
        content=content,
        metadata={
            "cells": len(cells),
            "code_cells": code_cells,
            "markdown_cells": markdown_cells,
        },
    )


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
    ext = get_extension(attachment.filename).lstrip(".")
    return _make_result(
        attachment.filename, "unknown", "unsupported",
        error=f"Tipe file .{ext} belum didukung",
    )


def extract_file(attachment):
    """Router: pilih extractor berdasarkan ekstensi file."""
    ext = get_extension(attachment.filename)

    if ext in SUPPORTED_TEXT_EXTENSIONS:
        return extract_text_file(attachment)

    if ext in SUPPORTED_NOTEBOOK_EXTENSIONS:
        return extract_notebook(attachment)

    return unsupported_file(attachment)


# --- Entry point baru: structured result ---

def process_attachments(attachments):
    """
    Proses semua attachment Discord dan kembalikan list of structured dict,
    satu entry per attachment, tidak peduli berhasil atau tidak.

    Setiap entry:
        {
            "filename": str,
            "file_type": "text" | "notebook" | "unknown",
            "extraction_status": "extracted" | "empty" | "unsupported" | "too_large" | "error",
            "content": str,       # hanya ada jika status == "extracted"
            "error": str,         # hanya ada jika status gagal
            "metadata": dict,     # hanya ada jika status == "extracted"
        }

    Truncation total karakter TIDAK dilakukan di sini -- itu tanggung jawab
    build_file_context(), supaya urutan prioritas file bisa diatur di sana.
    """
    results = []

    for att in attachments:
        if att.size > MAX_FILE_SIZE_BYTES:
            results.append(_make_result(
                att.filename, get_extension(att.filename).lstrip(".") or "unknown",
                "too_large",
                error=f"Ukuran {att.size} bytes melebihi batas {MAX_FILE_SIZE_BYTES} bytes",
            ))
            continue

        results.append(extract_file(att))

    return results


def build_file_context(results, max_total_chars=MAX_TOTAL_FILE_CHARS):
    """
    Gabungkan hasil extracted dari process_attachments() menjadi satu string
    file_context siap kirim ke LLM, dengan truncation total karakter.

    Return: (combined_text, warnings)
    """
    parts = []
    warnings = []
    total_chars = 0

    for r in results:
        status = r["extraction_status"]
        filename = r["filename"]

        if status == "unsupported":
            warnings.append(f"⚠️ `{filename}` dilewati ({r['error']})")
            continue

        if status == "too_large":
            warnings.append(f"⚠️ `{filename}` dilewati ({r['error']})")
            continue

        if status == "empty":
            warnings.append(f"⚠️ `{filename}` dilewati (file kosong)")
            continue

        if status == "error":
            warnings.append(f"⚠️ `{filename}` gagal diproses: {r['error']}")
            continue

        # status == "extracted"
        content = r["content"]

        if total_chars + len(content) > max_total_chars:
            remaining = max(max_total_chars - total_chars, 0)
            content = content[:remaining] + "\n... (dipotong, terlalu panjang)"
            warnings.append(f"⚠️ `{filename}` dipotong karena total isi file melebihi batas")

        total_chars += len(content)

        if r["file_type"] == "notebook":
            parts.append(content)  # sudah punya header sendiri dari extract_notebook
        else:
            parts.append(f"=== FILE: {filename} ===\n{content}")

        if total_chars >= max_total_chars:
            break

    combined_text = "\n\n".join(parts)
    return combined_text, warnings


# --- Legacy entry point (dipakai mentor_bot.py versi lama) ---

def extract_attachments_text(attachments):
    """
    Kompatibilitas mundur: langsung return (combined_text, warnings) seperti
    versi sebelumnya. Secara internal sekarang memakai process_attachments()
    + build_file_context(), jadi berbagi logic yang sama dengan jalur baru.
    """
    results = process_attachments(attachments)
    return build_file_context(results)