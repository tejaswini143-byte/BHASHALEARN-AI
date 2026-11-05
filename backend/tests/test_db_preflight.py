from types import SimpleNamespace

from sqlalchemy.exc import OperationalError

from backend.scripts import db_preflight


def test_safe_target_omits_credentials_and_query_parameters():
    target = db_preflight._safe_target(
        "postgresql+psycopg://postgres:secret-value@localhost:5432/bhashalearn?sslpassword=other-secret"
    )
    assert target == "localhost:5432/bhashalearn"
    assert "secret" not in target
    assert "postgres" not in target


def test_connection_failure_report_does_not_include_url_or_provider_details(monkeypatch):
    database_url = "postgresql+psycopg://postgres:secret-value@localhost:5432/bhashalearn"
    monkeypatch.setattr(
        db_preflight,
        "Settings",
        lambda: SimpleNamespace(database_url=database_url),
    )
    monkeypatch.setattr(
        db_preflight,
        "create_engine",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            OperationalError("connect", {}, RuntimeError("private provider details"))
        ),
    )

    ok, report = db_preflight.run_preflight()
    rendered = "\n".join(report)
    assert not ok
    assert "OperationalError" in rendered
    assert "secret-value" not in rendered
    assert "private provider details" not in rendered
    assert "postgresql+psycopg://" not in rendered
