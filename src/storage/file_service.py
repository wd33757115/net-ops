"""文件上传/下载/分享服务。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.auth.models import CurrentUser
from src.infrastructure.db.models import FileMetadata, StorageFolder, Team, TeamMember
from src.infrastructure.storage.minio_client import get_minio_storage
from src.storage import folder_service as fs
from src.storage.permissions import check_file_access, check_folder_access, check_team_access, can_write_storage
from src.storage.schemas import (
    DownloadResponse,
    FileResponse,
    ShareFileRequest,
    TeamCreateRequest,
    TeamMemberAddRequest,
    TeamResponse,
    UploadCompleteRequest,
    UploadInitRequest,
    UploadInitResponse,
)

UPLOAD_EXPIRES = 3600
DOWNLOAD_EXPIRES = 3600 * 24


def _file_to_response(row: FileMetadata) -> FileResponse:
    return FileResponse(
        id=row.id,
        name=row.name,
        folder_id=row.folder_id,
        visibility=row.visibility,
        team_id=row.team_id,
        owner_id=row.owner_id,
        content_type=row.content_type,
        size_bytes=row.size_bytes or 0,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_files_in_folder(session: Session, folder_id: str) -> list[FileMetadata]:
    return (
        session.query(FileMetadata)
        .filter(
            FileMetadata.folder_id == folder_id,
            FileMetadata.is_deleted.is_(False),
            FileMetadata.status == "active",
        )
        .order_by(FileMetadata.name.asc())
        .all()
    )


def init_upload(session: Session, user: CurrentUser, req: UploadInitRequest) -> UploadInitResponse:
    if not can_write_storage(user):
        raise HTTPException(status_code=403, detail="只读用户无法上传")

    if req.folder_id:
        folder = fs.get_folder_or_404(session, req.folder_id)
    else:
        folder = fs.ensure_root_folder(
            session,
            user=user,
            visibility=req.visibility,
            team_id=req.team_id,
        )
    check_folder_access(session, user, folder, write=True)

    prefix = fs.build_object_prefix(session, folder, user)
    safe_name = fs._sanitize_segment(req.filename)
    object_key = f"{prefix}/{safe_name}"
    file_id = f"file-{uuid.uuid4().hex[:16]}"
    now = datetime.now(timezone.utc)

    row = FileMetadata(
        id=file_id,
        name=req.filename,
        folder_id=folder.id,
        object_key=object_key,
        owner_id=user.user_id if req.visibility == "private" else None,
        team_id=req.team_id if req.visibility == "shared" else folder.team_id,
        visibility=req.visibility,
        content_type=req.content_type,
        size_bytes=req.size_bytes,
        status="pending",
        created_by=user.user_id,
        created_at=now,
        updated_at=now,
        is_deleted=False,
    )
    session.add(row)
    session.flush()

    storage = get_minio_storage()
    if not storage.is_ready():
        raise HTTPException(status_code=503, detail="MinIO 未就绪")
    upload_url = storage.presigned_put_url(object_key, expires=UPLOAD_EXPIRES)
    if not upload_url:
        raise HTTPException(status_code=500, detail="无法生成上传地址")

    return UploadInitResponse(
        file_id=file_id,
        object_key=object_key,
        upload_url=upload_url,
        expires_in=UPLOAD_EXPIRES,
    )


def complete_upload(session: Session, user: CurrentUser, req: UploadCompleteRequest) -> FileResponse:
    row = session.query(FileMetadata).filter(FileMetadata.id == req.file_id).first()
    if not row or row.is_deleted:
        raise HTTPException(status_code=404, detail="文件记录不存在")
    check_file_access(session, user, row, write=True)

    storage = get_minio_storage()
    stat = storage.stat_object(row.object_key)
    if not stat:
        raise HTTPException(status_code=400, detail="对象尚未上传至 MinIO，请先完成 PUT 上传")

    row.status = "active"
    row.size_bytes = req.size_bytes if req.size_bytes is not None else stat.get("size", 0)
    row.etag = stat.get("etag")
    row.content_type = row.content_type or stat.get("content_type")
    row.updated_at = datetime.now(timezone.utc)
    session.flush()
    return _file_to_response(row)


def get_download_url(session: Session, user: CurrentUser, file_id: str) -> DownloadResponse:
    row = session.query(FileMetadata).filter(FileMetadata.id == file_id, FileMetadata.is_deleted.is_(False)).first()
    if not row or row.status != "active":
        raise HTTPException(status_code=404, detail="文件不存在")
    check_file_access(session, user, row, write=False)

    storage = get_minio_storage()
    url = storage.get_presigned_url(row.object_key, expires=DOWNLOAD_EXPIRES)
    if not url:
        raise HTTPException(status_code=500, detail="无法生成下载地址")
    return DownloadResponse(
        file_id=row.id,
        filename=row.name,
        download_url=url,
        expires_in=DOWNLOAD_EXPIRES,
    )


def delete_file(session: Session, user: CurrentUser, file_id: str) -> None:
    row = session.query(FileMetadata).filter(FileMetadata.id == file_id, FileMetadata.is_deleted.is_(False)).first()
    if not row:
        raise HTTPException(status_code=404, detail="文件不存在")
    check_file_access(session, user, row, write=True)

    storage = get_minio_storage()
    storage.delete_object(row.object_key)
    row.is_deleted = True
    row.updated_at = datetime.now(timezone.utc)


def share_file_to_team(session: Session, user: CurrentUser, req: ShareFileRequest) -> FileResponse:
    source = session.query(FileMetadata).filter(FileMetadata.id == req.file_id, FileMetadata.is_deleted.is_(False)).first()
    if not source or source.status != "active":
        raise HTTPException(status_code=404, detail="源文件不存在")
    check_file_access(session, user, source, write=True)
    check_team_access(session, user, req.team_id, write=True)

    if req.target_folder_id:
        target_folder = fs.get_folder_or_404(session, req.target_folder_id)
        if target_folder.visibility != "shared" or target_folder.team_id != req.team_id:
            raise HTTPException(status_code=400, detail="目标目录须为同一团队的共享目录")
    else:
        target_folder = fs.ensure_root_folder(session, user=user, visibility="shared", team_id=req.team_id)

    prefix = fs.build_object_prefix(session, target_folder, user)
    safe_name = fs._sanitize_segment(source.name)
    dest_key = f"{prefix}/{safe_name}"

    storage = get_minio_storage()
    if not storage.copy_object(source.object_key, dest_key):
        raise HTTPException(status_code=500, detail="复制到团队空间失败")

    now = datetime.now(timezone.utc)
    new_row = FileMetadata(
        id=f"file-{uuid.uuid4().hex[:16]}",
        name=source.name,
        folder_id=target_folder.id,
        object_key=dest_key,
        owner_id=user.user_id,
        team_id=req.team_id,
        visibility="shared",
        content_type=source.content_type,
        size_bytes=source.size_bytes,
        etag=source.etag,
        status="active",
        created_by=user.user_id,
        created_at=now,
        updated_at=now,
        is_deleted=False,
    )
    session.add(new_row)
    session.flush()
    return _file_to_response(new_row)


def list_teams(session: Session, user: CurrentUser) -> list[TeamResponse]:
    if user.is_admin():
        teams = session.query(Team).filter(Team.is_deleted.is_(False)).order_by(Team.name.asc()).all()
        result: list[TeamResponse] = []
        for t in teams:
            count = (
                session.query(TeamMember)
                .filter(TeamMember.team_id == t.id, TeamMember.is_deleted.is_(False))
                .count()
            )
            result.append(
                TeamResponse(
                    id=t.id,
                    name=t.name,
                    description=t.description,
                    role="admin",
                    member_count=count,
                )
            )
        return result

    rows = (
        session.query(Team, TeamMember.role)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .filter(
            TeamMember.user_id == user.user_id,
            TeamMember.is_deleted.is_(False),
            Team.is_deleted.is_(False),
        )
        .order_by(Team.name.asc())
        .all()
    )
    out: list[TeamResponse] = []
    for team, role in rows:
        count = (
            session.query(TeamMember)
            .filter(TeamMember.team_id == team.id, TeamMember.is_deleted.is_(False))
            .count()
        )
        out.append(
            TeamResponse(
                id=team.id,
                name=team.name,
                description=team.description,
                role=role,
                member_count=count,
            )
        )
    return out


def create_team(session: Session, user: CurrentUser, req: TeamCreateRequest) -> TeamResponse:
    if not user.is_admin():
        raise HTTPException(status_code=403, detail="仅管理员可创建团队")
    now = datetime.now(timezone.utc)
    team_id = f"team-{uuid.uuid4().hex[:12]}"
    team = Team(
        id=team_id,
        name=req.name.strip(),
        description=req.description,
        created_by=user.user_id,
        created_at=now,
        updated_at=now,
        is_deleted=False,
    )
    session.add(team)
    session.add(
        TeamMember(
            id=f"tm-{uuid.uuid4().hex[:12]}",
            team_id=team_id,
            user_id=user.user_id,
            role="owner",
            created_at=now,
            is_deleted=False,
        )
    )
    session.flush()
    fs.ensure_root_folder(session, user=user, visibility="shared", team_id=team_id)
    return TeamResponse(id=team.id, name=team.name, description=team.description, role="owner", member_count=1)


def add_team_member(session: Session, user: CurrentUser, team_id: str, req: TeamMemberAddRequest) -> dict:
    if not user.is_admin():
        role = check_team_access(session, user, team_id, write=True)
        if role != "owner":
            raise HTTPException(status_code=403, detail="仅团队所有者可添加成员")

    team = session.query(Team).filter(Team.id == team_id, Team.is_deleted.is_(False)).first()
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")

    existing = (
        session.query(TeamMember)
        .filter(
            TeamMember.team_id == team_id,
            TeamMember.user_id == req.user_id,
            TeamMember.is_deleted.is_(False),
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="用户已在团队中")

    session.add(
        TeamMember(
            id=f"tm-{uuid.uuid4().hex[:12]}",
            team_id=team_id,
            user_id=req.user_id,
            role=req.role,
            created_at=datetime.now(timezone.utc),
            is_deleted=False,
        )
    )
    return {"success": True, "team_id": team_id, "user_id": req.user_id}
