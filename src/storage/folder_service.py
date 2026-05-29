"""虚拟目录服务。"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.auth.models import CurrentUser
from src.infrastructure.db.models import FileMetadata, StorageFolder
from src.infrastructure.storage.minio_client import get_minio_storage
from src.storage.permissions import check_folder_access, check_team_access
from src.storage.schemas import FolderCreateRequest, FolderResponse, FolderTreeNode

ROOT_NAME = "根目录"
_SAFE_SEGMENT = re.compile(r"[^a-zA-Z0-9_\-\u4e00-\u9fff.]+")


def _folder_to_response(row: StorageFolder) -> FolderResponse:
    return FolderResponse(
        id=row.id,
        name=row.name,
        parent_id=row.parent_id,
        visibility=row.visibility,
        team_id=row.team_id,
        owner_id=row.owner_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _sanitize_segment(name: str) -> str:
    cleaned = _SAFE_SEGMENT.sub("_", name.strip())
    return cleaned or "untitled"


def build_folder_path(session: Session, folder: StorageFolder | None) -> str:
    if not folder:
        return ""
    parts: list[str] = []
    current: StorageFolder | None = folder
    visited: set[str] = set()
    while current and current.id not in visited:
        visited.add(current.id)
        if current.name != ROOT_NAME:
            parts.append(_sanitize_segment(current.name))
        if not current.parent_id:
            break
        current = (
            session.query(StorageFolder)
            .filter(StorageFolder.id == current.parent_id, StorageFolder.is_deleted.is_(False))
            .first()
        )
    parts.reverse()
    return "/".join(parts)


def build_object_prefix(session: Session, folder: StorageFolder | None, user: CurrentUser) -> str:
    rel = build_folder_path(session, folder)
    if folder and folder.visibility == "shared" and folder.team_id:
        base = f"shared/teams/{folder.team_id}"
    else:
        base = f"private/users/{user.user_id}"
    return f"{base}/{rel}".rstrip("/") if rel else base


def ensure_root_folder(
    session: Session,
    *,
    user: CurrentUser,
    visibility: str,
    team_id: str | None = None,
) -> StorageFolder:
    q = session.query(StorageFolder).filter(
        StorageFolder.is_deleted.is_(False),
        StorageFolder.parent_id.is_(None),
        StorageFolder.visibility == visibility,
    )
    if visibility == "private":
        q = q.filter(StorageFolder.owner_id == user.user_id)
    else:
        if not team_id:
            raise HTTPException(status_code=400, detail="团队目录需要 team_id")
        check_team_access(session, user, team_id, write=False)
        q = q.filter(StorageFolder.team_id == team_id)

    root = q.first()
    if root:
        return root

    now = datetime.now(timezone.utc)
    root = StorageFolder(
        id=f"fld-{uuid.uuid4().hex[:16]}",
        name=ROOT_NAME,
        parent_id=None,
        owner_id=user.user_id if visibility == "private" else None,
        team_id=team_id if visibility == "shared" else None,
        visibility=visibility,
        path_cache="",
        created_by=user.user_id,
        created_at=now,
        updated_at=now,
        is_deleted=False,
    )
    session.add(root)
    session.flush()
    return root


def get_folder_or_404(session: Session, folder_id: str) -> StorageFolder:
    folder = (
        session.query(StorageFolder)
        .filter(StorageFolder.id == folder_id, StorageFolder.is_deleted.is_(False))
        .first()
    )
    if not folder:
        raise HTTPException(status_code=404, detail="目录不存在")
    return folder


def create_folder(session: Session, user: CurrentUser, req: FolderCreateRequest) -> FolderResponse:
    if not req.parent_id:
        parent = ensure_root_folder(
            session,
            user=user,
            visibility=req.visibility,
            team_id=req.team_id,
        )
    else:
        parent = get_folder_or_404(session, req.parent_id)
        check_folder_access(session, user, parent, write=True)
        if parent.visibility != req.visibility:
            raise HTTPException(status_code=400, detail="子目录可见性需与父目录一致")
        if req.visibility == "shared" and parent.team_id != req.team_id:
            raise HTTPException(status_code=400, detail="team_id 与父目录不一致")

    dup = (
        session.query(StorageFolder)
        .filter(
            StorageFolder.parent_id == parent.id,
            StorageFolder.name == req.name.strip(),
            StorageFolder.is_deleted.is_(False),
        )
        .first()
    )
    if dup:
        raise HTTPException(status_code=409, detail="同级目录下已存在同名文件夹")

    now = datetime.now(timezone.utc)
    folder = StorageFolder(
        id=f"fld-{uuid.uuid4().hex[:16]}",
        name=req.name.strip(),
        parent_id=parent.id,
        owner_id=user.user_id if req.visibility == "private" else None,
        team_id=req.team_id if req.visibility == "shared" else None,
        visibility=req.visibility,
        path_cache=build_folder_path(session, parent),
        created_by=user.user_id,
        created_at=now,
        updated_at=now,
        is_deleted=False,
    )
    session.add(folder)
    session.flush()
    return _folder_to_response(folder)


def _collect_subtree_folder_ids(session: Session, root_id: str) -> list[str]:
    ids = [root_id]
    queue = [root_id]
    while queue:
        parent_id = queue.pop(0)
        children = (
            session.query(StorageFolder.id)
            .filter(StorageFolder.parent_id == parent_id, StorageFolder.is_deleted.is_(False))
            .all()
        )
        for (child_id,) in children:
            ids.append(child_id)
            queue.append(child_id)
    return ids


def _is_descendant(session: Session, ancestor_id: str, candidate_id: str) -> bool:
    current = get_folder_or_404(session, candidate_id)
    visited: set[str] = set()
    while current.parent_id and current.id not in visited:
        visited.add(current.id)
        if current.parent_id == ancestor_id:
            return True
        current = get_folder_or_404(session, current.parent_id)
    return False


def _rebuild_object_key(session: Session, folder: StorageFolder, filename: str, user: CurrentUser) -> str:
    prefix = build_object_prefix(session, folder, user)
    return f"{prefix}/{_sanitize_segment(filename)}"


def _relocate_files_in_folders(session: Session, user: CurrentUser, folder_ids: list[str]) -> None:
    storage = get_minio_storage()
    files = (
        session.query(FileMetadata)
        .filter(
            FileMetadata.folder_id.in_(folder_ids),
            FileMetadata.is_deleted.is_(False),
            FileMetadata.status == "active",
        )
        .all()
    )
    for row in files:
        folder = get_folder_or_404(session, row.folder_id)
        new_key = _rebuild_object_key(session, folder, row.name, user)
        if row.object_key != new_key:
            if not storage.copy_object(row.object_key, new_key):
                raise HTTPException(status_code=500, detail=f"移动文件 {row.name} 失败")
            storage.delete_object(row.object_key)
            row.object_key = new_key
        row.updated_at = datetime.now(timezone.utc)


def delete_folder(session: Session, user: CurrentUser, folder_id: str) -> None:
    folder = get_folder_or_404(session, folder_id)
    if folder.parent_id is None:
        raise HTTPException(status_code=400, detail="不能删除根目录")
    check_folder_access(session, user, folder, write=True)

    folder_ids = _collect_subtree_folder_ids(session, folder_id)
    storage = get_minio_storage()
    files = (
        session.query(FileMetadata)
        .filter(
            FileMetadata.folder_id.in_(folder_ids),
            FileMetadata.is_deleted.is_(False),
        )
        .all()
    )
    now = datetime.now(timezone.utc)
    for row in files:
        storage.delete_object(row.object_key)
        row.is_deleted = True
        row.updated_at = now

    folders = session.query(StorageFolder).filter(StorageFolder.id.in_(folder_ids)).all()
    for fld in folders:
        fld.is_deleted = True
        fld.updated_at = now


def rename_folder(session: Session, user: CurrentUser, folder_id: str, new_name: str) -> FolderResponse:
    folder = get_folder_or_404(session, folder_id)
    if folder.parent_id is None:
        raise HTTPException(status_code=400, detail="不能重命名根目录")
    check_folder_access(session, user, folder, write=True)

    name = new_name.strip()
    dup = (
        session.query(StorageFolder)
        .filter(
            StorageFolder.parent_id == folder.parent_id,
            StorageFolder.name == name,
            StorageFolder.is_deleted.is_(False),
            StorageFolder.id != folder.id,
        )
        .first()
    )
    if dup:
        raise HTTPException(status_code=409, detail="同级目录下已存在同名文件夹")

    folder.name = name
    folder.updated_at = datetime.now(timezone.utc)
    folder_ids = _collect_subtree_folder_ids(session, folder_id)
    _relocate_files_in_folders(session, user, folder_ids)
    session.flush()
    return _folder_to_response(folder)


def move_folder(session: Session, user: CurrentUser, folder_id: str, target_folder_id: str) -> FolderResponse:
    folder = get_folder_or_404(session, folder_id)
    if folder.parent_id is None:
        raise HTTPException(status_code=400, detail="不能移动根目录")
    target = get_folder_or_404(session, target_folder_id)
    if folder.id == target.id:
        raise HTTPException(status_code=400, detail="不能移动到自身")
    if _is_descendant(session, folder.id, target.id):
        raise HTTPException(status_code=400, detail="不能移动到子目录")

    check_folder_access(session, user, folder, write=True)
    check_folder_access(session, user, target, write=True)
    if folder.visibility != target.visibility:
        raise HTTPException(status_code=400, detail="只能在相同空间内移动")
    if folder.visibility == "shared" and folder.team_id != target.team_id:
        raise HTTPException(status_code=400, detail="团队目录不一致")

    dup = (
        session.query(StorageFolder)
        .filter(
            StorageFolder.parent_id == target.id,
            StorageFolder.name == folder.name,
            StorageFolder.is_deleted.is_(False),
            StorageFolder.id != folder.id,
        )
        .first()
    )
    if dup:
        raise HTTPException(status_code=409, detail="目标目录下已存在同名文件夹")

    folder.parent_id = target.id
    folder.updated_at = datetime.now(timezone.utc)
    folder_ids = _collect_subtree_folder_ids(session, folder_id)
    _relocate_files_in_folders(session, user, folder_ids)
    session.flush()
    return _folder_to_response(folder)


def list_children(
    session: Session,
    user: CurrentUser,
    *,
    folder_id: str | None,
    visibility: str,
    team_id: str | None,
) -> tuple[StorageFolder | None, list[StorageFolder]]:
    if folder_id:
        current = get_folder_or_404(session, folder_id)
        check_folder_access(session, user, current, write=False)
    else:
        current = ensure_root_folder(session, user=user, visibility=visibility, team_id=team_id)

    children = (
        session.query(StorageFolder)
        .filter(
            StorageFolder.parent_id == current.id,
            StorageFolder.is_deleted.is_(False),
        )
        .order_by(StorageFolder.name.asc())
        .all()
    )
    return current, children


def build_breadcrumb(session: Session, folder: StorageFolder | None) -> list[FolderResponse]:
    if not folder:
        return []
    chain: list[StorageFolder] = []
    current: StorageFolder | None = folder
    visited: set[str] = set()
    while current and current.id not in visited:
        visited.add(current.id)
        chain.append(current)
        if not current.parent_id:
            break
        current = get_folder_or_404(session, current.parent_id)
    chain.reverse()
    return [_folder_to_response(f) for f in chain]


def build_folder_tree(session: Session, user: CurrentUser, root: StorageFolder) -> FolderTreeNode:
    check_folder_access(session, user, root, write=False)

    def _walk(parent_id: str) -> list[FolderTreeNode]:
        rows = (
            session.query(StorageFolder)
            .filter(
                StorageFolder.parent_id == parent_id,
                StorageFolder.is_deleted.is_(False),
            )
            .order_by(StorageFolder.name.asc())
            .all()
        )
        return [
            FolderTreeNode(
                id=row.id,
                name=row.name,
                parent_id=row.parent_id,
                children=_walk(row.id),
            )
            for row in rows
        ]

    return FolderTreeNode(
        id=root.id,
        name=root.name,
        parent_id=root.parent_id,
        children=_walk(root.id),
    )
