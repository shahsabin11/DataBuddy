"""Dataset upload, signed download URLs, and delete."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import AuthUser, get_app_db_with_rls, require_member
from app.config import get_settings
from app.models import (
    AgentStep,
    AnalysisSession,
    Artifact,
    Dataset,
    DatasetVersion,
    InstitutionBudget,
    Project,
    ProjectMember,
)
from app.models.enums import DatasetStatus, ProjectMemberSource
from app.storage import (
    dataset_object_key,
    delete_keys,
    presigned_get_url,
    put_bytes,
)
from app.upload_validation import UploadValidationError, validate_upload

router = APIRouter(
    prefix="/datasets",
    tags=["datasets"],
    dependencies=[Depends(require_member)],
)


class DatasetResponse(BaseModel):
    id: str
    project_id: str
    name: str
    original_filename: str
    status: str
    current_version_id: str | None
    version_number: int | None = None
    storage_key: str | None = None
    byte_size: int | None = None
    row_count: int | None = None
    column_count: int | None = None


class DownloadUrlResponse(BaseModel):
    url: str
    expires_in: int
    storage_key: str


class DeleteResponse(BaseModel):
    status: str = "deleted"
    id: str


def _ensure_project(
    db: Session,
    user: AuthUser,
    project_id: uuid.UUID | None,
) -> Project:
    assert user.institution_id is not None
    if project_id is not None:
        project = db.get(Project, project_id)
        if project is None or project.institution_id != user.institution_id:
            raise HTTPException(404, detail="Project not found.")
        member = db.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id == user.user_id,
            )
        )
        if member is None and user.role not in {
            "institution_admin",
            "platform_admin",
        }:
            raise HTTPException(403, detail="Not a member of this project.")
        if member is None:
            # Institution admins may join for break-glass-style upload in v1.
            db.add(
                ProjectMember(
                    institution_id=user.institution_id,
                    project_id=project.id,
                    user_id=user.user_id,
                    source=ProjectMemberSource.BREAK_GLASS.value,
                )
            )
            db.flush()
        return project

    # Prefer an existing project the user already belongs to (e.g. teacher invite).
    existing = db.scalar(
        select(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(
            Project.institution_id == user.institution_id,
            ProjectMember.user_id == user.user_id,
        )
        .order_by(Project.created_at.desc())
    )
    if existing is not None:
        return existing

    project = Project(
        institution_id=user.institution_id,
        owner_user_id=user.user_id,
        title="Untitled project",
    )
    db.add(project)
    db.flush()
    db.add(
        ProjectMember(
            institution_id=user.institution_id,
            project_id=project.id,
            user_id=user.user_id,
            source=ProjectMemberSource.OWNER.value,
        )
    )
    db.flush()
    return project


def _check_region_allows_upload(db: Session, institution_id: uuid.UUID) -> None:
    budget = db.get(InstitutionBudget, institution_id)
    if budget is not None and not budget.allow_data_to_leave_region:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "region_pin_unsupported",
                "message": (
                    "This institution requires data to stay in-region, "
                    "which the current deployment cannot guarantee."
                ),
            },
        )


def _dataset_response(ds: Dataset, version: DatasetVersion | None) -> DatasetResponse:
    return DatasetResponse(
        id=str(ds.id),
        project_id=str(ds.project_id),
        name=ds.name,
        original_filename=ds.original_filename,
        status=ds.status,
        current_version_id=str(ds.current_version_id) if ds.current_version_id else None,
        version_number=version.version_number if version else None,
        storage_key=version.storage_key if version else None,
        byte_size=version.byte_size if version else None,
        row_count=version.row_count if version else None,
        column_count=version.column_count if version else None,
    )


@router.get("", response_model=list[DatasetResponse])
def list_datasets(
    user: Annotated[AuthUser, Depends(require_member)],
    db: Annotated[Session, Depends(get_app_db_with_rls)],
) -> list[DatasetResponse]:
    rows = db.scalars(
        select(Dataset).order_by(Dataset.created_at.desc())
    ).all()
    out: list[DatasetResponse] = []
    for ds in rows:
        ver = db.get(DatasetVersion, ds.current_version_id) if ds.current_version_id else None
        out.append(_dataset_response(ds, ver))
    return out


@router.post("", response_model=DatasetResponse, status_code=201)
async def upload_dataset(
    user: Annotated[AuthUser, Depends(require_member)],
    db: Annotated[Session, Depends(get_app_db_with_rls)],
    file: Annotated[UploadFile, File()],
    project_id: Annotated[str | None, Form()] = None,
    name: Annotated[str | None, Form()] = None,
) -> DatasetResponse:
    assert user.institution_id is not None
    settings = get_settings()
    _check_region_allows_upload(db, user.institution_id)

    parsed_project: uuid.UUID | None = None
    if project_id:
        try:
            parsed_project = uuid.UUID(project_id)
        except ValueError as exc:
            raise HTTPException(400, detail="Invalid project_id.") from exc

    project = _ensure_project(db, user, parsed_project)

    # Stream with a hard size cap (do not trust Content-Length alone).
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > settings.max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={
                    "code": "file_too_large",
                    "message": (
                        f"File exceeds the "
                        f"{settings.max_upload_bytes // (1024 * 1024)} MB upload limit."
                    ),
                },
            )
        chunks.append(chunk)
    data = b"".join(chunks)

    original = file.filename or "upload.csv"
    try:
        validated = validate_upload(
            data, filename=original, max_bytes=settings.max_upload_bytes
        )
    except UploadValidationError as exc:
        status_code = (
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            if exc.code == "file_too_large"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(
            status_code=status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    display_name = (name or original).strip()[:300] or "Untitled dataset"
    safe_filename = original.rsplit("/", 1)[-1][:500]
    if not safe_filename.lower().endswith(validated.extension):
        # Normalize extension to the detected type.
        stem = safe_filename.rsplit(".", 1)[0] if "." in safe_filename else safe_filename
        safe_filename = f"{stem}{validated.extension}"

    dataset_id = uuid.uuid4()
    storage_key = dataset_object_key(
        institution_id=user.institution_id,
        user_id=user.user_id,
        dataset_id=dataset_id,
        filename=f"v0{validated.extension}",
    )

    ds = Dataset(
        id=dataset_id,
        institution_id=user.institution_id,
        project_id=project.id,
        created_by_user_id=user.user_id,
        name=display_name,
        original_filename=safe_filename,
        status=DatasetStatus.PENDING.value,
    )
    db.add(ds)
    db.flush()

    try:
        put_bytes(
            key=storage_key,
            body=data,
            content_type=validated.content_type,
            settings=settings,
        )
    except Exception as exc:
        ds.status = DatasetStatus.DELETING.value
        db.flush()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "storage_failed",
                "message": "Could not store the file. Try again.",
            },
        ) from exc

    version = DatasetVersion(
        institution_id=user.institution_id,
        project_id=project.id,
        dataset_id=ds.id,
        parent_version_id=None,
        created_by_user_id=user.user_id,
        version_number=0,
        operation="upload",
        operation_params={"kind": validated.kind},
        actor="student",
        reason="Original upload",
        storage_key=storage_key,
        row_count=validated.row_count,
        column_count=validated.column_count,
        byte_size=len(data),
    )
    db.add(version)
    db.flush()
    ds.current_version_id = version.id
    ds.status = DatasetStatus.READY.value
    db.flush()
    return _dataset_response(ds, version)


@router.get("/{dataset_id}/download-url", response_model=DownloadUrlResponse)
def download_url(
    dataset_id: uuid.UUID,
    user: Annotated[AuthUser, Depends(require_member)],
    db: Annotated[Session, Depends(get_app_db_with_rls)],
) -> DownloadUrlResponse:
    """
    Issue a short-lived signed GET URL after Postgres/RLS confirms access.

    Never trust a client-supplied storage key or institution_id.
    """
    assert user.institution_id is not None
    settings = get_settings()
    ds = db.get(Dataset, dataset_id)
    if ds is None or ds.institution_id != user.institution_id:
        raise HTTPException(404, detail="Dataset not found.")
    if ds.status != DatasetStatus.READY.value or ds.current_version_id is None:
        raise HTTPException(409, detail="Dataset is not ready.")

    version = db.get(DatasetVersion, ds.current_version_id)
    if version is None:
        raise HTTPException(404, detail="Dataset version not found.")

    # Defense in depth: key must be under this institution (and preferably user).
    expected_prefix = f"{user.institution_id}/"
    if not version.storage_key.startswith(expected_prefix):
        raise HTTPException(500, detail="Storage key failed tenancy check.")

    url = presigned_get_url(version.storage_key, settings=settings)
    return DownloadUrlResponse(
        url=url,
        expires_in=settings.s3_presign_ttl_seconds,
        storage_key=version.storage_key,
    )


@router.delete("/{dataset_id}", response_model=DeleteResponse)
def delete_dataset(
    dataset_id: uuid.UUID,
    user: Annotated[AuthUser, Depends(require_member)],
    db: Annotated[Session, Depends(get_app_db_with_rls)],
) -> DeleteResponse:
    """Remove dataset, all versions, related artifacts, and storage objects."""
    assert user.institution_id is not None
    ds = db.get(Dataset, dataset_id)
    if ds is None or ds.institution_id != user.institution_id:
        raise HTTPException(404, detail="Dataset not found.")

    ds.status = DatasetStatus.DELETING.value
    db.flush()

    versions = db.scalars(
        select(DatasetVersion).where(DatasetVersion.dataset_id == ds.id)
    ).all()
    sessions = db.scalars(
        select(AnalysisSession).where(AnalysisSession.dataset_id == ds.id)
    ).all()
    session_ids = [s.id for s in sessions]

    keys: list[str] = [v.storage_key for v in versions if v.storage_key]
    if session_ids:
        artifacts = db.scalars(
            select(Artifact).where(Artifact.analysis_session_id.in_(session_ids))
        ).all()
        keys.extend(a.storage_key for a in artifacts if a.storage_key)
        db.execute(
            AgentStep.__table__.delete().where(
                AgentStep.analysis_session_id.in_(session_ids)
            )
        )
        db.execute(
            Artifact.__table__.delete().where(
                Artifact.analysis_session_id.in_(session_ids)
            )
        )
        db.execute(
            AnalysisSession.__table__.delete().where(
                AnalysisSession.id.in_(session_ids)
            )
        )

    ds.current_version_id = None
    db.flush()
    db.execute(
        DatasetVersion.__table__.delete().where(DatasetVersion.dataset_id == ds.id)
    )
    db.delete(ds)
    db.flush()

    try:
        delete_keys(keys)
    except Exception:
        # Row is already gone; sweeper can retry orphaned keys later.
        pass

    return DeleteResponse(id=str(dataset_id))
