from __future__ import annotations

import json
from typing import Any, Iterable

from finraw.db.client import DBProtocol


def _commit_if_needed(db: DBProtocol) -> None:
    commit_if_needed = getattr(db, "_commit_if_needed", None)
    if callable(commit_if_needed):
        commit_if_needed()
        return
    db.conn.commit()  # type: ignore[attr-defined]


def insert_rows(
    db: DBProtocol,
    table: str,
    rows: list[dict[str, Any]],
    columns: list[str],
    json_columns: set[str] | None = None,
) -> None:
    if not rows:
        return
    json_columns = json_columns or set()
    postgres = db.__class__.__name__ == "PostgresMetadataDB"
    if postgres:
        from psycopg.types.json import Jsonb

        values = [
            [
                Jsonb(_json_ready(row.get(column)))
                if column in json_columns
                else row.get(column)
                for column in columns
            ]
            for row in rows
        ]
        updates = ", ".join(
            f"{column}=EXCLUDED.{column}" for column in columns if column != columns[0]
        )
        sql = (
            f"INSERT INTO {table} ({','.join(columns)}) "
            f"VALUES ({','.join(['%s'] * len(columns))}) "
            f"ON CONFLICT ({columns[0]}) DO UPDATE SET {updates}"
        )
        with db.conn.cursor() as cursor:  # type: ignore[attr-defined]
            cursor.executemany(sql, values)
        _commit_if_needed(db)
        return

    values = [
        [
            json.dumps(row.get(column), ensure_ascii=False, sort_keys=True, default=str)
            if column in json_columns
            else row.get(column)
            for column in columns
        ]
        for row in rows
    ]
    sql = (
        f"INSERT OR REPLACE INTO {table} ({','.join(columns)}) "
        f"VALUES ({','.join('?' for _ in columns)})"
    )
    db.conn.executemany(sql, values)  # type: ignore[attr-defined]
    _commit_if_needed(db)


def execute_many(db: DBProtocol, sql: str, rows: list[tuple[Any, ...]]) -> None:
    if not rows:
        return
    if db.__class__.__name__ == "PostgresMetadataDB":
        with db.conn.cursor() as cursor:  # type: ignore[attr-defined]
            cursor.executemany(db._sql(sql), rows)  # type: ignore[attr-defined]
        _commit_if_needed(db)
    else:
        db.conn.executemany(sql, rows)  # type: ignore[attr-defined]
        _commit_if_needed(db)


def chunks(values: list[Any], size: int = 1000) -> Iterable[list[Any]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _json_ready(value: Any) -> Any:
    return json.loads(
        json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    )


def json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default
