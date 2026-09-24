# demo/api/tests/conftest.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


@pytest.fixture(autouse=True)
def _no_real_upload_cleanup(monkeypatch):
    """The API prunes expired uploads from the on-disk ChromaDB; keep tests
    from opening (and rewriting) the committed demo database."""
    import main
    monkeypatch.setattr(main, "delete_expired_uploads", lambda max_age_seconds: [])
