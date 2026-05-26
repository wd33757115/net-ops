"""Skills 管理 API 路由。"""

from fastapi import APIRouter, HTTPException, status

from src.gateway.schemas import (
    CreateSkillRequest,
    SkillContentRequest,
    SkillFileUploadRequest,
    SkillToggleRequest,
    UpdateSkillRequest,
)
from src.skills.skill_manager import get_skill_manager

router = APIRouter(prefix="/api/v1/skills", tags=["Skills"])


def _manager():
    return get_skill_manager()


def _ensure_success(result: dict, default_status: int = 400):
    if not result.get("success", True):
        raise HTTPException(status_code=default_status, detail=result.get("message", "操作失败"))
    return result


@router.get("")
async def list_skills():
    return _manager().list_all_skills()


@router.get("/stats")
async def skill_stats():
    return _manager().get_stats()


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_skill(request: CreateSkillRequest):
    data = request.model_dump(exclude_none=True)
    return _ensure_success(_manager().create_skill(data))


@router.get("/{skill_name}/content")
async def get_skill_content(skill_name: str):
    content = _manager().get_skill_content(skill_name)
    if content is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' 不存在")
    return {"name": skill_name, "content": content}


@router.put("/{skill_name}/content")
async def save_skill_content(skill_name: str, request: SkillContentRequest):
    return _ensure_success(_manager().save_skill_content(skill_name, request.content))


@router.get("/{skill_name}/files")
async def list_skill_files(skill_name: str):
    result = _manager().list_skill_files(skill_name)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message", "Skill 不存在"))
    return result


@router.post("/{skill_name}/files")
async def upload_skill_file(skill_name: str, request: SkillFileUploadRequest):
    return _ensure_success(
        _manager().upload_skill_file(
            skill_name,
            request.folder,
            request.filename,
            request.file_content,
        )
    )


@router.patch("/{skill_name}/toggle")
async def toggle_skill(skill_name: str, request: SkillToggleRequest):
    return _ensure_success(_manager().toggle_skill(skill_name, request.enabled))


@router.post("/{skill_name}/reload")
async def reload_skill(skill_name: str):
    return _ensure_success(_manager().reload_skill(skill_name))


@router.post("/reload-all")
async def reload_all_skills():
    return _ensure_success(_manager().reload_all())


@router.put("/{skill_name}")
async def update_skill(skill_name: str, request: UpdateSkillRequest):
    data = request.model_dump(exclude_none=True)
    data["name"] = skill_name
    return _ensure_success(_manager().update_skill(skill_name, data))


@router.delete("/{skill_name}", status_code=status.HTTP_200_OK)
async def delete_skill(skill_name: str):
    return _ensure_success(_manager().delete_skill(skill_name))
