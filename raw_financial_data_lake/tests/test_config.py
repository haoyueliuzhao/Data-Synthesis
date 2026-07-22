from __future__ import annotations

import json

from finraw.config import load_config


def test_profile_extends_parent_relative_to_child(tmp_path):
    parent = tmp_path / "parent.json"
    child = tmp_path / "child.json"
    parent.write_text(
        json.dumps({"test_inheritance": {"parent": 1, "shared": "parent"}}),
        encoding="utf-8",
    )
    child.write_text(
        json.dumps(
            {
                "extends": "parent.json",
                "test_inheritance": {"child": 2, "shared": "child"},
            }
        ),
        encoding="utf-8",
    )

    config = load_config(str(child))

    assert config["test_inheritance"] == {
        "parent": 1,
        "child": 2,
        "shared": "child",
    }
