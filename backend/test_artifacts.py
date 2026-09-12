from pathlib import Path
import pytest
from backend.api.artifacts import _safe_path
from fastapi import HTTPException
def test_safe_path_rejects_traversal(tmp_path):
    with pytest.raises(HTTPException) as exc: _safe_path(tmp_path, str(tmp_path/'..'/'secret'))
    assert exc.value.status_code==403
def test_safe_path_accepts_child(tmp_path):
    child=tmp_path/'a.json'; child.write_text('{}')
    assert _safe_path(tmp_path, str(child))==child.resolve()
