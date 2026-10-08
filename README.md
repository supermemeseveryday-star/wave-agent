# Wave Agent

**以自然语言为入口、重视证据质量的 AI Agent 操作系统 MVP。**

Wave Agent 将 Qwen 推理、世界模型、确定性工具、结果评估和经验记录连接成一条可运行的任务链。系统会区分已验证的工具结果与未经核实的模型回答：只有满足验证条件的经验才会进入训练候选集。

> 当前版本：`v0.1.0`。这是可运行的第一阶段 MVP，并非完整的自主训练或通用电脑操作系统。

## 已实现

- **自然语言工作台**：Next.js 界面展示对话、任务、世界模型、Skill、Workflow、训练数据和模型记录。
- **任务与进度**：FastAPI 提供聊天接口和 SSE 任务事件流，保存任务状态、工具活动、结果及错误。
- **Qwen 推理接入**：默认通过 Ollama 调用 Qwen，也可连接 OpenAI 兼容的聊天接口。
- **世界模型记录**：保存知识、原则、因果关系、状态、预测、经验、Skill 和 Workflow；手工录入的事实会标记为未独立验证。
- **预测场景**：使用有量化系数的因果关系计算下一状态，并明确标注不确定性及启发式概率。
- **受限工具执行**：支持安全算术、时间和经授权的 HTTPS 读取；未开放任意 Shell、发送、购买或发布操作。
- **评估与训练候选**：Judge 记录结果评价。未经验证的模型回答不会自动变成训练数据；候选模型可登记并接受基准分数门槛检查。

## 任务链

```text
用户输入
  → Intent Router / WaveMasterAgent
  → 世界模型检索
  → Qwen 规划或确定性工具
  → 结果评估
  → 经验记录
  → 已验证训练候选
  → 数据集构建
```

一个已实现的复用案例：首次询问 `What is 12 times 7?` 时，Qwen 选择算术工具；后续相似乘法题可直接走确定性路径。该优化目前只覆盖已识别的任务模式，不能代表所有任务都会减少模型调用。

## 本地启动

需要 Python 3.12、Node.js、[uv](https://docs.astral.sh/uv/) 和已安装目标模型的 [Ollama](https://ollama.com/)。默认模型名写在 [`.env.example`](.env.example) 中；如果你的 Ollama 模型名不同，请修改 `MODEL_NAME`。

### 1. 启动 API

```bash
uv venv --python 3.12
uv pip install -e '.[test]'
cp .env.example .env
source .venv/bin/activate
uvicorn apps.api.main:app --reload
```

API 文档：<http://127.0.0.1:8000/docs>

默认开发数据库是 `~/.wave-agent/wave.db`，因此本地开发不依赖 Docker。配置文件通过 `.env` 加载。

### 2. 启动工作台

在另一个终端执行：

```bash
cd dashboard
npm install
npm run dev
```

工作台：<http://127.0.0.1:3000>

如果 API 不在本机 `8000` 端口运行，可设置 `NEXT_PUBLIC_WAVE_API` 后重新启动前端。

### 3. 验证任务

```bash
curl -s http://127.0.0.1:8000/system/status
curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"计算 12 * 7"}'
```

运行不依赖外部模型的端到端演示：

```bash
python scripts/demo.py
```

该演示覆盖工具任务、相似任务、Skill、Workflow、数据集及候选模型门槛；它不会训练模型权重。

## 测试

```bash
pytest -q
cd dashboard && npm run build && npm audit --audit-level=moderate
```

## PostgreSQL / Redis

仓库提供 [`docker-compose.yml`](docker-compose.yml)，包含 PostgreSQL、pgvector、Redis 和 API 服务：

```bash
docker compose up --build
```

Compose 服务默认只映射到本机回环地址。Ollama 需单独运行。SQLite 是已验证的本地开发路径；PostgreSQL/Redis 配置存在，但本项目尚未对容器路径完成完整运行验证。

## 当前边界

- 联网研究尚无自动搜索与来源交叉验证流程；`/research` 当前复用聊天链路。
- 自然语言定时任务可识别，但后台 Scheduler 尚未接通。
- 浏览器及电脑操作 Robot、文件上传、向量检索和多用户权限系统尚未实现。
- `POST /training/run` 会返回 `501`：Qwen 权重训练后端尚未配置。训练数据集生成、候选登记和基准门槛已实现，但模型部署仍需人工执行。
- 项目 API 目前没有身份认证，不能直接暴露到公网。

设计与实现边界见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 项目结构

```text
apps/api/          FastAPI 接口
core/              Agent、推理、数据库与世界模型
models/            模型提供方适配
robots/            受限工具路由
training/          数据集与模型门槛
dashboard/        Next.js 工作台
scripts/           演示与 pgvector 初始化
tests/             自动测试
```

## License

尚未选择开源许可证。公开仓库前请根据你希望允许的使用方式添加 `LICENSE` 文件。
