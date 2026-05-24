# NetOps Agent - Django + React 架构

这是 NetOps Agent 的新前端架构，使用 Django + React 替代了原先的 Streamlit 前端。

## 架构说明

- **后端（FastAPI）**：保持不变，继续处理 AI 逻辑、Agent、RAG 等
- **中间层（Django）**：新增，提供用户界面、会话管理、API 代理
- **前端（React + Ant Design）**：现代化的聊天界面，参考 Grok、GPT 等设计

## 端口分配

- FastAPI 网关: `http://localhost:8000`
- Django 后端: `http://localhost:8001`
- React 前端: `http://localhost:3000`

## 快速启动

### 1. 先启动原有的 FastAPI 服务（在项目根目录）

确保 Docker 中间件已启动，然后：

```bash
# 在 netops-agent 目录
python -m src.gateway.main
```

### 2. 安装并启动 Django 后端

```bash
cd web/django_backend
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 8001
```

### 3. 安装并启动 React 前端

```bash
cd web/react_frontend
npm install
npm run dev
```

## 访问

- 前端界面: `http://localhost:3000` 或 `http://localhost:8001`
- FastAPI 文档: `http://localhost:8000/docs`

## 开发说明

- React 组件在 `web/react_frontend/src/`
- Django 视图在 `web/django_backend/chat/views.py`
- 状态管理使用 Zustand
- API 请求使用 Axios + React Query
