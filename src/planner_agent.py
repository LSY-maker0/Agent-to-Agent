import json
import asyncio
import os
import inspect
from typing import Dict, Callable, List
from openai import AsyncOpenAI
from dotenv import load_dotenv  
import httpx
from uuid import uuid4

# A2A 依赖
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.client import A2ACardResolver
from a2a.server.events import EventQueue
from a2a.client.client_factory import ClientFactory
from a2a.client.client import ClientConfig
from a2a.types import Message, Part, Role

load_dotenv()   

DEFAULT_MODEL = os.environ["DASHSCOPE_CHAT_MODEL"]
DEFAULT_BASE_URL = os.environ["DASHSCOPE_HOST"]
DEFAULT_API_KEY = os.environ["DASHSCOPE_API_KEY"]

OTHER_AGENT_URLS = ['http://localhost:8000','http://localhost:8001'] 

class Tool:
    def __init__(self, func: Callable, description: str, parameters: dict):
        self.func = func
        self.description = description
        self.parameters = parameters

LOCAL_TOOLS = []

async def call_remote_agent(agent_client, query_text: str) -> str:
    """通用的 A2A 请求发送函数"""
    try:
        message = Message(
            role=Role.user,
            parts=[Part(text=query_text)],
            message_id=uuid4().hex,
            context_id=uuid4().hex,
        )
        response = agent_client.send_message(message)
        result_text = ""
        async for task, update in response:
            if task and task.artifacts:
                for artifact in task.artifacts:
                    for part in artifact.parts:
                        result_text += part.root.text
        return result_text or "远程 Agent 未返回有效内容"
    except Exception as e:
        return f"调用远程 Agent 失败: {str(e)}"

class ToolRegistry:
    def __init__(self):
        self._tools = {}       # {工具名: 执行函数}
        self._schemas = []     # 给 LLM 看的 JSON 格式

    def add_tool(self, tool: Tool):
        """添加本地工具"""
        self._tools[tool.func.__name__] = tool.func
        self._schemas.append({
            "type": "function", 
            "function": {
                "name": tool.func.__name__, 
                "description": tool.description, 
                "parameters": tool.parameters
            }
        })

    def add_remote_tool(self, skill_id: str, skill_name: str, skill_desc: str, agent_client):
        """把远程 A2A 技能包装成工具加进来"""
        self._tools[skill_id] = lambda query_text, client=agent_client: call_remote_agent(client, query_text)
        self._schemas.append({
            "type": "function",
            "function": {
                "name": skill_id,
                "description": f"[远程A2A能力] {skill_desc}",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": f"传递给 {skill_name} 的查询内容"}},
                    "required": ["query"]
                }
            }
        })

    def get_schemas(self): 
        return self._schemas

    async def execute(self, name: str, arguments: str) -> str:
        func = self._tools.get(name)
        if not func:
            return f"未知工具: {name}"
        args = json.loads(arguments)
        print(f"执行工具: {name}，参数: {args}")
        result =await func(args["query"])
        print(f"工具 {name} 执行结果: {result}")
        return result

class PlannerAgent(AgentExecutor):
    def __init__(self):
        self.client = AsyncOpenAI(api_key=DEFAULT_API_KEY, base_url=DEFAULT_BASE_URL)
        self.model = DEFAULT_MODEL
        self.tools = ToolRegistry()
        self._initialized = False

    async def _discover_remote_agents(self):
        """发现其他 A2A Agent 并把它们的技能变成自己的工具"""
        async with httpx.AsyncClient(timeout=30) as httpx_client:
            for url in OTHER_AGENT_URLS:
                try:
                    resolver = A2ACardResolver(httpx_client=httpx_client, base_url=url)
                    card = await resolver.get_agent_card()
                    print(f"✅ 发现远程 Agent: {card.name} @ {url}")
                    
                    client_factory = ClientFactory(config=ClientConfig(streaming=False))
                    agent_client = client_factory.create(card)
                    
                    for skill in card.skills:
                        self.tools.add_remote_tool(skill.id, skill.name, skill.description, agent_client)
                except Exception as e:
                    print(f"❌ 无法连接到远程 Agent {url}: {e}")

    async def _init_tools(self):
        """初始化工具（只执行一次）"""
        if not self._initialized:
            # 1. 加入本地工具
            for tool in LOCAL_TOOLS:
                self.tools.add_tool(tool)
            # 2. 发现并加入远程 A2A 工具
            await self._discover_remote_agents()
            self._initialized = True

    async def run(self, query: str) -> str:
        await self._init_tools() # 确保工具已加载
        
        messages = [{"role": "system", "content": "你是一个全能助手，可以调用远程Agent查询信息。请用中文回答。"}, {"role": "user", "content": query}]
        while True:
            resp = await self.client.chat.completions.create(
                messages=messages, model=self.model, tools=self.tools.get_schemas()
            )
            msg = resp.choices[0].message
            
            if msg.tool_calls:

                messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
                for tc in msg.tool_calls:
                    print("初始消息:", tc)
                    result = await self.tools.execute(tc.function.name, tc.function.arguments) # 有问题
                    messages.append({"role": "tool", "name": tc.function.name, "content": result})
            else:
                return msg.content or ""

    async def execute(self, context: RequestContext) -> None:
        user_text = context.message.parts[0].root.text if context.message and context.message.parts else ""
        final_result = await self.run(user_text)
        await context.emit_task_complete([{"type": "text", "text": final_result}])

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        pass

async def run_a2a_client():
    agent = PlannerAgent()
    result = await agent.run("帮我查一下去上海的航班，并把结果写入到 flight_result.md 里")
    # result = await agent.run("帮我查一下去上海的航班")
    # result = await agent.run("帮我写个hello world到.md")
    print(result)

if __name__ == "__main__":
    asyncio.run(run_a2a_client())
