# A2A Multi-Agent System

一个基于 A2A 框架的多智能体协作系统，包含多个专业化的智能体服务。

## 项目概述

这是一个利用 A2A SDK 构建的多智能体协作系统，实现了智能体间的发现、通信与任务编排。系统采用分布式架构，各智能体独立部署并通过标准接口协作。

### 核心组件

- **Planner Agent**: 核心调度器，负责解析用户请求、规划任务并协调其他智能体执行
- **Flight Search Agent**: 专门处理航班查询业务 (运行于端口 8000)
- **Write File Agent**: 提供文件写入功能 (运行于端口 8001)

### 主要特性

- **智能体发现**: 自动发现网络中的其他 A2A 智能体并将其能力注册为工具
- **工具调用**: 支持本地和远程工具的统一调用接口
- **ReAct 推理**: 结合推理与行动的决策机制
- **分布式部署**: 各智能体独立部署，通过 HTTP API 通信

### 文件结构

```
.
├── a2a_client.py          # 客户端入口，用于连接和调用多智能体系统
├── a2a_server.py          # 服务端入口，启动多智能体服务集群
├── pyproject.toml         # 项目依赖配置文件
├── readme.md              # 项目说明文档
├── .env                   # 环境变量配置（API密钥等）
├── .python-version        # Python 版本声明
├── src/
│   ├── planner_agent.py      # 核心调度器实现
│   ├── a2a_server.py         # 服务端主逻辑，定义多智能体注册表
│   ├── agents/
│   │   ├── flight_search_agent.py  # 航班查询智能体
│   │   └── write_file_agent.py     # 文件写入智能体
│   └── executor/
│       └── adapter.py            # 智能体执行器适配器
└── workspace/             # 工作空间目录，用于存放智能体生成的文件
```

### 技术栈

- Python 3.14+
- A2A SDK (>=0.3.25)
- OpenAI API 客户端
- Uvicorn ASGI 服务器

### 快速开始

```bash
# 启动多智能体服务集群
python a2a_server.py

# 启动客户端进行交互
python a2a_client.py
```