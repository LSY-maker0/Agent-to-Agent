import asyncio
import uvicorn
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.apps import A2AStarletteApplication
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from src.executor.adapter import SimpleAgentExecutor

# 导入你的执行器
from src.agents.flight_search_agent import FlightSearchAgent 
from src.agents.write_file_agent import WriteFileAgent 

# 把所有要启动的服务当成字典，塞进列表里
AGENT_REGISTRY = [
    {
        "name": "航班查询助手",
        "port": 8000,
        "description": "负责查询航班信息",
        "skills": [
            AgentSkill(id='flight_search', name='查航班', description='查询航班信息', tags=['航班'])
        ],
        "executor": SimpleAgentExecutor(FlightSearchAgent())
    },
    {
        "name": "文件写入助手",
        "port": 8001,
        "description": "负责将内容写入本地文件",
        "skills": [
            AgentSkill(id='write_file', name='写文件', description='写入文件', tags=['文件'])
        ],
        "executor": SimpleAgentExecutor(WriteFileAgent()) 
    },
]

def create_app(config: dict):
    """工厂函数：吃进一个字典配置，吐出一个 ASGI 应用"""
    agent_card = AgentCard(
        name=config["name"],
        version='1.0.0',
        description=config["description"],
        capabilities=AgentCapabilities(streaming=False),
        url=f'http://localhost:{config["port"]}',
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        skills=config["skills"]
    )
    # 实例化对应的执行器
    executor = config["executor"]
    handler = DefaultRequestHandler(agent_executor=executor, task_store=InMemoryTaskStore())
    return A2AStarletteApplication(agent_card=agent_card, http_handler=handler).build()


async def run_a2a_server():
    servers = []
    
    # 🌟 核心循环：遍历列表，动态生成所有服务
    for config in AGENT_REGISTRY:
        app = create_app(config)
        server = uvicorn.Server(uvicorn.Config(app=app, host="0.0.0.0", port=config["port"]))
        servers.append(server)
        print(f"🟢 已注册 [{config['name']}] -> http://localhost:{config['port']}")

    print("\n🚀 正在并发启动所有服务...\n")
    # 并发启动它们
    await asyncio.gather(*[server.serve() for server in servers])


if __name__ == "__main__":
    try:
        asyncio.run(run_a2a_server())
    except KeyboardInterrupt:
        print("\n🛑 所有服务已停止")
