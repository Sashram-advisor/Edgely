# Team A — P1 交付说明（身份、权限与 Tutor 界面）

> English version: [README.md](./README.md)

基线：`main @ 97b203d`（PR #15 *Teammate A P0* 合并之后）。
任务来源：*Edgely readiness checklist v2，2026-11-17*，第 03 节（Team A）。

| ID | 任务 | 优先级 | 状态 |
|---|---|---|---|
| R6 | 前端能安装自己的登录客户端 | P1 | 依赖已在 P0 加入；用 `npm run build` 验证（见“验证”） |
| A5 | Dashboard 登录保护（route guard） | P1 | 完成 |
| T3 | SSE 规范写成文档；错误改为固定错误码 | P1 | 完成 |
| T4 | 按用户限流（429 + Retry-After）；记录每轮 token | P1 | 完成 |
| T5 | `APP_ENV=production` 时只能访问 `/tutor` | P1 | 完成 |

Team A 的 P0（R3、A1–A4、T1、T2、O4）已在 PR #15 合并。A6 是 P2，而且不需要做：
A1 选择了方案 (a)，浏览器直接连 Supabase Auth，后端不代理登录接口。

---

## 1. 每个任务改了什么

### R6 — 前端的 Supabase 客户端
`frontend/package.json` 里已经有 `@supabase/supabase-js ^2.49.0`（P0 加的）。
P1 只需要完成“完成标准”：`npm install && npm run build` 能通过。其他不用改。

### A5 — Dashboard 登录保护
**问题：** 任何人直接输入 `/dashboard` 都能看到页面。
**做法：** 在浏览器端做登录检查。

* Supabase 的 session 存在浏览器的 `localStorage`，不是 cookie，服务器端代码（middleware、server component）看不到，所以检查只能在浏览器里做。
* 检查过程中只显示“Checking your session…”，不渲染页面，避免隐私内容一闪而过。
* 没有 session → `router.replace("/login?next=/dashboard")`。用 `replace` 而不是 `push`，按返回键不会来回跳。
* 在任何标签页登出 → 立即跳转（监听 Supabase 的 `SIGNED_OUT` 事件）。
* 登录后回到 `next` 指定的页面。`safeNextPath()` 只接受本站路径，所以 `?next=https://evil.example` 不能被用来做开放重定向（open redirect）攻击。
* 这个 guard 只是用户体验上的拦截，真正的安全边界还是后端：每个 API 调用都需要有效的 Bearer token（A3）。

### T3 — SSE 规范与错误脱敏
**问题：** 事件格式只存在于代码里；出错时 stream 直接发 `{"detail": str(exc)}`，内部异常文本（SQL、URL，甚至可能是 key）会被发到浏览器。
**做法：**

* 完整规范写在 [`docs/api/tutor-sse.md`](../api/tutor-sse.md)。
* `backend/app/core/tutor_sse.py` 把 stream 中的任何异常转换为 `{"code", "message", "retryable", "error_id", "detail"}`，`code` 是四个固定错误码之一：
  `TUTOR_MODEL_UNAVAILABLE`、`TUTOR_MODEL_RATE_LIMITED`、`TUTOR_SAVE_FAILED`、`TUTOR_INTERNAL_ERROR`。
  `message` 是固定句子，绝不包含异常文本。
* 真正的异常和 traceback 写入服务器日志（logger `edgely.tutor.stream`），带同一个 `error_id`。用户看到的“Reference: 3f2a9c0d”可以直接对应到日志。
* 保留了 `detail` 字段（内容和 `message` 一样，已标记废弃），P1 之前的前端也能正常用。
* 前端 `streaming.ts` 读取新格式，把错误码转成友好提示。

### T4 — 限流与 token 记录
**问题：** 每个问题都调用两次模型（改写问题 + 回答），而且没有任何限流。
**做法：**

* `backend/app/core/rate_limit.py`：按用户的滑动窗口限流，`/tutor/chat` 和 `/tutor/chat/stream` 共用一个额度。
  默认每分钟 10 次、每天 200 次（`TUTOR_RATE_LIMIT_PER_MINUTE`、`TUTOR_RATE_LIMIT_PER_DAY`）。
  超出 → `429`，带 `Retry-After` 和 `X-Error-Code: TUTOR_RATE_LIMITED`。
  限流的 key 是从 token 验证出的用户 id；检查发生在调用模型之前。
* `main.py`：CORS 的 `expose_headers` 加上 `Retry-After` 和 `X-Error-Code`，否则浏览器的 JS 读不到这两个头。
* `chat.py`：
  * `needs_rewrite()`：问题本身完整时跳过改写调用（`REWRITE_MODE=auto`，默认值），大部分问题只调用一次模型。设成 `always` 可以恢复旧行为。
  * **两次调用**的 token 都会记录：assistant 那一行的 `tokens_in` / `tokens_out` 现在是整轮的总和；`done` 事件的 `usage` 新增 `rewrite_*` 和 `total_*`（旧字段不变）；每轮在 `edgely.tutor.usage` 写一行日志。
* 聊天界面遇到 429 时显示“You can ask again in N s.”。

### T5 — 生产环境只保留一个 tutor 入口
**问题：** 有三个 tutor 入口：`/tutor`（需要登录）、`/ai-tutor`（旧版，无登录，`GET /users` 会列出所有学员邮箱）、`/local-tutor`（无登录）。
**做法（在 O4 的“双开关”规则之上）：**

* `backend/.env.example` 改为 `APP_ENV=production`（原来是 `local`）。把模板复制到服务器上，不会再意外开启只该在本地用的功能。开发者在自己电脑上手动改成 `local`。
* `merged_main.py` 启动时检查实际注册了哪些路由：如果 `APP_ENV` 不是 `local`，却存在 `/ai-tutor` 或 `/local-tutor` 路由，就拒绝启动（fail closed）。
* `local_only_main.py`（只提供 `/local-tutor` 的独立入口）在 `APP_ENV` 不是 `local` 时拒绝启动。
* `integration_tests/test_merge.py::test_local_tutor_routes_are_registered` 测的是 O4 之前的行为，O4 之后会失败，已改为 `test_local_tutor_routes_are_off_by_default`。

---

## 2. P1 改动的文件

| 文件 | 新建 / 修改 | 任务 | 作用 |
|---|---|---|---|
| `frontend/components/auth/RequireAuth.tsx` | 新建 | A5 | 浏览器端登录保护组件 |
| `frontend/utilities/redirect.ts` | 新建 | A5 | `safeNextPath()` / `loginUrlFor()`：安全地“登录后返回原页面” |
| `frontend/app/dashboard/page.tsx` | 修改 | A5 | 用 `<RequireAuth>` 包住 `<Dashboard />` |
| `frontend/components/auth/LoginForm.tsx` | 修改 | A5 | 登录后去 `?next=` 指定的页面，而不是固定去 `/dashboard` |
| `backend/app/core/tutor_sse.py` | 新建 | T3 | SSE 帧格式、错误码、错误脱敏 |
| `docs/api/tutor-sse.md` | 新建 | T3 | SSE 规范文档 |
| `frontend/utilities/streaming.ts` | 修改 | T3、T4 | 读取错误码；读取 429 的 `Retry-After` |
| `frontend/types/tutor.ts` | 修改 | T3、T4 | 新增 `TutorStreamError`，扩展 `ChatUsage` |
| `frontend/components/chat/TutorChat.tsx` | 修改 | T3、T4 | 显示错误提示、等待时间和 reference id |
| `backend/app/routes/tutor.py` | 修改 | T3、T4 | 使用限流依赖和脱敏后的 error 事件 |
| `backend/app/core/rate_limit.py` | 新建 | T4 | 滑动窗口限流器 + FastAPI 依赖 |
| `backend/app/core/config.py` | 修改 | T4 | 新增 `tutor_rate_limit_per_minute`、`tutor_rate_limit_per_day` |
| `backend/app/main.py` | 修改 | T4 | CORS `expose_headers` |
| `services/ai_tutor/backend/app/chat.py` | 修改 | T4 | `needs_rewrite()`、记录改写 token、`_turn_usage()`、用量日志 |
| `services/ai_tutor/backend/app/config.py` | 修改 | T4 | 新增 `rewrite_mode` 设置 |
| `backend/.env.example` | 修改 | T4、T5 | `APP_ENV=production`、`REWRITE_MODE`、`TUTOR_RATE_LIMIT_*` |
| `backend/app/merged_main.py` | 修改 | T5 | `registered_paths()`、`_assert_single_tutor_surface()` |
| `backend/app/local_only_main.py` | 修改 | T5 | `APP_ENV` 不是 `local` 时拒绝启动 |
| `backend/tests/unit/test_rate_limit.py` | 新建 | T4 | 限流器单元测试（模拟时钟） |
| `backend/tests/unit/test_tutor_sse.py` | 新建 | T3 | 错误脱敏和分类测试 |
| `backend/tests/unit/test_config_safety.py` | 修改 | T4、T5 | local-tutor 双开关、模板默认值、限流默认值 |
| `integration_tests/test_tutor_p1.py` | 新建 | T3、T4 | 429 + Retry-After、SSE 事件顺序、错误脱敏、改写判断、token 统计 |
| `integration_tests/test_tutor_startup.py` | 修改 | T5 | production/development 只暴露 `/tutor`；本地入口拒绝在生产启动 |
| `integration_tests/test_merge.py` | 修改 | T5 | 修正过时的 `/local-tutor` 断言 |
| `integration_tests/test_tutor_auth.py` | 修改 | T4 | 每个测试之间重置限流器 |

---

## 3. 验证

```bash
# 后端（在仓库根目录，使用 Team C 的 R1 依赖清单建好的虚拟环境）
cd backend && python -m pytest tests/unit -q && cd ..
python -m pytest integration_tests -q

# 前端（R6 完成标准）
cd frontend
npm install
npm run build
```

手动检查：

| 任务 | 操作 | 预期结果 |
|---|---|---|
| A5 | 登出后打开 `http://localhost:3000/dashboard` | 跳到 `/login?next=%2Fdashboard`；登录后回到 `/dashboard` |
| A5 | 打开 `/login?next=https://evil.example` 并登录 | 进入 `/dashboard`，不会跳到外部网站 |
| T3 | 把 `ANTHROPIC_API_KEY` 设成无效值，然后提问 | 界面显示固定提示 + “Reference: xxxxxxxx”；服务器日志里有同一个 id 和完整 traceback；浏览器看不到异常文本 |
| T4 | 设 `TUTOR_RATE_LIMIT_PER_MINUTE=2`，快速问 3 个问题 | 第 3 个返回 `429` 和 `Retry-After`；界面显示“You can ask again in N s.” |
| T4 | 在同一对话里问两个问题，然后执行 `select tokens_in, tokens_out from messages where role='assistant' order by id desc limit 2` | 数值等于 `done` 事件里的 `usage.total_input_tokens` / `total_output_tokens` |
| T5 | `APP_ENV=production ENABLE_LEGACY_TUTOR_MOUNT=true ENABLE_LOCAL_TUTOR_MOUNT=true uvicorn app.merged_main:app` | `/ai-tutor/*` 和 `/local-tutor/*` 返回 404；`/tutor/*` 正常 |
| T5 | `APP_ENV=production uvicorn app.local_only_main:app` | 启动失败，提示“only runs with APP_ENV=local” |

---

## 4. 需要告诉团队的事

* **开发者的 `.env` 要改：** 模板现在是 `APP_ENV=production`。如果你要用 Streamlit 开发界面（`/ai-tutor`）或 Ollama tutor（`/local-tutor`），请在**你自己的** `backend/.env` 里改成 `APP_ENV=local`。
* **Team C（O5、L5）：** T4 改了 `services/ai_tutor/backend/app/chat.py` 里的 `_persist()`（把改写调用的 token 加进 `tokens_in` / `tokens_out`）。O5（每轮一个事务）和 L5（从 insert 结果拿 assistant id）也会改这个函数。请基于这次改动 rebase，或者跟 Team A 商量哪个 PR 先合并。
* **限流的局限：** 计数存在进程内存里。如果有 N 个 uvicorn worker，实际额度是设置值的 N 倍，重启后计数清零。MVP 阶段只有一个进程，没问题；扩容之前要换成 Redis。
* **旧版应用：** `/ai-tutor/chat/stream` 仍然会发原始异常文本，因为这个 vendored 应用按约定保持不改动。它只能在 `APP_ENV=local` 加显式开关时运行，生产环境永远不会出现。
* **前端规范变化：** `error` 事件的格式变了（旧的 `detail` 作为别名保留），`usage` 新增了字段。其他读这个 stream 的人请改为根据 `code` 判断。
