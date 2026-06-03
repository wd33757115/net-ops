# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""知识库管理 API。"""

from fastapi import APIRouter, HTTPException
from urllib.parse import unquote

from src.core.rag_service.knowledge_manager import get_knowledge_manager
from src.gateway.schemas import KnowledgeUploadRequest

router = APIRouter(prefix="/api/v1/knowledge", tags=["Knowledge"])


def _manager():
    return get_knowledge_manager()


def _ensure_success(result: dict, status: int = 400):
    if not result.get("success", True):
        raise HTTPException(status_code=status, detail=result.get("message", "操作失败"))
    return result


@router.get("/documents")
async def list_knowledge_documents():
    """列出 knowledge_base 中已加载/可索引的文档。"""
    return _manager().list_documents()


@router.post("/documents")
async def upload_knowledge_document(request: KnowledgeUploadRequest):
    """上传文档（base64），可选自动重建索引。"""
    return _ensure_success(
        _manager().upload_document(
            request.filename,
            request.file_content,
            folder=request.folder,
            relative_path=request.relative_path,
            auto_reindex=request.auto_reindex,
        )
    )


@router.get("/documents/{doc_path:path}/content")
async def get_knowledge_document_content(doc_path: str):
    """预览文档内容。"""
    rel = unquote(doc_path)
    result = _manager().get_document_content(rel)
    if not result.get("success", True):
        raise HTTPException(status_code=404, detail=result.get("message", "文档不存在"))
    return result


@router.delete("/documents/{doc_path:path}")
async def delete_knowledge_document(doc_path: str, auto_reindex: bool = True):
    """删除文档，可选自动重建索引。"""
    rel = unquote(doc_path)
    return _ensure_success(_manager().delete_document(rel, auto_reindex=auto_reindex))


@router.get("/stats")
async def knowledge_stats():
    """知识库统计（文档数、索引片段数等）。"""
    return _manager().get_stats()


@router.post("/reindex")
async def reindex_knowledge():
    """重建 Chroma 向量索引。"""
    result = _manager().reindex()
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message", "重建索引失败"))
    return result
