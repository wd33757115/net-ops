"""网盘权限：应用层 RBAC + 团队归属。"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.auth.models import CurrentUser
from src.infrastructure.db.models import FileMetadata, StorageFolder, TeamMember


def _team_role(session: Session, team_id: str, user_id: str) -> str | None:
    member = (
        session.query(TeamMember)
        .filter(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id,
            TeamMember.is_deleted.is_(False),
        )
        .first()
    )
    return member.role if member else None


def can_write_storage(user: CurrentUser) -> bool:
    return user.role in {"admin", "operator"}


def check_folder_access(session: Session, user: CurrentUser, folder: StorageFolder, write: bool = False) -> None:
    if folder.is_deleted:
        raise HTTPException(status_code=404, detail="目录不存在")

    if folder.visibility == "private":
        if folder.owner_id != user.user_id and not user.is_admin():
            raise HTTPException(status_code=403, detail="无权访问该个人目录")
        if write and not can_write_storage(user):
            raise HTTPException(status_code=403, detail="只读用户无法修改文件")
        return

    if folder.visibility == "shared":
        if not folder.team_id:
            raise HTTPException(status_code=403, detail="团队目录配置错误")
        role = _team_role(session, folder.team_id, user.user_id)
        if user.is_admin():
            return
        if not role:
            raise HTTPException(status_code=403, detail="非团队成员无法访问")
        if write:
            if not can_write_storage(user):
                raise HTTPException(status_code=403, detail="只读用户无法修改文件")
            if role == "viewer":
                raise HTTPException(status_code=403, detail="团队查看者无法修改文件")
        return

    raise HTTPException(status_code=403, detail="未知可见性类型")


def check_file_access(session: Session, user: CurrentUser, file_row: FileMetadata, write: bool = False) -> None:
    if file_row.is_deleted:
        raise HTTPException(status_code=404, detail="文件不存在")

    if file_row.folder_id:
        folder = session.query(StorageFolder).filter(StorageFolder.id == file_row.folder_id).first()
        if folder:
            check_folder_access(session, user, folder, write=write)
            return

    if file_row.visibility == "private":
        if file_row.owner_id != user.user_id and not user.is_admin():
            raise HTTPException(status_code=403, detail="无权访问该文件")
        if write and not can_write_storage(user):
            raise HTTPException(status_code=403, detail="只读用户无法修改文件")
        return

    if file_row.visibility == "shared" and file_row.team_id:
        role = _team_role(session, file_row.team_id, user.user_id)
        if user.is_admin():
            return
        if not role:
            raise HTTPException(status_code=403, detail="非团队成员无法访问")
        if write:
            if not can_write_storage(user):
                raise HTTPException(status_code=403, detail="只读用户无法修改文件")
            if role == "viewer":
                raise HTTPException(status_code=403, detail="团队查看者无法修改文件")
        return

    raise HTTPException(status_code=403, detail="无权访问该文件")


def check_team_access(session: Session, user: CurrentUser, team_id: str, write: bool = False) -> str | None:
    if user.is_admin():
        return "admin"
    role = _team_role(session, team_id, user.user_id)
    if not role:
        raise HTTPException(status_code=403, detail="非团队成员")
    if write and role == "viewer":
        raise HTTPException(status_code=403, detail="团队查看者无法执行写操作")
    if write and not can_write_storage(user):
        raise HTTPException(status_code=403, detail="只读用户无法执行写操作")
    return role
