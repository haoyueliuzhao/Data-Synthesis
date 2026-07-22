from __future__ import annotations

from finraw.storage import sha256_bytes
from finraw.validation import validate_raw_objects


class FakeDB:
    def __init__(self, rows):
        self.rows = rows
        self.updates = []

    def fetchall(self, *_args, **_kwargs):
        return self.rows

    def execute(self, sql, params):
        self.updates.append((sql, params))


def _row(path, *, response_status=200, validation_status="unchecked"):
    content = path.read_bytes()
    return {
        "raw_object_id": "rawobj_test",
        "storage_uri": str(path),
        "content_sha256": sha256_bytes(content),
        "response_status": response_status,
        "validation_status": validation_status,
        "notes": None,
    }


def test_checksum_validation_does_not_promote_http_error(tmp_path):
    path = tmp_path / "error.json"
    path.write_bytes(b'{"message":"bad request"}')
    db = FakeDB([_row(path, response_status=400, validation_status="failed")])

    passed, failed = validate_raw_objects(db)

    assert (passed, failed) == (0, 1)
    assert db.updates[-1][1][0] == "failed"
    assert "HTTP status 400" in db.updates[-1][1][1]


def test_checksum_validation_preserves_warning_status(tmp_path):
    path = tmp_path / "document.pdf"
    path.write_bytes(b"valid bytes")
    db = FakeDB([_row(path, validation_status="warning")])

    passed, failed = validate_raw_objects(db)

    assert (passed, failed) == (1, 0)
    assert db.updates == []


def test_checksum_validation_preserves_retired_http_error(tmp_path):
    path = tmp_path / "retired.json"
    path.write_bytes(b'{"message":"retired target"}')
    db = FakeDB([_row(path, response_status=400, validation_status="retired")])

    passed, failed = validate_raw_objects(db)

    assert (passed, failed) == (1, 0)
    assert db.updates == []
