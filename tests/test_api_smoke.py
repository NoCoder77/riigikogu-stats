"""API smoke tests using TestClient with mocked DB."""
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from riigikogu_stats.api.app import app


def _mock_conn():
    conn = MagicMock()
    cur = MagicMock()
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)
    cur.fetchall.return_value = []
    cur.fetchone.return_value = None
    conn.cursor.return_value = cur
    return conn


@patch("riigikogu_stats.api.app.connect_db")
@patch("riigikogu_stats.api.app.load_settings")
def test_health_ok(mock_load_settings, mock_connect_db):
    mock_load_settings.return_value = MagicMock(database_url="postgresql://fake")
    mock_connect_db.return_value.__enter__ = MagicMock(return_value=_mock_conn())
    mock_connect_db.return_value.__exit__ = MagicMock(return_value=False)
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@patch("riigikogu_stats.api.app.connect_db")
@patch("riigikogu_stats.api.app.load_settings")
def test_health_unhealthy(mock_load_settings, mock_connect_db):
    mock_load_settings.return_value = MagicMock(database_url="postgresql://fake")
    mock_connect_db.side_effect = Exception("connection refused")
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unhealthy"
    assert "error" in data


@patch("riigikogu_stats.api.app.connect_db")
@patch("riigikogu_stats.api.app.load_settings")
def test_list_imports(mock_load_settings, mock_connect_db):
    mock_load_settings.return_value = MagicMock(database_url="postgresql://fake")
    conn = _mock_conn()
    conn.cursor.return_value.__enter__.return_value.fetchall.return_value = []
    mock_connect_db.return_value.__enter__ = MagicMock(return_value=conn)
    mock_connect_db.return_value.__exit__ = MagicMock(return_value=False)
    client = TestClient(app)
    resp = client.get("/imports?limit=10&offset=0")
    assert resp.status_code == 200
    assert resp.json() == []


@patch("riigikogu_stats.api.app.connect_db")
@patch("riigikogu_stats.api.app.load_settings")
def test_list_sessions(mock_load_settings, mock_connect_db):
    mock_load_settings.return_value = MagicMock(database_url="postgresql://fake")
    conn = _mock_conn()
    mock_connect_db.return_value.__enter__ = MagicMock(return_value=conn)
    mock_connect_db.return_value.__exit__ = MagicMock(return_value=False)
    client = TestClient(app)
    resp = client.get("/sessions?limit=10&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data and "total" in data
    assert data["items"] == []
    assert data["total"] == 0


@patch("riigikogu_stats.api.app.connect_db")
@patch("riigikogu_stats.api.app.load_settings")
def test_list_votes(mock_load_settings, mock_connect_db):
    mock_load_settings.return_value = MagicMock(database_url="postgresql://fake")
    conn = _mock_conn()
    mock_connect_db.return_value.__enter__ = MagicMock(return_value=conn)
    mock_connect_db.return_value.__exit__ = MagicMock(return_value=False)
    client = TestClient(app)
    resp = client.get("/votes?limit=10&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data and "total" in data
    assert data["items"] == []
    assert data["total"] == 0


@patch("riigikogu_stats.api.app.run_etl")
@patch("riigikogu_stats.api.app.load_settings")
@patch("riigikogu_stats.api.app.connect_db")
def test_create_import_queued(mock_connect_db, mock_load_settings, mock_run_etl):
    mock_load_settings.return_value = MagicMock(database_url="sqlite:///:memory:")
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.rowcount = 0
    mock_conn.cursor.return_value = mock_cur
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_conn
    mock_cm.__exit__.return_value = False
    mock_connect_db.return_value = mock_cm
    client = TestClient(app)
    resp = client.post(
        "/imports",
        json={
            "startDate": "2013-01-01",
            "endDate": "2013-01-07",
            "stepDays": 7,
            "onlyVotings": False,
            "onlySittings": False,
            "initDb": False,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert "run_id" in data
    # TestClient runs background tasks synchronously
    mock_run_etl.assert_called_once()
    call_kw = mock_run_etl.call_args[1]
    assert call_kw["run_id"] == data["run_id"]
    assert call_kw["start_date"].isoformat() == "2013-01-01"
    assert call_kw["end_date"].isoformat() == "2013-01-07"
    assert call_kw["step_days"] == 7
    assert call_kw["init_db"] is False
