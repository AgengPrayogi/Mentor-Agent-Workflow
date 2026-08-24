"""
test_attachment.py

Menguji skenario yang disepakati di Checkpoint 2:
    ✓ .py berhasil diekstrak
    ✓ .txt berhasil diekstrak
    ✓ .ipynb berhasil diekstrak (markdown + code + output)
    ✓ unsupported file ditolak
    ✓ file kosong ditangani
    ✓ notebook invalid ditangani
    ✓ notebook kosong (tanpa cells) ditangani
    ✓ file terlalu besar ditangani
    ✓ build_file_context() menggabungkan hasil dengan benar
    ✓ build_file_context() melakukan truncation saat total karakter kelebihan
"""

import attachment
from conftest import FakeAttachment


# --- Ekstraksi file yang didukung ---

def test_py_file_extracted_successfully():
    att = FakeAttachment("sample.py")
    result = attachment.extract_file(att)

    assert result["extraction_status"] == "extracted"
    assert result["file_type"] == "text"
    assert "def greet" in result["content"]
    assert result["metadata"]["chars"] > 0


def test_txt_file_extracted_successfully():
    att = FakeAttachment("sample.txt")
    result = attachment.extract_file(att)

    assert result["extraction_status"] == "extracted"
    assert result["file_type"] == "text"
    assert "file teks sederhana" in result["content"]


def test_notebook_extracted_successfully():
    att = FakeAttachment("sample.ipynb")
    result = attachment.extract_file(att)

    assert result["extraction_status"] == "extracted"
    assert result["file_type"] == "notebook"
    assert "[MARKDOWN CELL 1]" in result["content"]
    assert "[CODE CELL 2]" in result["content"]
    assert "[OUTPUT CELL 2]" in result["content"]
    assert "Analisis Sederhana" in result["content"]
    assert "print(x)" in result["content"]
    assert result["metadata"]["cells"] == 2
    assert result["metadata"]["code_cells"] == 1
    assert result["metadata"]["markdown_cells"] == 1


# --- File tidak didukung / bermasalah ---

def test_unsupported_extension_rejected():
    att = FakeAttachment("sample.py")
    att.filename = "sample.exe"  # ganti nama, konten tidak dibaca karena unsupported
    result = attachment.extract_file(att)

    assert result["extraction_status"] == "unsupported"
    assert "belum didukung" in result["error"]


def test_empty_text_file_handled():
    att = FakeAttachment("empty.txt")
    result = attachment.extract_file(att)

    assert result["extraction_status"] == "empty"
    assert "content" not in result


def test_invalid_notebook_json_handled():
    att = FakeAttachment("invalid.ipynb")
    result = attachment.extract_file(att)

    assert result["extraction_status"] == "error"
    assert "tidak valid" in result["error"]


def test_empty_notebook_handled():
    att = FakeAttachment("empty.ipynb")
    result = attachment.extract_file(att)

    assert result["extraction_status"] == "empty"


def test_file_too_large_rejected_by_process_attachments():
    # size di-override manual supaya melebihi MAX_FILE_SIZE_BYTES,
    # tanpa perlu benar-benar membuat file 500KB+ di fixtures/
    att = FakeAttachment("sample.py", size=attachment.MAX_FILE_SIZE_BYTES + 1)
    results = attachment.process_attachments([att])

    assert len(results) == 1
    assert results[0]["extraction_status"] == "too_large"


# --- process_attachments() untuk banyak file sekaligus ---

def test_process_attachments_returns_one_result_per_file():
    atts = [FakeAttachment("sample.py"), FakeAttachment("sample.ipynb")]
    results = attachment.process_attachments(atts)

    assert len(results) == 2
    assert results[0]["filename"] == "sample.py"
    assert results[1]["filename"] == "sample.ipynb"
    assert all(r["extraction_status"] == "extracted" for r in results)


def test_process_attachments_mixed_success_and_failure():
    atts = [
        FakeAttachment("sample.py"),        # sukses
        FakeAttachment("empty.txt"),        # empty
        FakeAttachment("invalid.ipynb"),    # error
    ]
    att_exe = FakeAttachment("sample.py")
    att_exe.filename = "virus.exe"          # unsupported
    atts.append(att_exe)

    results = attachment.process_attachments(atts)

    statuses = [r["extraction_status"] for r in results]
    assert statuses == ["extracted", "empty", "error", "unsupported"]


# --- build_file_context(): gabungkan + truncate ---

def test_build_file_context_combines_extracted_files():
    atts = [FakeAttachment("sample.py"), FakeAttachment("sample.txt")]
    results = attachment.process_attachments(atts)
    combined, warnings = attachment.build_file_context(results)

    assert "=== FILE: sample.py ===" in combined
    assert "=== FILE: sample.txt ===" in combined
    assert warnings == []


def test_build_file_context_generates_warnings_for_skipped_files():
    att_exe = FakeAttachment("sample.py")
    att_exe.filename = "virus.exe"
    results = attachment.process_attachments([att_exe, FakeAttachment("empty.txt")])
    combined, warnings = attachment.build_file_context(results)

    assert len(warnings) == 2
    assert any("virus.exe" in w for w in warnings)
    assert any("empty.txt" in w for w in warnings)


def test_build_file_context_truncates_when_over_limit():
    att = FakeAttachment("sample.py")
    results = attachment.process_attachments([att])

    # paksa limit sangat kecil supaya truncation pasti terjadi
    combined, warnings = attachment.build_file_context(results, max_total_chars=10)

    assert "dipotong" in combined
    assert any("dipotong" in w for w in warnings)


# --- Backward compatibility: extract_attachments_text() ---

def test_legacy_extract_attachments_text_still_works():
    atts = [FakeAttachment("sample.py")]
    combined, warnings = attachment.extract_attachments_text(atts)

    assert "=== FILE: sample.py ===" in combined
    assert "def greet" in combined
    assert warnings == []
