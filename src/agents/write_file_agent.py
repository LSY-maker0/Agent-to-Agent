import json
import asyncio
import os
import inspect
from typing import Dict, Callable, List
from openai import AsyncOpenAI
from dotenv import load_dotenv  
load_dotenv()   

# A2A 相关依赖
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.types import Message, Part, Role

DEFAULT_MODEL = os.environ["DASHSCOPE_CHAT_MODEL"]
DEFAULT_BASE_URL = os.environ["DASHSCOPE_HOST"]
DEFAULT_API_KEY = os.environ["DASHSCOPE_API_KEY"]

class Tool:
    def __init__(self, func: Callable, description: str, parameters: dict):
        self.func = func
        self.description = description
        self.parameters = parameters

def write_file(filename: str, content: str) -> str:
    """将内容写入 workspace 目录下的指定文件"""
    try:
        workspace_dir = os.path.join(os.getcwd(), "workspace")
        os.makedirs(workspace_dir, exist_ok=True)
        filepath = os.path.join(workspace_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"成功将内容写入文件：{filepath}"
    except Exception as e:
        return f"写入文件失败: {str(e)}"

TOOLS = [
    Tool(
        func=write_file,
        description="将指定的文本内容写入到本地文件中",
        parameters={
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "要写入的文件名，例如：output.txt"},
                "content": {"type": "string", "description": "要写入文件的具体文本内容"}
            },
            "required": ["filename", "content"]
        }
    )
]

class ToolRegistry:
    def __init__(self, tools: List[Tool]):
        self._tools = {t.func.__name__: t.func for t in tools}
        self._schemas = [{
            "type": "function", 
            "function": {
                "name": t.func.__name__, 
                "description": t.description, 
                "parameters": t.parameters
            }
        } for t in tools]

    def get_schemas(self): 
        return self._schemas

    async def execute(self, name: str, arguments: str) -> str:
        func = self._tools.get(name)
        if not func: 
            return f"未知工具: {name}"
        args = json.loads(arguments)
        return await func(**args) if inspect.iscoroutinefunction(func) else func(**args)
    
class WriteFileAgent:
    """一个Agent，能够处理查询航班和票价的请求"""
    
    def __init__(self, client = None, model = None, tools = None):
        self.client = client or  AsyncOpenAI(
            api_key=DEFAULT_API_KEY,  
            base_url=DEFAULT_BASE_URL,
        )
        self.model = model or DEFAULT_MODEL
        self.tools = tools or ToolRegistry(TOOLS)

    async def run(self, query: str) -> str:
        """核心方法：执行 ReAct 循环，返回最终完整结果"""
        messages = [{"role": "user", "content": query}]

        while True:
            resp = await self.client.chat.completions.create(
                messages=messages, 
                model=self.model, 
                tools=self.tools.get_schemas()
            )
            msg = resp.choices[0].message

            if msg.tool_calls:
                # 记录 LLM 的工具调用意图
                messages.append({
                    "role": "assistant", 
                    "content": msg.content or "", 
                    "tool_calls": [tc.model_dump() for tc in msg.tool_calls]
                })
                # 执行工具并记录结果
                for tc in msg.tool_calls:
                    result = await self.tools.execute(tc.function.name, tc.function.arguments)
                    messages.append({
                        "role": "tool", 
                        "name": tc.function.name, 
                        "content": result
                    })
            else:
                # 没有工具调用了，直接返回最终文本
                return msg.content or ""
            
async def main():
    agent = WriteFileAgent()
    result = await agent.run("帮我写个hello world写入到.md")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())