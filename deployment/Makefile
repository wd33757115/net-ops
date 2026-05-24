.PHONY: help install up down down-v logs ps init-db test celery fastapi streamlit build build-only django react up-all

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

install: ## 安装Python依赖
	pip install --upgrade pip
	pip install -r requirements.txt

up: ## 启动所有中间件服务
	cd deployment && docker-compose up -d postgres redis rabbitmq minio qdrant

up-all: ## 启动所有服务（包括应用服务）
	cd deployment && docker-compose up -d

build: ## 构建并启动所有服务
	cd deployment && docker-compose up -d --build

build-only: ## 仅构建镜像不启动
	cd deployment && docker-compose build

down: ## 停止所有服务
	cd deployment && docker-compose down

down-v: ## 停止服务并清理数据
	cd deployment && docker-compose down -v

logs: ## 查看所有服务日志
	cd deployment && docker-compose logs -f

logs-app: ## 仅查看应用服务日志
	cd deployment && docker-compose logs -f django react fastapi

ps: ## 查看服务状态
	cd deployment && docker-compose ps

init-db: ## 初始化数据库
	python -m scripts.init_db

django-migrate: ## Django 数据库迁移
	cd deployment && docker-compose exec django python manage.py migrate

django-shell: ## 进入 Django Shell
	cd deployment && docker-compose exec django python manage.py shell

celery: ## 启动 Celery Worker
	celery -A src.core.celery_tasks.celery_app worker --loglevel=info -P solo -c 2

fastapi: ## 启动 FastAPI Gateway
	python -m src.gateway.main

streamlit: ## 启动 Streamlit 前端
	streamlit run streamlit_app.py --server.port 8501

django: ## 本地启动 Django（开发）
	cd web/django_backend && python manage.py runserver 8001

react: ## 本地启动 React（开发）
	cd web/react_frontend && npm run dev

test: ## 运行测试
	pytest tests/ -v
