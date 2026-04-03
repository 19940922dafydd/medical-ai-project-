# 🏥 医疗问答智能体 (Medical Q&A Agent)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0-green.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2.20-orange.svg)](https://langchain-ai.github.io/langgraph/)

本项目是一款面向医疗场景的生产级问答系统，采用 **LangGraph** 多专家协同架构，深度集成 **向量库 (ChromaDB)** 与 **知识图谱 (Neo4j)**，实现精准、可溯源的医疗知识服务。

---

## 🌟 核心特性

- 🛡️ **多专家智能路由**: 自动识别用户意图，精准分发至「导诊后台」、「药理专家」或「辅助诊断」节点。
- 🔍 **混合检索 (Hybrid RAG)**: 结合向量语义搜索与图谱拓扑路径，显著降低大模型（LLM）的幻觉。
- 🌲 **分层知识管理**: 支持 L1/L2/L3 级目录体系的医疗文献灌库，实现知识的精细化治理。
- ⚙️ **数据飞轮 (HITL)**: 集成反馈回路，捕获 Bad Case 并通过人工研判（Human-In-The-Loop）持续优化。
- 💎 **企业级管理后台**: 基于 Streamlit 打造的火山引擎（Volcengine）风格 UI，提供全链路白盒联调与监控。

---

## 🛠️ 技术栈

| 维度 | 技术选型 | 备注 |
| :--- | :--- | :--- |
| **逻辑核心** | Python 3.10+, LangChain, LangGraph | 基于图驱动的 Reasoning 链条 |
| **推断后端** | Ollama (Qwen2.5 7B) | 本地化部署，保障数据隐私 |
| **API 服务** | FastAPI | 高性能异步处理架构 |
| **存储层** | ChromaDB, Neo4j, MySQL | 向量、图、关系型三位一体 |
| **管理前台** | Streamlit | 低代码、高性能管理界面 |
| **测试框架** | Pytest | 覆盖 API、Agent Unit 及逻辑回归 |

---

## 📂 项目目录结构

```text
.
├── backend/               # FastAPI 服务及 LangGraph 核心逻辑
│   ├── agent.py           # 智能体工作流定义 (Experts, Router)
│   ├── main.py            # API 入口与流式输出接口
│   └── metrics.py         # 系统运行指标记录
├── frontend/              # Web 界面 (Streamlit)
│   ├── admin_app.py       # 企业级管理后台主程序
│   ├── client_app.py      # 用户测试客户端
│   └── components/        # 功能组件 (知识库、意图、图谱管理等)
├── data/                  # 数据处理层
│   ├── mysql_mgr.py       # 数据库/连接池驱动
│   └── graph_store/       # Neo4j 处理逻辑
├── config/                # 环境、模型与数据库配置
├── prompts/               # 针对各专家的系统提示词 (Prompts)
├── tests/                 # 自动化测试脚本 (API/场景测试)
├── run.sh                 # 一键全启动脚本 (Backend + Frontend)
└── requirements.txt       # 项目依赖清单
```

---

## 🚀 快速开始

### 1. 环境准备
确保已安装 Python 3.10+，并启动 Ollama 以及配套数据库（MySQL, Chroma, Neo4j）。

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置环境变量
在根目录创建 `.env` 文件，并参考 `config/settings.py` 进行如下配置：
```env
LLM_MODEL=qwen2.5:7b
NEO4J_URI=bolt://localhost:7687
NEO4J_PASSWORD=your_password
MYSQL_HOST=localhost
API_URL=http://localhost:8000
```

### 4. 启动服务
使用内置脚本一键启动：
```bash
./run.sh
```

---

## 📜 开发规范

本项目遵循严格的工程化准则：

### 1. 命名与代码风格
- **变量/函数**: 采用 `camelCase` 小驼峰命名。
- **类名/组件**: 采用 `PascalCase` 大驼峰命名。
- **常量**: 采用 `UPPER_SNAKE_CASE` 全大写下划线命名。
- **后端分层**: 遵循 `api (请求) -> service (逻辑) -> repository (访问)` 的解耦原则，禁止在 API 层直操数据库。

### 2. 注释准则 (JSDoc/Docstring)
注释应解释「**为什么**」而非「是什么」。复杂的业务逻辑、由于合规或边界条件引入的特殊处理必须添加详细注释。

### 3. 安全与质量
- **参数校验**: 所有外部输入必须经过 Pydantic 模型严格校验。
- **异常处理**: 禁止使用裸 `except`，需捕获特定 `MedicalAgentError` 并记录 Metrics。
- **敏感数据**: 禁止在前端存储密钥，所有敏感逻辑需在 Service 层完成权限验证。

---

## 🔄 数据迭代流程
1. **数据灌库**: 通过管理后台通过 L1-L3 目录上传文献。
2. **知识洗练**: 系统自动进行 Chunking、向量化及三元组提取。
3. **反馈闭环**: 诊断如有误，用户可通过「Bad Case」功能反馈，管理员在「安全溯源库」中定位冲突节点并校准。

---

Powered by **Antigravity**. 🏥 企业级医疗 AI 基础设施。
