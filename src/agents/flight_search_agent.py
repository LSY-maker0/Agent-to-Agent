import json
import asyncio
import os
import inspect
from typing import Dict, Callable, List
from openai import AsyncOpenAI
from dotenv import load_dotenv  
load_dotenv()   

DEFAULT_MODEL = os.getenv("ANTHROPIC_CHAT_MODEL")
DEFAULT_BASE_URL = os.getenv("ANTHROPIC_BASE_URL")
DEFAULT_API_KEY = os.getenv("ANTHROPIC_API_KEY")

class Tool:
    def __init__(self, func: Callable, description: str, parameters: dict):
        self.func = func
        self.description = description
        self.parameters = parameters

def search_flights(destination: str) -> str:
    """查询航班"""
    if destination == "上海":
        return json.dumps([
            {"flight_id": "CA1234", "time": "08:00-10:30", "status": "有票"},
            {"flight_id": "MU5678", "time": "14:00-16:20", "status": "有票"}
        ], ensure_ascii=False)
    return json.dumps([{"flight_id": "None", "time": "无", "status": "无航班"}], ensure_ascii=False)

def get_ticket_price(flight_id: str) -> str:
    """查询价格"""
    prices = {
        "CA1234": 850,
        "MU5678": 620
    }
    price = prices.get(flight_id, 0)
    return f"航班 {flight_id} 的当前票价为 {price} 元。"

TOOLS = [
    Tool(
        func=search_flights,
        description="根据目的地查询可用航班列表，返回航班号和时间",
        parameters={
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "目的地城市，例如：上海、北京"}
            },
            "required": ["destination"] 
        }
    ),
    Tool(
        func=get_ticket_price,
        description="根据航班号查询当前票价",
        parameters={
            "type": "object",
            "properties": {
                "flight_id": {"type": "string", "description": "航班号"}
            },
            "required": ["flight_id"]
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
    
class FlightSearchAgent:
    """一个Agent，能够处理查询航班和票价的请求"""
    
    def __init__(self, client = None, model = None, tools = None):
        self.client = client or  AsyncOpenAI(
            api_key = DEFAULT_API_KEY,  
            base_url = DEFAULT_BASE_URL,
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
    agent = FlightSearchAgent()
    result = await agent.run("帮我查下去上海的机票，推荐最便宜的")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())