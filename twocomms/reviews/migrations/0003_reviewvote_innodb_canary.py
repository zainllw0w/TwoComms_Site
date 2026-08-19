from __future__ import annotations

import re
import os
import stat
from pathlib import Path

from django.conf import settings
from django.db import migrations


TABLE = "reviews_reviewvote"
EXPECTED_FORWARD_ROWS = 0
EXPECTED_INDEXES = (
    ("PRIMARY", 0, "BTREE", "id"),
    ("reviews_reviewvote_anon_key_9578b8b8", 1, "BTREE", "anon_key"),
    ("reviews_reviewvote_review_id_0cdb7cab", 1, "BTREE", "review_id"),
    ("reviews_reviewvote_user_id_595149a6", 1, "BTREE", "user_id"),
    ("rev_vote_unique_anon", 0, "BTREE", "review_id,anon_identity"),
    ("rev_vote_unique_user", 0, "BTREE", "review_id,user_id"),
)
EXPECTED_INDEX_LAYOUT = tuple(
    sorted((non_unique, index_type, columns) for _, non_unique, index_type, columns in EXPECTED_INDEXES)
)
FRESH_INSTALL_FOREIGN_KEYS = frozenset(
    {
        (TABLE, "review_id", "reviews_review", "id"),
        (TABLE, "user_id", "auth_user", "id"),
    }
)
MARKER_BYTES = b"review-write-freeze-v1\n"
EXPECTED_ANON_IDENTITY_EXPRESSION = "casewhenuser_idisnullthenanon_keyelsenullend"


def review_write_freeze_marker_path() -> Path:
    configured = getattr(settings, "REVIEW_WRITE_FREEZE_MARKER", None)
    if configured is not None:
        return Path(configured)
    return Path(settings.BASE_DIR) / "tmp" / "review_writes.frozen"


def review_write_freeze_verified() -> bool:
    """Keep migration history independent of the current reviews app code."""

    path = review_write_freeze_marker_path()
    if not path.is_absolute():
        return False
    try:
        path_stat = os.lstat(path)
    except OSError:
        return False
    if (
        stat.S_ISLNK(path_stat.st_mode)
        or not stat.S_ISREG(path_stat.st_mode)
        or stat.S_IMODE(path_stat.st_mode) != 0o600
        or path_stat.st_uid != os.geteuid()
    ):
        return False
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
        try:
            opened_stat = os.fstat(descriptor)
            if (
                not stat.S_ISREG(opened_stat.st_mode)
                or stat.S_IMODE(opened_stat.st_mode) != 0o600
                or opened_stat.st_uid != os.geteuid()
                or (opened_stat.st_dev, opened_stat.st_ino)
                != (path_stat.st_dev, path_stat.st_ino)
            ):
                return False
            return os.read(descriptor, len(MARKER_BYTES) + 1) == MARKER_BYTES
        finally:
            os.close(descriptor)
    except OSError:
        return False


def _validated_table(table: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", table):
        raise RuntimeError("ReviewVote canary table identity is invalid")
    return table


def _table_engine(schema_editor, table: str) -> str:
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s "
            "AND TABLE_TYPE='BASE TABLE'",
            [table],
        )
        row = cursor.fetchone()
    if row is None or not row[0]:
        raise RuntimeError("ReviewVote canary table is missing")
    return str(row[0])


def _index_signature(schema_editor, table: str) -> tuple[tuple[str, int, str, str], ...]:
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT INDEX_NAME, NON_UNIQUE, INDEX_TYPE, "
            "GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX SEPARATOR ',') "
            "FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s "
            "GROUP BY INDEX_NAME, NON_UNIQUE, INDEX_TYPE ORDER BY INDEX_NAME",
            [table],
        )
        rows = cursor.fetchall()
    return tuple(
        sorted(
            (str(name), int(non_unique), str(index_type).upper(), str(columns))
            for name, non_unique, index_type, columns in rows
        )
    )


def _foreign_key_signature(schema_editor, table: str) -> frozenset[tuple[str, str, str, str]]:
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, "
            "REFERENCED_COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE CONSTRAINT_SCHEMA=DATABASE() "
            "AND REFERENCED_TABLE_NAME IS NOT NULL "
            "AND (TABLE_NAME=%s OR REFERENCED_TABLE_NAME=%s)",
            [table, table],
        )
        rows = cursor.fetchall()
    return frozenset(tuple(str(value) for value in row) for row in rows)


def _generated_column_signature(schema_editor, table: str) -> tuple[str, str]:
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT EXTRA, GENERATION_EXPRESSION FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s "
            "AND COLUMN_NAME='anon_identity'",
            [table],
        )
        row = cursor.fetchone()
    if row is None:
        raise RuntimeError("ReviewVote canary generated identity is missing")
    return (
        str(row[0]).casefold(),
        re.sub(r"[\s`()]+", "", str(row[1]).casefold()),
    )


def _scalar_count(schema_editor, statement: str, params: list[str]) -> int:
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(statement, params)
        row = cursor.fetchone()
    if row is None:
        raise RuntimeError("ReviewVote canary count proof is missing")
    return int(row[0])


def _row_count(schema_editor, table: str) -> int:
    quote = schema_editor.quote_name
    return _scalar_count(
        schema_editor,
        f"SELECT COUNT(*) FROM {quote(table)}",
        [],
    )


def _assert_schema_facts(
    schema_editor,
    table: str,
    *,
    expected_engine: str,
    allowed_foreign_keys: frozenset[frozenset[tuple[str, str, str, str]]],
) -> None:
    engine = _table_engine(schema_editor, table)
    if engine.casefold() != expected_engine.casefold():
        raise RuntimeError(
            f"ReviewVote canary engine mismatch: expected {expected_engine}"
        )
    index_signature = _index_signature(schema_editor, table)
    index_layout = tuple(
        sorted(
            (non_unique, index_type, columns)
            for _name, non_unique, index_type, columns in index_signature
        )
    )
    if len(index_signature) != len(EXPECTED_INDEXES) or index_layout != EXPECTED_INDEX_LAYOUT:
        raise RuntimeError("ReviewVote canary index contract mismatch")
    generated_extra, generated_expression = _generated_column_signature(
        schema_editor, table
    )
    if (
        generated_extra != "stored generated"
        or generated_expression != EXPECTED_ANON_IDENTITY_EXPRESSION
    ):
        raise RuntimeError("ReviewVote canary generated identity contract mismatch")
    triggers = _scalar_count(
        schema_editor,
        "SELECT COUNT(*) FROM information_schema.TRIGGERS "
        "WHERE TRIGGER_SCHEMA=DATABASE() AND EVENT_OBJECT_TABLE=%s",
        [table],
    )
    if triggers:
        raise RuntimeError("ReviewVote canary trigger contract mismatch")
    fulltext = _scalar_count(
        schema_editor,
        "SELECT COUNT(*) FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s "
        "AND INDEX_TYPE = 'FULLTEXT'",
        [table],
    )
    if fulltext:
        raise RuntimeError("ReviewVote canary FULLTEXT contract mismatch")
    foreign_keys = _foreign_key_signature(schema_editor, table)
    if foreign_keys not in allowed_foreign_keys:
        raise RuntimeError("ReviewVote canary foreign key contract mismatch")

    quote = schema_editor.quote_name
    duplicate_queries = (
        f"SELECT COUNT(*) FROM (SELECT 1 FROM {quote(table)} "
        "WHERE `user_id` IS NOT NULL GROUP BY `review_id`, `user_id` "
        "HAVING COUNT(*) > 1) AS duplicate_review_votes",
        f"SELECT COUNT(*) FROM (SELECT 1 FROM {quote(table)} "
        "WHERE `user_id` IS NULL AND `anon_key` <> '' "
        "GROUP BY `review_id`, `anon_key` HAVING COUNT(*) > 1) "
        "AS duplicate_review_votes",
    )
    if any(_scalar_count(schema_editor, statement, []) for statement in duplicate_queries):
        raise RuntimeError("ReviewVote canary duplicate contract mismatch")


def _transition_engine(
    schema_editor,
    table: str,
    *,
    source: str,
    target: str,
    require_empty: bool,
) -> None:
    table = _validated_table(table)
    if not review_write_freeze_verified():
        raise RuntimeError("ReviewVote write-freeze marker is not verified")
    no_foreign_keys = frozenset({frozenset()})
    _assert_schema_facts(
        schema_editor,
        table,
        expected_engine=source,
        allowed_foreign_keys=no_foreign_keys,
    )
    rows_before = _row_count(schema_editor, table)
    if require_empty and rows_before != EXPECTED_FORWARD_ROWS:
        raise RuntimeError("ReviewVote canary row count contract mismatch")
    indexes_before = _index_signature(schema_editor, table)

    schema_editor.execute(
        f"ALTER TABLE {schema_editor.quote_name(table)} ENGINE={target}"
    )

    _assert_schema_facts(
        schema_editor,
        table,
        expected_engine=target,
        allowed_foreign_keys=no_foreign_keys,
    )
    if _row_count(schema_editor, table) != rows_before:
        raise RuntimeError("ReviewVote canary row count changed during engine transition")
    if _index_signature(schema_editor, table) != indexes_before:
        raise RuntimeError("ReviewVote canary indexes changed during engine transition")


def convert_reviewvote_to_innodb(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    engine = _table_engine(schema_editor, TABLE)
    if engine.casefold() == "innodb":
        _assert_schema_facts(
            schema_editor,
            TABLE,
            expected_engine="InnoDB",
            allowed_foreign_keys=frozenset(
                {frozenset(), FRESH_INSTALL_FOREIGN_KEYS}
            ),
        )
        return
    if engine.casefold() != "myisam":
        raise RuntimeError("ReviewVote canary engine is neither MyISAM nor InnoDB")
    _transition_engine(
        schema_editor,
        TABLE,
        source="MyISAM",
        target="InnoDB",
        require_empty=True,
    )


def restore_reviewvote_to_myisam(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    engine = _table_engine(schema_editor, TABLE)
    if engine.casefold() == "myisam":
        _assert_schema_facts(
            schema_editor,
            TABLE,
            expected_engine="MyISAM",
            allowed_foreign_keys=frozenset({frozenset()}),
        )
        return
    if engine.casefold() != "innodb":
        raise RuntimeError("ReviewVote canary engine is neither MyISAM nor InnoDB")
    foreign_keys = _foreign_key_signature(schema_editor, TABLE)
    if foreign_keys == FRESH_INSTALL_FOREIGN_KEYS:
        _assert_schema_facts(
            schema_editor,
            TABLE,
            expected_engine="InnoDB",
            allowed_foreign_keys=frozenset({FRESH_INSTALL_FOREIGN_KEYS}),
        )
        return
    _transition_engine(
        schema_editor,
        TABLE,
        source="InnoDB",
        target="MyISAM",
        require_empty=False,
    )


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("reviews", "0002_mariadb_vote_uniqueness")]
    operations = [
        migrations.RunPython(
            convert_reviewvote_to_innodb,
            reverse_code=restore_reviewvote_to_myisam,
        )
    ]
