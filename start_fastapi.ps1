# 直接启动 FastAPI 测试
cd C:\Users\wangd\PycharmProjects\PythonProject\netops-agent
& "venv\Scripts\python.exe" -m uvicorn src.gateway.main:app --host 0.0.0.0 --port 8000 --reload