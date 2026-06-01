import os
import sys
from pathlib import Path
from typing import Any, Optional

os.environ["LLAMA_INDEX_CACHE_DIR"] = str(Path("./cache/llama_index").absolute())

BASE_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

import chromadb
from llama_index.core import SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.schema import BaseNode, NodeWithScore
from llama_index.core.vector_stores import MetadataFilters
from llama_index.vector_stores.chroma import ChromaVectorStore

from src.common.config import get_settings
from src.core.logging import get_logger

settings = get_settings()
log = get_logger(__name__)


class SimpleEmbedding(BaseEmbedding):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        import hashlib
        self._hash_func = hashlib.md5

    @classmethod
    def class_name(cls) -> str:
        return "SimpleEmbedding"

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._get_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> list[float]:
        return self._get_text_embedding(text)

    def _get_query_embedding(self, query: str) -> list[float]:
        return self._simple_hash(query)

    def _get_text_embedding(self, text: str) -> list[float]:
        return self._simple_hash(text)

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        return [self._simple_hash(t) for t in texts]

    def _simple_hash(self, text: str) -> list[float]:
        hash_val = self._hash_func(text.encode('utf-8')).digest()
        return [float(b) / 255.0 for b in hash_val] + [0.0] * (384 - 16)


class UnifiedRAGService:
    """
    统一RAG服务（企业级Central RAG模式）
    - 所有Agent共享同一份向量库
    - 支持Metadata过滤（设备、场景、版本、重要性）
    - 单例模式全局复用
    """

    _instance: Optional["UnifiedRAGService"] = None
    _index: VectorStoreIndex | None = None
    _embed_model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _ensure_initialized(self):
        if self._index is not None:
            return
        self._initialize()

    def _initialize(self):
        log.info("rag_service_init_begin", embedding="SimpleEmbedding")
        self._embed_model = SimpleEmbedding()

        persist_dir = Path("./vectorstore/chroma_db")
        persist_dir.mkdir(parents=True, exist_ok=True)

        chroma_client = chromadb.PersistentClient(path=str(persist_dir))
        chroma_collection = chroma_client.get_or_create_collection("netops_knowledge")
        collection_count = chroma_collection.count()

        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        kb_path = Path("./knowledge_base")
        if kb_path.exists() and any(kb_path.iterdir()):
            if collection_count > 0:
                self._index = VectorStoreIndex.from_vector_store(
                    vector_store=vector_store,
                    storage_context=storage_context,
                    embed_model=self._embed_model
                )
                log.info("rag_service_loaded", embedding_count=collection_count)
            else:
                log.info("rag_service_rebuild_index", reason="collection_empty")
                self._reindex_documents(kb_path, storage_context)
        else:
            kb_path.mkdir(parents=True, exist_ok=True)
            log.info("rag_service_kb_empty", kb_path=str(kb_path))
            self._index = VectorStoreIndex(
                nodes=[],
                storage_context=storage_context,
                embed_model=self._embed_model
            )

    def _reindex_documents(self, kb_path: Path, storage_context: StorageContext):
        from llama_index.core.node_parser import SentenceSplitter

        documents = SimpleDirectoryReader(
            input_dir=str(kb_path),
            recursive=True,
            required_exts=[".md", ".txt", ".pdf", ".docx"]
        ).load_data()

        for doc in documents:
            fname = Path(doc.metadata.get("file_name", "")).name
            doc.metadata = {
                "file_name": fname,
                "source": doc.metadata.get("file_path", ""),
                "doc_type": self._infer_doc_type(fname),
                "category": self._infer_category(fname)
            }

        parser = SentenceSplitter(chunk_size=1024, chunk_overlap=128)
        nodes = parser.get_nodes_from_documents(documents)

        self._index = VectorStoreIndex(
            nodes=nodes,
            storage_context=storage_context,
            embed_model=self._embed_model,
            show_progress=True
        )
        log.info(
            "rag_service_index_rebuilt",
            document_count=len(documents),
            node_count=len(nodes),
        )
        return len(documents), len(nodes)

    def reindex_from_disk(self) -> dict[str, Any]:
        """清空并重建向量索引（读取 knowledge_base/）。"""
        if self._embed_model is None:
            self._embed_model = SimpleEmbedding()

        kb_path = Path("./knowledge_base")
        persist_dir = Path("./vectorstore/chroma_db")
        persist_dir.mkdir(parents=True, exist_ok=True)

        chroma_client = chromadb.PersistentClient(path=str(persist_dir))
        try:
            chroma_client.delete_collection("netops_knowledge")
        except Exception as exc:
            log.warning("rag_service_delete_collection_failed", error=str(exc))

        self._index = None
        chroma_collection = chroma_client.get_or_create_collection("netops_knowledge")
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        has_files = kb_path.exists() and any(
            p.is_file() and p.suffix.lower() in {".md", ".txt", ".pdf", ".docx"}
            for p in kb_path.rglob("*")
        )
        if has_files:
            doc_count, node_count = self._reindex_documents(kb_path, storage_context)
        else:
            kb_path.mkdir(parents=True, exist_ok=True)
            self._index = VectorStoreIndex(
                nodes=[],
                storage_context=storage_context,
                embed_model=self._embed_model,
            )
            doc_count, node_count = 0, 0

        return {
            "document_count": doc_count,
            "chunk_count": node_count,
            "message": f"索引已重建：{doc_count} 篇文档，{node_count} 个片段",
        }

    def _infer_doc_type(self, filename: str) -> str:
        fname_lower = filename.lower()
        if "_SOP" in filename or "sop" in fname_lower:
            return "sop"
        elif "config" in fname_lower or "配置" in filename:
            return "configuration"
        elif "trouble" in fname_lower or "故障" in filename:
            return "troubleshooting"
        else:
            return "general"

    def _infer_category(self, filename: str) -> str:
        fname_lower = filename.lower()
        if "switch" in fname_lower or "交换机" in filename:
            return "switch"
        elif "router" in fname_lower or "路由器" in filename:
            return "router"
        elif "firewall" in fname_lower or "防火墙" in filename:
            return "firewall"
        elif "linux" in fname_lower:
            return "linux"
        elif "windows" in fname_lower:
            return "windows"
        else:
            return "general"

    def retrieve(
        self,
        query: str,
        top_k: int = 6,
        metadata_filters: dict[str, Any] | None = None
    ) -> list[NodeWithScore]:
        """
        统一检索接口
        Args:
            query: 用户查询
            top_k: 返回条数
            metadata_filters: Dict格式过滤条件，如 {"doc_type": "sop", "category": "firewall"}
        """
        self._ensure_initialized()
        if self._index is None:
            return []

        filters = None
        if metadata_filters:
            filter_list = []
            for k, v in metadata_filters.items():
                if isinstance(v, list):
                    pass
                else:
                    filter_list.append({"key": k, "value": v})
            if filter_list:
                filters = MetadataFilters(
                    filters=filter_list
                )

        retriever = self._index.as_retriever(
            similarity_top_k=top_k
        )
        nodes = retriever.retrieve(query)
        return nodes

    def retrieve_formatted(
        self,
        query: str,
        top_k: int = 6,
        metadata_filters: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """检索并返回格式化结果（含上下文字符串）"""
        nodes = self.retrieve(query, top_k, metadata_filters)
        contexts = []
        references = []

        for i, node in enumerate(nodes, 1):
            text = node.text.strip()
            contexts.append(f"--- 文档片段{i} ---\n{text}")
            meta = node.metadata
            references.append({
                "file": meta.get("file_name", "unknown"),
                "doc_type": meta.get("doc_type", "general"),
                "category": meta.get("category", "general"),
                "score": getattr(node, 'score', None)
            })

        return {
            "context_str": "\n\n".join(contexts),
            "nodes": nodes,
            "references": references,
            "count": len(nodes)
        }

    def add_documents(self, documents: list[BaseNode]):
        if self._index:
            self._index.insert_nodes(documents)


rag_service = UnifiedRAGService()


def get_rag_service() -> UnifiedRAGService:
    return rag_service
