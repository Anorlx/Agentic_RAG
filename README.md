# SuperAgentic_RAG

> 面向水稻农业知识服务的多源证据 Agentic RAG 系统。

SuperAgentic_RAG 将用户上传的技术规程、试验资料和田间记录，与天气、政策、病虫害动态、市场信息和最新研究等时效性公开信息分开取证，并按问题意图选择合适的证据路径。回答会附带可核验的文档片段或网页来源，帮助用户回看结论依据。

> 适用主题：水稻栽培、品种与育种、病虫害、土壤与施肥、水分管理、农机，以及用户上传的项目资料。

## 核心能力

| 能力 | 说明 |
| --- | --- |
| 多源证据路由 | 将请求约束为直接回答、知识库检索、网页搜索、双源并行取证四条路径 |
| Agentic RAG | 对复杂问题规划子问题，执行检索、证据评分、有限改写与结果合成 |
| 层级索引 | L1/L2/L3 父子分块，L3 精准召回，命中集中时自动合并父级上下文 |
| 混合检索 | BGE-M3 Dense Retrieval + Milvus 原生 BM25 + RRF 融合 |
| 本地精排 | 可选本地 `bge-reranker-v2-m3` Cross-Encoder 重排，避免依赖外部 Rerank API |
| 可观测回答 | 展示路由、检索、合并、精排、证据评分、改写与引用来源，不展示隐藏推理 |
| 文档管理 | 支持 PDF、Word、Excel、HTML 的异步上传、索引、删除和分块树审阅 |

## 技术栈

| 层级 | 技术 |
| --- | --- |
| Agent / LLM | LangGraph、LangChain、OpenAI-compatible LLM、Pydantic Structured Output |
| RAG | BGE-M3、Milvus、BM25、RRF、Auto-merging、`bge-reranker-v2-m3`、Step-back、HyDE |
| 后端与数据 | FastAPI、SQLAlchemy、PostgreSQL、Redis、MinIO、etcd、Docker Compose |
| 前端 | Vue 3、TypeScript、Vite、Pinia、Axios、SSE |
| 评测与质量 | LangSmith、单元测试、检索 Trace、Schema Validation |
| 外部信息 | Tavily（可选） |

## 工作流

```mermaid
flowchart TD
    U[用户问题] --> P[加载 AGENTS.md<br/>领域范围与路由规则]
    P --> S{LangGraph Supervisor}

    S -->|direct| D[直接回答]
    S -->|knowledge_base| R[Agentic RAG 子图]
    S -->|web_search| W[Tavily 网页搜索]
    S -->|knowledge_base_and_web_search| RW[并行执行 RAG 与网页搜索]

    R --> C[复杂度规划<br/>简单问题 / 并行子问题]
    C --> H[检索 L3 叶子块<br/>BGE-M3 Dense + BM25]
    H --> F[RRF 融合]
    F --> M[Auto-merging<br/>L3 → L2 → L1]
    M --> RR[本地 Cross-Encoder 精排]
    RR --> G{结构化证据评分}
    G -->|充分| A[基于证据生成答案]
    G -->|不足| Q[单次 Step-back / HyDE<br/>澄清或无可靠知识]
    Q --> H

    D --> A
    W --> A
    RW --> A
    A --> O[流式回答 + 引用 + 执行 Trace]
```

### 证据路由

| 路径 | 适用问题 | 执行方式 |
| --- | --- | --- |
| `direct` | 稳定通用知识 | 直接回答，不执行无效检索 |
| `knowledge_base` | 上传资料中的事实、数据、流程与规程 | 执行 Agentic RAG |
| `web_search` | 当前天气、政策、市场、病虫害动态与最新研究 | 执行网页搜索 |
| `knowledge_base_and_web_search` | 同时需要本地资料和时效信息 | 并行取证后联合回答 |

## 检索设计

### 三级分块与上下文加载

文档按解析单元分为 L1 / L2 / L3。PDF 通常按页解析；各层均优先在段落、句末标点、换行和逗号等自然边界切分。

| 层级 | 最大字符数 | 重叠字符数 | 存储与职责 |
| --- | ---: | ---: | --- |
| L1 | 2400 | 400 | PostgreSQL / Redis；章节级上下文 |
| L2 | 1600 | 200 | PostgreSQL / Redis；主题或小节级上下文 |
| L3 | 800 | 100 | Milvus；最小可检索叶子片段 |

每个 L3 保存 `parent_chunk_id`（所属 L2）与 `root_chunk_id`（所属 L1）。检索只针对 L3；当同一父块下多个 L3 命中时，系统以 L2 或 L1 替换零散片段，实现“条款级定位 + 章节级语义补全”。

### 混合召回、精排与证据门控

1. BGE-M3 生成稠密向量，在 Milvus 的 HNSW 索引中进行语义检索。
2. Milvus 中文 Analyzer（Jieba）自动将 `text` 转为 BM25 稀疏向量，进行关键词检索。
3. 使用 Reciprocal Rank Fusion（RRF）融合两路候选，再执行 Auto-merging。
4. 可选本地 Cross-Encoder 对候选精排，按阈值保留结果。
5. 独立证据评分模型输出相关性、可回答性、歧义、缺失条件和下一步路由。
6. 仅当存在相关信号但证据不足时，在 Step-back 与 HyDE 中二选一进行**一次**改写检索；仍不足则澄清或拒答。

## 数据流

```text
PDF / Word / Excel / HTML
          │
          ▼
解析、文本净化、三级分块
          │
          ├── L1 / L2 父块 ──► PostgreSQL ──► Redis 缓存
          │
          └── L3 + Dense 向量 + BM25 稀疏向量 ──► Milvus
                                                         │
用户问题 ──► Supervisor ──► Agentic RAG / 网页搜索 ────┘
                                                         │
                                                引用与可观测 Trace
```

## 快速开始

### 前置条件

- Python 3.12+
- Node.js 18+
- Docker Desktop 与 Docker Compose
- 可访问的 OpenAI-compatible LLM 接口
- 可选：本地 BGE-M3 与 `bge-reranker-v2-m3` 模型目录

### 1. 安装依赖

```bash
git clone <your-repository-url>
cd SuperAgentic_RAG

# 推荐使用 uv；也可在 Python 3.12+ 环境中执行 pip install -e .
uv sync

cd frontend
npm ci
```

### 2. 配置环境变量

```bash
cd ..
cp .env.example .env
```

请在 `.env` 中配置模型、存储服务与密钥。以下为常用示例，真实密钥不得提交到 Git：

```dotenv
# LLM：最终回答、复杂度规划/改写、证据评分
ARK_API_KEY=your_api_key
BASE_URL=https://your-llm-endpoint/v1
MODEL=your_model
FAST_MODEL=your_fast_model
GRADE_MODEL=your_grade_model

# 本地 Embedding
EMBEDDING_MODEL=/path/to/bge-m3
EMBEDDING_DEVICE=cpu
DENSE_EMBEDDING_DIM=1024

# 可选：未配置时自动降级为不精排
LOCAL_RERANK_MODEL=/path/to/bge-reranker-v2-m3
LOCAL_RERANK_DEVICE=cpu

MILVUS_HOST=127.0.0.1
MILVUS_PORT=19530
DATABASE_URL=postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/langchain_app
REDIS_URL=redis://127.0.0.1:6379/0

# 可选：实时网页搜索
TAVILY_API_KEY=your_tavily_key
```

### 3. 启动基础服务

```bash
docker compose up -d
docker compose ps
```

如默认镜像源不可用，可使用本地镜像覆盖：

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d
```

默认端口：PostgreSQL `5432`、Redis `6379`、Milvus `19530`、Milvus health `9091`、Attu `8080`。

### 4. 启动应用

开发模式：

```bash
# Terminal 1：后端
uv run uvicorn backend.app:app --host 0.0.0.0 --port 8000

# Terminal 2：前端
cd frontend
npm run dev
```

生产构建可由 FastAPI 托管：

```bash
cd frontend
npm run build

cd ..
uv run uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

访问应用：`http://127.0.0.1:8000/`。API 文档：`http://127.0.0.1:8000/docs`

## 验证与评测

```bash
# 后端单元测试
uv run python -m unittest discover -s tests -v

# 前端测试与构建
cd frontend
npm test
npm run build
```

仓库包含路由、查询改写、检索降级、Trace Schema、分块树与文档索引等自动化测试。

如需进行 LangSmith 端到端实验，先配置 Dataset 和凭证，再运行：

```bash
uv run python langsmith_eval.py
```

该脚本会以独立会话调用完整 Agent 流程，输出最终回答与 `rag_trace`，适合回归检查。正式效果评测建议标注“问题 → 相关 L3 证据块 / 参考答案”，并报告路由准确率、Recall@K、MRR、nDCG、引用忠实度与拒答准确率，同时保留数据集规模和 Baseline 口径。

## 目录结构

```text
SuperAgentic_RAG/
├── AGENTS.md                     # 可编辑的农业知识范围与路由偏好
├── backend/
│   ├── chat/supervisor.py         # 外层 LangGraph Supervisor
│   ├── rag/pipeline.py            # 内层 Agentic RAG 子图
│   ├── rag/utils.py               # 混合检索、Auto-merging、Rerank
│   ├── indexing/                  # 解析、分块、Embedding、Milvus 写入
│   ├── api/routes/                # Auth、Chat、Documents、Sessions API
│   └── infra/                     # PostgreSQL、Redis、JWT
├── frontend/                      # Vue 3 前端
├── tests/                         # 后端单元测试
├── docker-compose.yml             # PostgreSQL、Redis、Milvus 等依赖
├── docker-compose.local.yml       # 可选的本地镜像覆盖
├── langsmith_eval.py              # LangSmith 端到端评测入口
└── .env.example                   # 环境变量模板
```

## 优点与边界

### 优点

- 区分私有资料和实时公开信息，避免单一 RAG 链路覆盖所有问题。
- 通过层级分块和按需父块加载，平衡精确命中与上下文完整性。
- 混合检索、精排、证据评分和有限改写构成可控的检索纠错闭环。
- 前端与 `rag_trace` 提供可验证执行状态，便于定位错误路由、错误召回和证据不足。
- 本地 Embedding / Reranker 可避免将文档正文发送到第三方向量化或精排服务。

### 当前边界

- Excel 当前以文本解析并进入文档检索，不按工作表、行列或公式执行结构化分析。
- 当前是文本 RAG：未实现 OCR、图片向量化或视觉模型推理；扫描件、图表和田间照片中的视觉信息不能可靠回答。
- 实时信息质量取决于网页搜索服务和来源本身；关键农事决策应结合当地实况与农技人员意见复核。
- 本项目用于信息检索与辅助决策，不替代植保处方、农药合规判断或田间诊断。

## 🚀 未来展望：文件化农业上下文库

> 📌 **规划中，尚未实现。** 本方向借鉴 OpenViking 的文件系统式上下文组织与分层加载理念[^1]；当前项目并未集成 OpenViking SDK。

当前项目的 L1/L2/L3 是面向检索的**分块层级**。下一阶段会在此之上增加面向人和 Agent 的**资源目录层**：将上传的文档、Excel 工作表、田间试验项目和数据集组织成可浏览的“文件”，而非仅作为匿名文本块存入向量库。

```text
agri://resources/
└── rice/
    ├── .abstract.md                       # L0：知识库范围、关键主题与快速相关性判断
    ├── .overview.md                       # L1：目录、文档摘要、数据集与主要字段概览
    ├── experiments/
    │   └── 2025_early_rice_trial/
    │       ├── .abstract.md               # 试验目的、地点、年份、品种与关键结论
    │       ├── .overview.md               # 试验设计、处理组、指标与工作表目录
    │       ├── manifest.json              # 来源、更新时间、版本、权限与文件元数据
    │       ├── raw/
    │       │   └── yield_trial.xlsx       # 原始文件
    │       ├── sheets/
    │       │   ├── treatment.md           # 工作表摘要、字段说明与样例
    │       │   └── yield.md
    │       └── chunks/                    # 现有 L1/L2/L3 分块及其溯源关系
    └── regulations/
        └── rice_fertilization_guideline/
```

资源目录层与现有的分块层级职责不同：前者解决“有什么资料、资料讲什么、谁可以访问、哪个版本有效”的导航与治理问题；后者继续负责混合检索、Auto-merging、Rerank 和引用定位。两层结合后，Agent 可先从轻量摘要判断资源是否相关，再按需深入到目录、原文件、工作表或细粒度证据块。

### 三层去重与版本关系

文件化资源库需要把“同一份资料被多次上传”与“内容相近但版本不同”区分处理。规划采用三层去重机制，并将去重范围限制在同一租户和可共享的权限域内，避免因复用索引而跨越访问边界：

| 层级 | 识别方式 | 处理方式 |
| --- | --- | --- |
| 文件级精确去重 | 上传时流式计算 `raw_file_sha256 = SHA256(原始文件字节)`；唯一约束为 `tenant_id + raw_file_sha256` | 完全相同的文件复用已有解析、索引与向量结果，不重复建库。 |
| 内容级精确去重 | 解析、清洗后计算 `content_sha256 = SHA256(normalized_text)` | 识别“同一规程的 PDF 与 Word”等跨格式重复；保留不同来源、文件名与权限，而非简单物理删除。 |
| 近似重复检测 | SimHash、MinHash + LSH、文档摘要向量相似度，以及分块指纹重合率 | 超过阈值标记为“疑似重复”，再由业务规则决定合并、建立版本关系或并存。 |

内容级重复不会直接丢弃文件。未来资源模型会以 `canonical_document_id` 指向规范文档，以 `duplicate_of` 记录重复关系，并通过 `source_aliases` 保留每一次上传的来源、文件名和业务归属。这样既能节省重复索引成本，也不会丢失农业数据的采集渠道、区域权限和审计信息。

在分块层，规划计算 `chunk_hash = SHA256(normalized_chunk_text)`。当租户、权限域、分块策略及 Embedding 版本一致时，相同 Chunk 仅保存一份向量，其余文档保留对该证据块的引用与溯源关系；权限或模型版本变化时则隔离存储，确保检索结果始终符合授权范围。

### 规划中的资源数据模型

`documents` 主表将承载文件、内容、农业业务元数据和索引状态：

| 字段组 | 规划字段 |
| --- | --- |
| 标识与归属 | `document_id`、`tenant_id`、`knowledge_base_id`、`filename`、`source_uri` |
| 去重与关系 | `raw_file_sha256`、`content_sha256`、`canonical_document_id`、`duplicate_of`、`source_aliases` |
| 内容描述 | `title`、`document_summary`、`tags`、`document_type`、`language` |
| 农业语义 | `region`、`crop`、`effective_date`、`version` |
| 治理与索引 | `acl_scope`、`status`、`parser_version`、`embedding_version`、`indexed_at` |

分块记录除 `document_id` 外，还将保留 `section_title`、`section_path`、`chunk_hash`、`section_summary` 与 `metadata_json`。这些字段让系统能够先按区域、作物、资料类型、时效性和权限做元数据预过滤；再以摘要索引召回候选资源；最后由 L3 原文分块完成事实检索、精排和可追溯引用。

计划中的查询路径如下：

```mermaid
flowchart LR
    accTitle: 文件化农业上下文库的未来查询路径
    accDescr: Agent 先根据摘要筛选农业资源，再读取目录，按需加载原文、工作表或已有分块，最后选择 RAG 或 Text-to-SQL 并生成带引用的回答。
    user_question[用户问题] --> resource_abstract[L0 资源摘要筛选]
    resource_abstract --> resource_overview[L1 目录与概览]
    resource_overview --> on_demand_content[按需加载原文、工作表或 L3 证据块]
    on_demand_content --> answer_route[RAG 或 Text-to-SQL]
    answer_route --> cited_answer[带来源与溯源的回答]
```

这一方向将优先服务水稻农业资料：试验报告可呈现地点、季节、品种和处理组摘要；政策与农艺规程可呈现目录和适用区域；Excel 可进一步暴露 Sheet、字段和指标口径。由此可以形成“文章问答 + 表格查询”的统一入口，并保留从回答回溯至资源、文件和具体分块的证据链。

后续拟逐步实现：

- 文档、试验和工作表的目录浏览、摘要生成与来源追溯。
- `manifest` 驱动的版本、更新时间和访问权限管理。
- 文件 Hash、内容 Hash 与近似重复检测协同运行，复用索引但保留来源和版本关系。
- Excel 的 Sheet / 字段资源化，并与 Text-to-SQL 查询链路衔接。
- 检索阶段先读摘要和概览、再按需取数，降低无关上下文进入模型的比例。

[^1]: Volcengine. [OpenViking](https://github.com/volcengine/OpenViking)：面向 Agent 的开源上下文数据库，采用文件系统式资源组织与分层上下文加载。

## API 概览

| 模块 | 主要接口 |
| --- | --- |
| 鉴权 | `POST /auth/register`、`POST /auth/login`、`GET /auth/me` |
| 对话 | `POST /chat`、`POST /chat/stream` |
| 会话 | `GET /sessions`、`GET /sessions/{session_id}`、`DELETE /sessions/{session_id}` |
| 文档（管理员） | `GET /documents`、`POST /documents/upload/async`、`DELETE /documents/delete/async/{filename}` |
| 分块浏览（管理员） | `GET /documents/{filename}/chunks` |

完整接口以运行中的 `/docs` 为准。

## 安全与数据说明

- `.env` 中的 API Key、JWT 密钥和管理员邀请码不得提交到 Git。
- 修改 `AGENTS.md` 可以调整知识库业务范围与路由偏好；它是可审阅的领域配置，不应存放密钥或私密信息。
- 文档正文是否会被发送到外部服务，取决于模型端点和网页搜索配置；本地 Embedding 与 Reranker 不会主动向外部服务提交文本。

---

欢迎提出 Issue 或提交 PR。
