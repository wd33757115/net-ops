import streamlit as st
import httpx
import json
from typing import Optional, Dict, Any
from pathlib import Path

# 添加项目根目录到 PATH
root_dir = Path(__file__).parent.parent
import sys
sys.path.insert(0, str(root_dir))

FASTAPI_BASE_URL = "http://localhost:8000"


def check_api_health() -> bool:
    try:
        r = httpx.get(f"{FASTAPI_BASE_URL}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def send_chat_message(query: str, thread_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    payload = {"query": query}
    if thread_id:
        payload["thread_id"] = thread_id

    try:
        r = httpx.post(
            f"{FASTAPI_BASE_URL}/api/v1/chat",
            json=payload,
            timeout=120
        )
        if r.status_code == 200:
            return r.json()
        else:
            st.error(f"API 错误: {r.status_code} - {r.text}")
            return None
    except Exception as e:
        st.error(f"请求失败: {str(e)}")
        return None


st.set_page_config(
    page_title="NetOps 运维智能体",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "企业级运维AI Agent系统 v2.0"
    }
)

with st.sidebar:
    st.title("🛠️ NetOps Agent")
    st.caption("企业级运维智能体系统 v2.0")

    with st.container():
        st.subheader("📊 系统状态")
        if check_api_health():
            st.success("✅ FastAPI Gateway: 在线")
        else:
            st.error("❌ FastAPI Gateway: 离线")
            st.info("请先启动 FastAPI 服务: `python -m src.gateway.main`")

    st.divider()

    with st.container():
        st.subheader("🔧 对话配置")
        if "thread_id" not in st.session_state:
            import uuid
            st.session_state.thread_id = f"ui-thread-{uuid.uuid4().hex[:10]}"

        thread_id_input = st.text_input(
            "Thread ID（持久化多轮）",
            value=st.session_state.thread_id,
            help="相同 Thread ID 可以恢复历史对话"
        )
        st.session_state.thread_id = thread_id_input

        if st.button("🔄 新建对话", use_container_width=True):
            import uuid
            new_id = f"ui-thread-{uuid.uuid4().hex[:10]}"
            st.session_state.thread_id = new_id
            st.session_state.messages = []
            st.rerun()

    st.divider()

    with st.expander("📚 功能说明"):
        st.markdown("""
        **支持场景：**
        - ✅ 知识库问答 (Knowledge QA)
        - ⏳ 脚本执行 (Script Executor, 阶段2)
        - ⏳ ITSM Webhook (阶段3)
        """)

st.title("🏭 数据中心 & 园区网运维智能体")

st.info("""
💡 **架构亮点：Supervisor Agent + PostgreSQL 持久化 + 统一RAG服务**
- 对话状态持久化，关闭浏览器再打开相同 Thread ID 可继续
- 所有Agent共享统一向量库，保证知识一致性
""", icon="🏗️")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("请输入运维问题或指令 (如: 交换机端口Down了怎么办？)..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("🧠 Agent 处理中...", expanded=True) as status:
            status.write("📍 Supervisor 正在路由决策...")

            result = send_chat_message(prompt, st.session_state.thread_id)

            if result:
                status.write(f"✅ Agent: {result.get('agent_type')}")
                response = result.get("response", "")
                status.update(label="Agent 执行完成!", state="complete", expanded=False)
                st.session_state.messages.append({"role": "assistant", "content": response})

                with st.container():
                    st.markdown(response)

                    if result.get("agent_type"):
                        st.caption(f"路由结果: {result.get('agent_type')} | Thread ID: {result.get('thread_id')}")
            else:
                status.update(label="处理失败", state="error", expanded=True)
                err_msg = "处理请求失败，请检查 FastAPI 服务是否已启动"
                st.error(err_msg)
                st.session_state.messages.append({"role": "assistant", "content": err_msg})
