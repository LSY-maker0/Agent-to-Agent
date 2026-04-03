import os
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import TaskArtifactUpdateEvent, TaskState, TaskStatus, TaskStatusUpdateEvent
from a2a.utils.artifact import new_text_artifact
from a2a.utils.task import new_task

class SimpleAgentExecutor(AgentExecutor):
    """极简执行器：与具体智能体解耦，支持外部传入"""

    def __init__(self, agent):
        # 像插头一样，把智能体插进来
        self.agent = agent

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        # 1. 初始化 A2A 任务
        task = context.current_task or new_task(context.message)
        await event_queue.enqueue_event(task)
        
        # 2. 提取用户问题
        query = ""
        if context.message and context.message.parts:
            query = context.message.parts[0].root.text

        # 3. 调用智能体，拿到完整结果
        final_text = await self.agent.run(query)

        # 4. 把完整结果一次性作为 Artifact 发送出去
        await event_queue.enqueue_event(
            TaskArtifactUpdateEvent(
                task_id=task.id,
                context_id=task.context_id,
                artifact=new_text_artifact(name='result', text=final_text),
            )
        )

        # 5. 告诉 A2A 协议，任务完成了
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task.id,
                context_id=task.context_id,
                status=TaskStatus(state=TaskState.completed),
                final=True
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        pass
