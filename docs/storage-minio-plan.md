<!-- SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# MinIO 网盘落地方案

## 架构决策（最佳实践）

| 决策 | 选择 | 理由 |
|------|------|------|
| 目录模型 | **虚拟目录（PostgreSQL）+ MinIO object_key 前缀** | 层级查询、权限继承、面包屑无需 list_objects 递归 |
| 上传路径 | **Presigned PUT → complete 确认** | 大文件不经 BFF/FastAPI 中转，降低带宽与超时风险 |
| 权限 | **应用层 RBAC + 团队归属**（Phase 5 可补 Bucket Policy） | 与现有 `CurrentUser` / JWT / BFF 头注入一致 |
| 用户体系 | **Django SQLite 用户 + PG 网盘元数据** | 不重复 users 表，沿用 `user_id` 字符串关联 |
| 团队共享 | **teams + team_members + shared/teams/{id}/ 前缀** | 清晰隔离个人与团队空间 |

## 对象 Key 规范

```
private/users/{user_id}/{folder_path}/{filename}
shared/teams/{team_id}/{folder_path}/{filename}
```

## API（FastAPI `/api/v1/storage`，BFF `/api/storage/`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/teams` | 当前用户可见团队 |
| POST | `/teams` | 创建团队（admin） |
| POST | `/teams/{id}/members` | 添加成员 |
| POST | `/folders` | 新建目录 |
| DELETE | `/folders/{id}` | 删除目录（软删） |
| GET | `/folders/tree` | 目录树 |
| GET | `/list` | 当前目录子项 + 面包屑 |
| POST | `/upload/init` | 获取 Presigned PUT |
| POST | `/upload/complete` | 确认上传写元数据 |
| GET | `/files/{id}/download` | Presigned GET |
| DELETE | `/files/{id}` | 删除文件 |
| POST | `/share` | 个人文件复制到团队空间 |

## 数据库表（`init_db_models` 自动建表）

- `netops_teams` / `netops_team_members`
- `netops_storage_folders` / `netops_file_metadata`

## 前端

- 路由：`/storage`（`StoragePage.tsx`）
- 侧栏：「网盘」
- 上传：浏览器 `fetch PUT` 至 MinIO presigned URL

## MinIO CORS（浏览器直传必配）

在 MinIO 控制台 → Bucket `netops-files` → Access Rules → CORS，或使用 `mc`：

```json
[
  {
    "AllowedOrigin": ["http://localhost:3000"],
    "AllowedMethod": ["GET", "PUT", "HEAD"],
    "AllowedHeader": ["*"],
    "ExposeHeader": ["ETag"],
    "MaxAgeSeconds": 3000
  }
]
```

## 启动与验证

```powershell
# 中间件（含 MinIO）已由 start.ps1 拉起
.\scripts\test\start.ps1

# 1. admin 登录 → 网盘 → 创建团队（账户管理同账号）
# 2. 我的文件：新建文件夹、上传
# 3. 分享到团队 → 团队共享 Tab 查看
```

## 阶段 6（后续）

- Skill 产出自动写入 `file_metadata`
- 分片上传 / 版本 / 回收站
- RAG 索引网盘文档
- MinIO Bucket Policy 硬隔离
