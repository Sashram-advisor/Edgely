# 合并对比简报

**对比基线**：`Sashram-advisor/Edgely`，`main` 分支，commit `da2d784`。  
**对比时间**：2026-11-02  
**对比方式**：目录与文件清单对比（不做逐行代码 diff）。

## 结论

| 项目 | 数量 |
| --- | ---: |
| 修改的已有文件 | 1 个（`README.md`，仅文档） |
| 新增文件 | 49 个（含本报告） |
| 删除文件 | 0 个 |
| 新增顶层文件夹 | 5 个：`docs/`、`services/`、`ui/`、`integrations/`、`integration_tests/` |
| 新增嵌套文件夹 | `backend/app/integrations/`，以及 `services/ai_tutor/`、`services/local_tutor/` 内部目录 |
| Git commit | 0 个（HEAD 仍是 `da2d784`，未 push） |

原有 Edgely 应用代码没有改动；`uvicorn app.main:app` 仍可单独运行。  
合并后的入口是 `uvicorn app.merged_main:app`。

## 1. 哪些地方有改变

| 位置 | 变化 | 说明 |
| --- | --- | --- |
| 根目录 | 新增 5 个文件 | `.dockerignore`、`.gitignore`、`requirements-merged.txt`、`requirements-dev.txt`、`requirements-ui.txt` |
| `README.md` | 修改 | 增加合并说明和快速开始；唯一被修改的已有文件 |
| `backend/` | 新增 7 个文件 | 合并入口、local-only 入口、AI 集成层、pgvector 迁移、环境模板 |
| `frontend/` | 新增 1 个文件 | 仅新增 `frontend/README.md` 说明；原 Next.js 脚手架源码未改 |
| `docs/` | 新文件夹 | 合并文档与本报告 |
| `services/` | 新文件夹 | 原样承接 repo 2 和 zip 的代码 |
| `ui/` | 新文件夹 | 合并后的 Streamlit UI |
| `integrations/` | 新文件夹 | Dockerfile、Compose、启动脚本 |
| `integration_tests/` | 新文件夹 | 离线结构/单元测试 |
| `ai/`、`infrastructure/`、`scripts/`、`documentation/`、`.github/` | 无变化 | 原目录保持原样 |

## 2. 新创建的文件夹

```text
Edgely/
├── docs/                              # 新增：合并文档、对比报告
├── services/                          # 新增：两个外部代码库的原始副本
│   ├── ai_tutor/                      # repo 2，21 个文件，原样保留
│   │   ├── backend/app/               # FastAPI 课程 RAG 后端
│   │   ├── ui/streamlit_app.py        # repo 2 原始 UI
│   │   ├── scripts/                   # embedding 回填等脚本
│   │   ├── migrations/                # 原始 pgvector 迁移
│   │   └── eval/                      # 原始评测骨架
│   └── local_tutor/                   # zip，main.py + data + 依赖
├── ui/                                # 新增：合并 UI（两种模式）
├── integrations/                      # 新增：Docker 与本地启动脚本
├── integration_tests/                 # 新增：离线测试
└── backend/app/integrations/          # 新增：组合层/挂载层
```

另有 `services/ai_tutor/backend/`、`services/ai_tutor/supabase/` 等 repo 2 原有子目录，不是 Edgely 原有目录。

## 3. 新的合并代码在哪里

| 文件 | 作用 |
| --- | --- |
| `backend/app/merged_main.py` | 合并入口：Edgely 原 app + `/ai-tutor` 挂载 + `/local-tutor` 路由 |
| `backend/app/local_only_main.py` | 只启动本地 Ollama tutor 的入口，不需要 Edgely 数据库 |
| `backend/app/integrations/ai_tutor_mount.py` | 用私有包名 `edgely_ai_tutor` 加载 repo 2，保留其原始相对 import |
| `backend/app/integrations/local_tutor_api.py` | 把 zip 的 Ollama RAG 暴露为 HTTP 接口 |
| `ui/merged_app.py` | 一个 UI，两种引擎：Course tutor / Local Ollama |
| `backend/app/database/migrations/20261102000100_ai_tutor_pgvector.sql` | 合并数据库迁移：pgvector、citation 字段、`match_document_chunks` |
| `integrations/docker-compose.yml` | API + UI + 可选 Ollama 的容器编排 |
| `integration_tests/test_merge.py` | 合并结构、挂载、检索辅助函数测试 |

## 4. AI progress 在哪里

AI 相关代码分为三块：

### 4.1 课程 RAG tutor（来自 repo 2）

位置：`services/ai_tutor/backend/app/`

- `chat.py`：完整对话流程（context → scope → history → rewrite → retrieve → prompt → Claude → 持久化）
- `context.py`：学习者画像、enrollment、薄弱 domain
- `retrieval.py`：Supabase pgvector 检索
- `embeddings.py`：Gemini/OpenAI embedding
- `prompt.py`：带 citations 的 prompt 构造
- `main.py`：FastAPI 路由（`/chat`、`/chat/stream`、`/users` 等）
- `config.py` / `db.py`：配置与 Supabase 客户端

对外入口：`/ai-tutor/*`（由 `backend/app/merged_main.py` 挂载）。

### 4.2 本地 Ollama tutor（来自 zip）

位置：

- `services/local_tutor/main.py`：原始 CLI，未改动
- `services/local_tutor/data/study_material.txt`：AWS 学习材料，未改动
- `backend/app/integrations/local_tutor_api.py`：新增 HTTP bridge

对外入口：`/local-tutor/chat`、`/local-tutor/health`、`/local-tutor/material`。

### 4.3 AI UI 与数据准备

- UI：`ui/merged_app.py`（合并 UI）；`services/ai_tutor/ui/streamlit_app.py`（repo 2 原始 UI，保留）
- Embedding 回填：`services/ai_tutor/scripts/embed_chunks.py`
- 数据库：`backend/app/database/migrations/20261102000100_ai_tutor_pgvector.sql`
- 环境变量：`backend/.env.example`

## 5. AI 当前进度

| 能力 | 状态 |
| --- | --- |
| repo 2 课程 RAG 后端移植 | 已完成，代码原样保留并挂载 |
| repo 2 原始 Streamlit UI | 已保留，可独立运行 |
| zip 本地 Ollama CLI | 已保留，可独立运行 |
| zip HTTP bridge | 已完成，端到端用 fake Ollama 验证过 |
| 合并 UI（两种模式） | 已完成，Streamlit 启动测试通过 |
| 合并 API | 已完成，`/`、`/docs`、`/ai-tutor/docs`、`/local-tutor/health` 实测 200 |
| pgvector 迁移 | 已提供，尚未在真实 Supabase 执行 |
| 课程 RAG 真实回答 | 未实测；需要 Supabase 凭据、迁移、embedding 回填 |
| 鉴权 | 沿用上游限制：`/ai-tutor` 暂无登录校验，不要直接公网暴露 |

## 6. 一句话总结

Edgely 原有代码基本没动；新增了 5 个顶层目录和 49 个文件（含本报告），把 **repo 2 的课程 RAG tutor**、**zip 的本地 Ollama tutor**、**合并 API/UI/迁移/测试/文档** 全部放在 `services/`、`backend/app/integrations/`、`ui/`、`docs/`、`integration_tests/` 中，通过 `backend/app/merged_main.py` 组合启动。
