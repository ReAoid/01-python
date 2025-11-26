from typing import Dict
from backend.core.agent.agent import Agent
from backend.core.logger.log_system import logger

class AgentManager:
    def __init__(self):
        self.agents: Dict[str, Agent] = {}

    def register_agent(self, name: str, agent: Agent):
        """注册一个 agent 到管理器。"""
        self.agents[name] = agent
        logger.info(f"已注册 agent: {name}")

    def dispatch(self, agent_name: str, task: str) -> str:
        """分发任务给指定的 agent。"""
        agent = self.agents.get(agent_name)
        if not agent:
            raise ValueError(f"未找到 agent: {agent_name}")
        
        logger.info(f"分发任务给 {agent_name}: {task}")
        return agent.run(task)

    def broadcast(self, task: str) -> Dict[str, str]:
        """将同一任务广播给所有 agent 并收集结果。"""
        results = {}
        for name, agent in self.agents.items():
            results[name] = agent.run(task)
        return results
