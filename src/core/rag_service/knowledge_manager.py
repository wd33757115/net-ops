# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""知识库文档管理（扫描 knowledge_base/ + Chroma 索引状态）。"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".md", ".txt", ".pdf", ".docx"}
MAX_TEXT_PREVIEW_BYTES = 512 * 1024


class KnowledgeManager:
    def __init__(self) -> None:
        root = Path(__file__).resolve().parent.parent.parent.parent
        self._kb_root = root / "knowledge_base"
        self._chroma_dir = root / "vectorstore" / "chroma_db"

    def _rag(self):
        from src.core.rag_service.service import get_rag_service

        return get_rag_service()

    def _infer_doc_type(self, filename: str) -> str:
        return self._rag()._infer_doc_type(filename)

    def _infer_category(self, filename: str) -> str:
        return self._rag()._infer_category(filename)

    def _resolve_safe_path(self, relative_path: str) -> Path:
        rel = relative_path.replace("\\", "/").strip().lstrip("/")
        if not rel or ".." in rel.split("/"):
            raise ValueError("非法文档路径")
        kb_resolved = self._kb_root.resolve()
        target = (self._kb_root / rel).resolve()
        try:
            target.relative_to(kb_resolved)
        except ValueError as exc:
            raise ValueError("文档路径越界") from exc
        return target

    def _build_relative_path(self, filename: str, folder: str = "", relative_path: str | None = None) -> str:
        if relative_path:
            return relative_path.replace("\\", "/").strip().lstrip("/")
        safe_name = Path(filename).name
        if not safe_name or safe_name.startswith(".") or ".." in safe_name:
            raise ValueError("非法文件名")
        folder = (folder or "").replace("\\", "/").strip().strip("/")
        if folder and ".." in folder.split("/"):
            raise ValueError("非法子目录")
        return f"{folder}/{safe_name}" if folder else safe_name

    def _chroma_chunk_counts(self) -> dict[str, int]:
        """按 file_name 统计已索引 chunk 数。"""
        try:
            import chromadb

            if not self._chroma_dir.exists():
                return {}
            client = chromadb.PersistentClient(path=str(self._chroma_dir))
            coll = client.get_or_create_collection("netops_knowledge")
            if coll.count() == 0:
                return {}
            data = coll.get(include=["metadatas"])
            counts: dict[str, int] = {}
            for meta in data.get("metadatas") or []:
                if not meta:
                    continue
                name = meta.get("file_name") or Path(meta.get("source", "")).name
                if name:
                    counts[name] = counts.get(name, 0) + 1
            return counts
        except Exception as exc:
            logger.warning("读取 Chroma 索引统计失败: %s", exc)
            return {}

    def list_documents(self) -> list[dict[str, Any]]:
        """列出 knowledge_base 下所有支持的文档及索引状态。"""
        chunk_counts = self._chroma_chunk_counts()
        documents: list[dict[str, Any]] = []

        if not self._kb_root.exists():
            self._kb_root.mkdir(parents=True, exist_ok=True)
            return documents

        for path in sorted(self._kb_root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in ALLOWED_EXTENSIONS:
                continue

            rel = path.relative_to(self._kb_root).as_posix()
            stat = path.stat()
            file_name = path.name
            chunks = chunk_counts.get(file_name, 0)

            documents.append(
                {
                    "id": rel,
                    "file_name": file_name,
                    "relative_path": rel,
                    "size_bytes": stat.st_size,
                    "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    "doc_type": self._infer_doc_type(file_name),
                    "category": self._infer_category(file_name),
                    "indexed": chunks > 0,
                    "chunk_count": chunks,
                }
            )

        return documents

    def get_document_content(self, relative_path: str) -> dict[str, Any]:
        """预览文档：文本直接返回，docx 提取正文，pdf/大二进制返回 base64。"""
        target = self._resolve_safe_path(relative_path)
        if not target.is_file():
            return {"success": False, "message": "文档不存在"}

        suffix = target.suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            return {"success": False, "message": f"不支持的文件类型: {suffix}"}

        size = target.stat().st_size
        rel = target.relative_to(self._kb_root).as_posix()
        base = {
            "success": True,
            "id": rel,
            "file_name": target.name,
            "relative_path": rel,
            "size_bytes": size,
            "truncated": False,
        }

        if suffix in {".md", ".txt"}:
            raw = target.read_bytes()
            truncated = len(raw) > MAX_TEXT_PREVIEW_BYTES
            if truncated:
                raw = raw[:MAX_TEXT_PREVIEW_BYTES]
            text = raw.decode("utf-8", errors="replace")
            return {
                **base,
                "preview_type": "text",
                "content_type": "text/markdown" if suffix == ".md" else "text/plain",
                "content": text,
                "truncated": truncated,
            }

        if suffix == ".docx":
            try:
                from docx import Document

                doc = Document(str(target))
                lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
                text = "\n\n".join(lines)
                truncated = len(text.encode("utf-8")) > MAX_TEXT_PREVIEW_BYTES
                if truncated:
                    text = text[: MAX_TEXT_PREVIEW_BYTES // 2]
                return {
                    **base,
                    "preview_type": "extracted",
                    "content_type": "text/plain",
                    "content": text or "（文档无文本内容）",
                    "truncated": truncated,
                }
            except Exception as exc:
                return {"success": False, "message": f"DOCX 解析失败: {exc}"}

        # pdf 等二进制：返回 base64 供前端下载
        raw = target.read_bytes()
        truncated = len(raw) > MAX_TEXT_PREVIEW_BYTES
        if truncated:
            preview_bytes = raw[:MAX_TEXT_PREVIEW_BYTES]
        else:
            preview_bytes = raw
        return {
            **base,
            "preview_type": "binary",
            "content_type": "application/pdf" if suffix == ".pdf" else "application/octet-stream",
            "content": base64.b64encode(preview_bytes).decode("ascii"),
            "download_base64": base64.b64encode(raw).decode("ascii"),
            "truncated": truncated,
            "message": "该格式不支持在线渲染，可下载查看",
        }

    def upload_document(
        self,
        filename: str,
        file_content: str,
        *,
        folder: str = "",
        relative_path: str | None = None,
        auto_reindex: bool = True,
    ) -> dict[str, Any]:
        """上传文档到 knowledge_base（base64）。"""
        try:
            rel = self._build_relative_path(filename, folder, relative_path)
            target = self._resolve_safe_path(rel)

            if target.suffix.lower() not in ALLOWED_EXTENSIONS:
                return {
                    "success": False,
                    "message": f"仅支持: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
                }

            raw = base64.b64decode(file_content)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)

            result = {
                "success": True,
                "message": f"文档 {rel} 上传成功",
                "relative_path": rel,
            }
            if auto_reindex:
                reindex_result = self.reindex()
                result["reindex"] = reindex_result
            return result
        except Exception as exc:
            logger.exception("上传知识库文档失败")
            return {"success": False, "message": str(exc)}

    def delete_document(self, relative_path: str, *, auto_reindex: bool = True) -> dict[str, Any]:
        """删除 knowledge_base 中的文档。"""
        try:
            target = self._resolve_safe_path(relative_path)
            if not target.is_file():
                return {"success": False, "message": "文档不存在"}

            rel = target.relative_to(self._kb_root).as_posix()
            target.unlink()

            result = {"success": True, "message": f"文档 {rel} 已删除", "relative_path": rel}
            if auto_reindex:
                result["reindex"] = self.reindex()
            return result
        except Exception as exc:
            logger.exception("删除知识库文档失败")
            return {"success": False, "message": str(exc)}

    def get_stats(self) -> dict[str, Any]:
        docs = self.list_documents()
        total_chunks = sum(d.get("chunk_count", 0) for d in docs)
        indexed_docs = sum(1 for d in docs if d.get("indexed"))

        chroma_count = 0
        try:
            import chromadb

            if self._chroma_dir.exists():
                client = chromadb.PersistentClient(path=str(self._chroma_dir))
                coll = client.get_or_create_collection("netops_knowledge")
                chroma_count = coll.count()
        except Exception:
            pass

        return {
            "document_count": len(docs),
            "indexed_document_count": indexed_docs,
            "indexed_chunks": chroma_count or total_chunks,
            "kb_path": str(self._kb_root),
            "vector_store": "chroma",
            "collection": "netops_knowledge",
            "supported_extensions": sorted(ALLOWED_EXTENSIONS),
        }

    def reindex(self) -> dict[str, Any]:
        """重建 Chroma 向量索引。"""
        try:
            stats = self._rag().reindex_from_disk()
            return {"success": True, **stats}
        except Exception as exc:
            logger.exception("知识库重建索引失败")
            return {"success": False, "message": str(exc)}


_manager: KnowledgeManager | None = None


def get_knowledge_manager() -> KnowledgeManager:
    global _manager
    if _manager is None:
        _manager = KnowledgeManager()
    return _manager
