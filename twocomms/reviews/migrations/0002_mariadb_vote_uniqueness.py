import re

from django.db import migrations, models


def assert_no_review_vote_duplicates(apps, schema_editor):
    ReviewVote = apps.get_model("reviews", "ReviewVote")
    registered_duplicate = (
        ReviewVote.objects.filter(user__isnull=False)
        .values("review_id", "user_id")
        .annotate(row_count=models.Count("pk"))
        .filter(row_count__gt=1)
        .exists()
    )
    if registered_duplicate:
        raise RuntimeError("duplicate ReviewVote registered identity")
    anonymous_duplicate = (
        ReviewVote.objects.filter(user__isnull=True)
        .exclude(anon_key="")
        .values("review_id", "anon_key")
        .annotate(row_count=models.Count("pk"))
        .filter(row_count__gt=1)
        .exists()
    )
    if anonymous_duplicate:
        raise RuntimeError("duplicate ReviewVote anonymous identity")


def _is_mariadb(schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "mysql":
        return False
    if not getattr(connection, "mysql_is_mariadb", False):
        raise RuntimeError("ReviewVote generated identity requires MariaDB")
    return True


def _normalize_expression(value):
    return re.sub(r"[\s`()]+", "", str(value).casefold())


def _assert_column(schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, EXTRA, "
            "GENERATION_EXPRESSION FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME = 'reviews_reviewvote' "
            "AND COLUMN_NAME = 'anon_identity'"
        )
        row = cursor.fetchone()
    if row is None:
        raise RuntimeError("ReviewVote anon_identity column is missing")
    data_type, maximum_length, extra, expression = row
    if (
        str(data_type).casefold() != "varchar"
        or int(maximum_length or 0) != 64
        or str(extra).casefold() != "stored generated"
        or _normalize_expression(expression)
        != "casewhenuser_idisnullthenanon_keyelsenullend"
    ):
        raise RuntimeError("ReviewVote anon_identity column does not match")


def _assert_index(schema_editor, name, columns):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT NON_UNIQUE, "
            "GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX SEPARATOR ',') "
            "FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME = 'reviews_reviewvote' AND INDEX_NAME = %s "
            "GROUP BY NON_UNIQUE",
            [name],
        )
        rows = list(cursor.fetchall())
    if rows != [(0, ",".join(columns))]:
        raise RuntimeError(f"ReviewVote {name} unique index does not match")


def apply_review_vote_schema(apps, schema_editor):
    if not _is_mariadb(schema_editor):
        return
    statements = (
        (
            "ALTER TABLE `reviews_reviewvote` ADD COLUMN IF NOT EXISTS "
            "`anon_identity` varchar(64) GENERATED ALWAYS AS "
            "(CASE WHEN `user_id` IS NULL THEN `anon_key` ELSE NULL END) STORED",
            lambda: _assert_column(schema_editor),
        ),
        (
            "ALTER TABLE `reviews_reviewvote` ADD UNIQUE INDEX IF NOT EXISTS "
            "`rev_vote_unique_user` (`review_id`, `user_id`)",
            lambda: _assert_index(
                schema_editor,
                "rev_vote_unique_user",
                ("review_id", "user_id"),
            ),
        ),
        (
            "ALTER TABLE `reviews_reviewvote` ADD UNIQUE INDEX IF NOT EXISTS "
            "`rev_vote_unique_anon` (`review_id`, `anon_identity`)",
            lambda: _assert_index(
                schema_editor,
                "rev_vote_unique_anon",
                ("review_id", "anon_identity"),
            ),
        ),
    )
    for statement, verify in statements:
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(statement)
        verify()


def reverse_review_vote_schema(apps, schema_editor):
    if not _is_mariadb(schema_editor):
        return
    statements = (
        "ALTER TABLE `reviews_reviewvote` DROP INDEX IF EXISTS "
        "`rev_vote_unique_anon`",
        "ALTER TABLE `reviews_reviewvote` DROP INDEX IF EXISTS "
        "`rev_vote_unique_user`",
        "ALTER TABLE `reviews_reviewvote` DROP COLUMN IF EXISTS `anon_identity`",
    )
    with schema_editor.connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("reviews", "0001_initial")]

    operations = [
        migrations.RunPython(
            assert_no_review_vote_duplicates,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    apply_review_vote_schema,
                    reverse_code=reverse_review_vote_schema,
                ),
            ],
            state_operations=[
                migrations.RemoveConstraint(
                    model_name="reviewvote",
                    name="rev_vote_unique_per_user",
                ),
                migrations.RemoveConstraint(
                    model_name="reviewvote",
                    name="rev_vote_unique_per_anon",
                ),
                migrations.AddField(
                    model_name="reviewvote",
                    name="anon_identity",
                    field=models.GeneratedField(
                        db_persist=True,
                        expression=models.Case(
                            models.When(
                                user__isnull=True,
                                then=models.F("anon_key"),
                            ),
                            default=models.Value(None),
                            output_field=models.CharField(max_length=64),
                        ),
                        output_field=models.CharField(max_length=64),
                    ),
                ),
                migrations.AddConstraint(
                    model_name="reviewvote",
                    constraint=models.UniqueConstraint(
                        fields=("review", "user"),
                        name="rev_vote_unique_user",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="reviewvote",
                    constraint=models.UniqueConstraint(
                        fields=("review", "anon_identity"),
                        name="rev_vote_unique_anon",
                    ),
                ),
            ],
        ),
    ]
