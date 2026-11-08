"""Run the INT-11 migration against a fresh disposable SQLite database only."""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_mission_completion_migration_up_and_down_on_disposable_database(tmp_path):
    migration_file = Path(__file__).parents[1] / "alembic" / "versions" / "0010_mission_completions.py"
    spec = importlib.util.spec_from_file_location("mission_migration", migration_file)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = create_engine(f"sqlite:///{(tmp_path / 'migration-disposable.db').as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE students (id VARCHAR(36) PRIMARY KEY)"))
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()
        inspector = inspect(connection)
        assert "mission_completions" in inspector.get_table_names()
        assert {item["name"] for item in inspector.get_unique_constraints("mission_completions")} == {
            "uq_mission_completion_student_mission",
        }
        assert {item["name"] for item in inspector.get_check_constraints("mission_completions")} == {
            "ck_mission_completion_xp_nonnegative",
        }
        with Operations.context(context):
            migration.downgrade()
        assert "mission_completions" not in inspect(connection).get_table_names()
    engine.dispose()
