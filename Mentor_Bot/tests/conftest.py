"""
conftest.py
Fixture bersama untuk semua test di folder ini.

FakeAttachment meniru interface discord.Attachment yang dipakai attachment.py
(.filename, .size, .url) tanpa perlu koneksi Discord/network beneran.
_download() di attachment.py dipatch supaya baca file lokal, bukan HTTP request.
"""

import os
import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class FakeAttachment:
    """Meniru discord.Attachment: punya .filename, .size, .url"""

    def __init__(self, filename, size=None):
        self.filename = filename
        self.url = os.path.join(FIXTURES_DIR, filename)
        self.size = size if size is not None else os.path.getsize(self.url)


@pytest.fixture(autouse=True)
def patch_download(monkeypatch):
    """
    Ganti attachment._download supaya baca file lokal dari fixtures/
    alih-alih requests.get() ke Discord CDN. Berlaku otomatis di semua test
    di file ini (autouse=True) supaya tidak ada test yang diam-diam
    melakukan HTTP request beneran.
    """
    import attachment

    def fake_download(att):
        with open(att.url, "rb") as f:
            return f.read().decode("utf-8", errors="replace")

    monkeypatch.setattr(attachment, "_download", fake_download)
