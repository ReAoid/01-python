"""
Ollama LLM 实现类。
支持调用本地 Ollama 服务。
"""
import logging
from typing import List, Generator, Dict, AsyncGenerator, Optional
import httpx
from backend.core.message import Message
from backend.core.llm import Llm
from backend.config import settings

logger = logging.getLogger(__name__)


class OllamaLlm(Llm):
    """
    Ollama LLM 实现类。
    支持调用本地 Ollama 服务。
    """

    def __init__(
        self, 
        model: str = None, 
        base_url: str = None, 
        timeout: int = None
    ):
        """
        初始化 Ollama 客户端。优先使用传入参数，如果未提供，则从配置加载。
        
        Args:
            model: 模型名称 (如 llama3, qwen2 等)
            base_url: Ollama 服务地址 (默认 http://localhost:11434)
            timeout: 超时时间(秒)
        """
        self.model = model or settings.chat_llm.model
        self.base_url = (base_url or settings.chat_llm.api.base_url or "http://localhost:11434").rstrip('/')
        self.timeout = timeout or settings.chat_llm.api.timeout or 120

        if not self.model:
            error_msg = "❌ 配置错误: 缺少必要的 Ollama 模型配置！"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(f"Ollama LLM 初始化: model={self.model}, base_url={self.base_url}")

    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, str]]:
        """
        将 Message 对象列表转换为 Ollama API 格式的字典列表。
        """
        return [{"role": msg.role, "content": msg.content} for msg in messages]

    def generate(self, messages: List[Message], **kwargs) -> Message:
        """
        非流式生成响应,返回完整的消息。
        """
        default_temp = settings.chat_llm.temperature
        temperature = kwargs.get("temperature", default_temp)

        logger.info(f"正在调用 Ollama {self.model} 模型(非流式)...")

        try:
            api_messages = self._convert_messages(messages)
            
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": api_messages,
                        "think": False,
                        "stream": False,
                        "options": {
                            "temperature": temperature,
                            **{k: v for k, v in kwargs.items() if k not in ["temperature"]}
                        }
                    }
                )
                response.raise_for_status()
                result = response.json()

            content = result.get("message", {}).get("content", "")
            logger.info(f"Ollama 响应成功,生成了 {len(content)} 个字符")

            return Message(role="assistant", content=content)

        except Exception as e:
            logger.error(f"调用 Ollama API 时发生错误: {e}")
            raise

    async def agenerate(self, messages: List[Message], **kwargs) -> Message:
        """
        异步非流式生成响应。
        """
        default_temp = settings.chat_llm.temperature
        temperature = kwargs.get("temperature", default_temp)

        logger.info(f"正在异步调用 Ollama {self.model} 模型(非流式)...")

        try:
            api_messages = self._convert_messages(messages)
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": api_messages,
                        "think": False,
                        "stream": False,
                        "options": {
                            "temperature": temperature,
                            **{k: v for k, v in kwargs.items() if k not in ["temperature"]}
                        }
                    }
                )
                response.raise_for_status()
                result = response.json()

            content = result.get("message", {}).get("content", "")
            logger.info(f"Ollama 异步响应成功,生成了 {len(content)} 个字符")

            return Message(role="assistant", content=content)

        except Exception as e:
            logger.error(f"调用 Ollama API 时发生错误: {e}")
            raise

    def stream(self, messages: List[Message], **kwargs) -> Generator[str, None, None]:
        """
        流式生成响应。
        """
        default_temp = settings.chat_llm.temperature
        temperature = kwargs.get("temperature", default_temp)

        logger.info(f"正在调用 Ollama {self.model} 模型(流式)...")

        try:
            api_messages = self._convert_messages(messages)
            
            with httpx.Client(timeout=self.timeout) as client:
                with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": api_messages,
                        "think": False,
                        "stream": True,
                        "options": {
                            "temperature": temperature,
                            **{k: v for k, v in kwargs.items() if k not in ["temperature"]}
                        }
                    }
                ) as response:
                    response.raise_for_status()
                    logger.info("Ollama 开始流式响应")
                    
                    import json
                    for line in response.iter_lines():
                        if line:
                            try:
                                chunk_data = json.loads(line)
                                content = chunk_data.get("message", {}).get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue

            logger.info("流式响应完成")

        except Exception as e:
            logger.error(f"调用 Ollama API 时发生错误: {e}")
            raise

    async def astream(self, messages: List[Message], **kwargs) -> AsyncGenerator[str, None]:
        """
        异步流式生成响应。
        """
        default_temp = settings.chat_llm.temperature
        temperature = kwargs.get("temperature", default_temp)

        logger.info(f"正在异步调用 Ollama {self.model} 模型(流式)...")

        try:
            api_messages = self._convert_messages(messages)
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": api_messages,
                        "think": False,
                        "stream": True,
                        "options": {
                            "temperature": temperature,
                            **{k: v for k, v in kwargs.items() if k not in ["temperature"]}
                        }
                    }
                ) as response:
                    response.raise_for_status()
                    logger.info("Ollama 开始异步流式响应")
                    
                    import json
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                chunk_data = json.loads(line)
                                content = chunk_data.get("message", {}).get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue

            logger.info("异步流式响应完成")

        except Exception as e:
            logger.error(f"调用 Ollama API 时发生错误: {e}")
            raise
