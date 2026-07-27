from pathlib import Path


def test_referenced_tables_are_declared_before_fact_universe_memberships() -> None:
    schema = (Path(__file__).parents[1] / "sql" / "postgres_schema.sql").read_text(
        encoding="utf-8"
    )

    derived_facts = schema.index("CREATE TABLE IF NOT EXISTS derived_facts")
    derived_members = schema.index(
        "CREATE TABLE IF NOT EXISTS fact_universe_derived_members"
    )

    assert derived_facts < derived_members
