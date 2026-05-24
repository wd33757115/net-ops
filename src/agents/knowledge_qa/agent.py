import sys
import time
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from langchain_core.messages import AIMessage
from langchain_deepseek import ChatDeepSeek

from src.common.config import get_settings
from src.core.rag_service.service import get_rag_service

settings = get_settings()
rag_service = get_rag_service()

# RAG-specific LLM (separate instance, faster settings)
rag_llm = ChatDeepSeek(
    model=settings.LLM_MODEL,
    temperature=0.1,
    api_key=settings.DEEPSEEK_API_KEY,
    request_timeout=30
)

# Simple LRU cache for RAG results (key: query hash, value: answer)
# In production, use Redis for cross-process cache
_rag_cache: dict[str, str] = {}
_MAX_CACHE_SIZE = 100


def _truncate_context(context: str, max_chars: int = 3000) -> str:
    """
    Truncate context to reduce token count and speed up LLM response.
    Keep the beginning (usually has the most relevant info) and add a note.
    """
    if len(context) <= max_chars:
        return context
    return (
        context[:max_chars]
        + f"\n\n[... 内容已截断，共 {len(context)} 字符 ...]"
    )


def knowledge_qa_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Knowledge QA Agent - RAG-based Q&A with caching and optimization.

    Optimizations:
    - Context truncation (max 3000 chars) to reduce LLM token count
    - Simple in-memory cache for repeated queries
    - Early exit when no documents retrieved
    - Concise prompt to reduce LLM processing time
    """
    query = state["messages"][-1].content
    print(f"\n[Knowledge QA Agent] Processing query: {query[:60]}...")

    t_start = time.time()

    metadata_filters = state.get("metadata_filters", None)

    # Retrieve documents (RAG retrieval: ~0.3-0.5s)
    retrieved = rag_service.retrieve_formatted(query, top_k=4, metadata_filters=metadata_filters)

    context = retrieved["context_str"]
    references = retrieved["references"]
    count = retrieved["count"]

    print(f"   - Retrieved {count} documents in {time.time()-t_start:.1f}s")

    # Early exit: no relevant documents found
    if count == 0:
        answer = (
            "抱歉，知识库中未找到与您问题相关的内容。\n\n"
            "**建议**：\n"
            "- 请换一种方式描述您的问题\n"
            "- 联系管理员补充相关知识库文档\n"
            "- 或者换个具体的技术问题提问"
        )
        print("   - No docs found, returning early exit answer")
    else:
        # Truncate context to speed up LLM response
        truncated_context = _truncate_context(context, max_chars=3000)

        # Check cache
        cache_key = f"{query[:50]}:{count}"
        if cache_key in _rag_cache:
            print("   - Cache hit! Returning cached answer")
            answer = _rag_cache[cache_key]
        else:
            # Build concise prompt (reduced from previous version)
            prompt = f"""Based on the knowledge base below, answer the question.
If no relevant info exists, say "知识库中暂无相关内容".

=== Knowledge Base ===
{truncated_context}
===

Q: {query}
A:"""

            # LLM generation: typically 1-3s depending on DeepSeek API latency
            t_llm = time.time()
            response = rag_llm.invoke(prompt)
            print(f"   - LLM generation took {time.time()-t_llm:.1f}s")

            answer = response.content.strip()

            # Cache the result (simple LRU)
            if len(_rag_cache) >= _MAX_CACHE_SIZE:
                _rag_cache.pop(next(iter(_rag_cache)))
            _rag_cache[cache_key] = answer

    # Build references string (deduplicated)
    if references:
        ref_str = "\n\n**References:**\n"
        seen = set()
        for ref in references[:3]:
            fname = ref.get("file", "unknown")
            if fname not in seen:
                ref_str += f"- {fname}\n"
                seen.add(fname)
        answer += ref_str

    print(f"   - Total RAG time: {time.time()-t_start:.1f}s, answer length: {len(answer)}")

    new_state = {
        **state,
        "messages": state["messages"] + [AIMessage(content=answer)],
        "context": context,
        "knowledge_references": references
    }

    return new_state
