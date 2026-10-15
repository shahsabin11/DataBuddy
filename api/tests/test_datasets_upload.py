"""Dataset upload API: storage path tenancy and cross-user access."""

from __future__ import annotations

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.session import SessionPayload, issue_session_token
from app.config import get_settings
from app.main import create_app
from app.models import Dataset, DatasetVersion
from app.storage import dataset_object_key
from scripts.seed import INST_A, INST_B, PROJECT_A, USERS_A, USERS_B


def _client_as(
    *,
    user_id: uuid.UUID,
    institution_id: uuid.UUID,
    role: str = "student",
    email: str = "student@northfield.edu",
) -> TestClient:
    get_settings.cache_clear()
    app = create_app()
    client = TestClient(app)
    token = issue_session_token(
        SessionPayload(
            user_id=user_id,
            email=email,
            institution_id=institution_id,
            role=role,
            status="active",
        )
    )
    settings = get_settings()
    client.cookies.set(settings.session_cookie_name, token)
    return client


def test_storage_key_contains_institution_user_dataset():
    inst = uuid.uuid4()
    user = uuid.uuid4()
    ds = uuid.uuid4()
    key = dataset_object_key(
        institution_id=inst,
        user_id=user,
        dataset_id=ds,
        filename="v0.csv",
    )
    assert key == f"{inst}/{user}/{ds}/v0.csv"


@patch("app.routers.datasets.put_bytes")
def test_upload_creates_version_zero_and_private_key(
    mock_put, owner_session, migrated_db
):
    client = _client_as(
        user_id=USERS_A[1],
        institution_id=INST_A,
        email="user2@northfield.edu",
    )
    csv_bytes = b"group,score\nA,1\nB,2\n"
    resp = client.post(
        "/api/datasets",
        data={"project_id": str(PROJECT_A)},
        files={"file": ("survey.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "ready"
    assert body["version_number"] == 0
    assert body["storage_key"] is not None
    assert body["storage_key"].startswith(f"{INST_A}/{USERS_A[1]}/")
    assert body["storage_key"].endswith("/v0.csv")
    mock_put.assert_called_once()
    assert mock_put.call_args.kwargs["key"] == body["storage_key"]


@patch("app.routers.datasets.put_bytes")
def test_upload_rejects_formula_via_api(mock_put, migrated_db):
    client = _client_as(user_id=USERS_A[1], institution_id=INST_A)
    bad = b"name,value\nx,=1+1\n"
    resp = client.post(
        "/api/datasets",
        data={"project_id": str(PROJECT_A)},
        files={"file": ("evil.csv", bad, "text/csv")},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "formula_injection"
    mock_put.assert_not_called()


@patch("app.routers.datasets.put_bytes")
def test_upload_rejects_wrong_type_via_api(mock_put, migrated_db):
    client = _client_as(user_id=USERS_A[1], institution_id=INST_A)
    resp = client.post(
        "/api/datasets",
        data={"project_id": str(PROJECT_A)},
        files={"file": ("x.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 32, "image/png")},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "invalid_type"
    mock_put.assert_not_called()


@patch("app.routers.datasets.put_bytes")
def test_upload_rejects_oversize_via_api(mock_put, migrated_db, monkeypatch):
    client = _client_as(user_id=USERS_A[1], institution_id=INST_A)
    # Patch after client setup — _client_as clears the settings cache.
    monkeypatch.setattr(get_settings(), "max_upload_bytes", 64)
    resp = client.post(
        "/api/datasets",
        data={"project_id": str(PROJECT_A)},
        files={"file": ("big.csv", b"a,b\n" + b"1,2\n" * 40, "text/csv")},
    )
    assert resp.status_code == 413
    assert resp.json()["detail"]["code"] == "file_too_large"
    mock_put.assert_not_called()


@patch("app.routers.datasets.presigned_get_url", return_value="https://signed.example/obj")
def test_cross_user_cannot_get_download_url_for_other_institution(
    _mock_url, student_a, owner_session
):
    """Student A (via API session) cannot sign a URL for institution B's dataset."""
    # Seed dataset B is only visible under institution B RLS.
    client = _client_as(
        user_id=USERS_A[1],
        institution_id=INST_A,
        email="user2@northfield.edu",
    )
    from scripts.seed import DATASET_B

    resp = client.get(f"/api/datasets/{DATASET_B}/download-url")
    assert resp.status_code == 404


def test_cross_user_rls_hides_foreign_storage_rows(student_a):
    """Even knowing the path pattern, RLS returns no foreign dataset_versions."""
    session, ctx = student_a
    # Guess a path under institution B / user B.
    guessed = dataset_object_key(
        institution_id=INST_B,
        user_id=USERS_B[1],
        dataset_id=uuid.uuid4(),
        filename="v0.csv",
    )
    rows = session.scalars(
        select(DatasetVersion).where(DatasetVersion.storage_key == guessed)
    ).all()
    assert rows == []

    # Real seeded B version key is also invisible to student A.
    from scripts.seed import VERSION_B

    foreign = session.get(DatasetVersion, VERSION_B)
    assert foreign is None


@patch("app.routers.datasets.put_bytes")
@patch("app.routers.datasets.delete_keys")
def test_delete_removes_versions(mock_delete_keys, mock_put, migrated_db, owner_session):
    client = _client_as(user_id=USERS_A[1], institution_id=INST_A)
    csv_bytes = b"a,b\n1,2\n"
    created = client.post(
        "/api/datasets",
        data={"project_id": str(PROJECT_A)},
        files={"file": ("t.csv", csv_bytes, "text/csv")},
    )
    assert created.status_code == 201
    dataset_id = created.json()["id"]
    key = created.json()["storage_key"]

    deleted = client.delete(f"/api/datasets/{dataset_id}")
    assert deleted.status_code == 200
    mock_delete_keys.assert_called()
    assert key in mock_delete_keys.call_args.args[0]

    # Owner session (bypass) confirms row gone after commit from TestClient.
    owner_session.expire_all()
    assert owner_session.get(Dataset, uuid.UUID(dataset_id)) is None
