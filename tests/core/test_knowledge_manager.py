# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""知识库管理 API 单元测试。"""

import base64

import pytest

from src.core.rag_service.knowledge_manager import KnowledgeManager, get_knowledge_manager


def test_list_knowledge_documents_returns_list():
    docs = get_knowledge_manager().list_documents()
    assert isinstance(docs, list)
    for item in docs:
        assert "file_name" in item
        assert "relative_path" in item
        assert "doc_type" in item
        assert "indexed" in item


def test_knowledge_stats_shape():
    stats = get_knowledge_manager().get_stats()
    assert "document_count" in stats
    assert stats["vector_store"] == "chroma"


def test_upload_preview_delete_roundtrip(tmp_path, monkeypatch):
    mgr = KnowledgeManager()
    monkeypatch.setattr(mgr, "_kb_root", tmp_path / "kb")
    mgr._kb_root.mkdir(parents=True)

    content = "# 测试文档\n\nhello knowledge"
    b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
    up = mgr.upload_document("test.md", b64, auto_reindex=False)
    assert up["success"] is True

    preview = mgr.get_document_content("test.md")
    assert preview["success"] is True
    assert preview["preview_type"] == "text"
    assert "hello knowledge" in preview["content"]

    deleted = mgr.delete_document("test.md", auto_reindex=False)
    assert deleted["success"] is True
    assert not (mgr._kb_root / "test.md").exists()


def test_resolve_safe_path_rejects_traversal():
    mgr = KnowledgeManager()
    with pytest.raises(ValueError):
        mgr._resolve_safe_path("../etc/passwd")
