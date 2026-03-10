import os
import json
from typing import List, Generator, Dict, AsyncGenerator, Optional, Any, Union
from openai import OpenAI, AsyncOpenAI
from openai.types.chat import ChatCompletionMessage, ChatCompletionMessageToolCall
import logging
from backend.core.message import Message
from backend.core.llm import Llm
from backend.config import settings
from backend.config.prompts import SYSTEM_PROMPT_CODE_ASSISTANT

logger = logging.getLogger(__name__)


class ToolCallResult:
    """工具调用结果"""
    def __init__(
        self,
        tool_calls: List[ChatCompletionMessageToolCall] = None,
        content: str = None,
        is_tool_call: bool = False
    ):
        self.tool_calls = tool_calls or []
        self.content = content or ""
        self.is_tool_call = is_tool_call
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "is_tool_call": self.is_tool_call,
            "content": self.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in self.tool_calls
            ] if self.tool_calls else []
        }

class OpenaiLlm(Llm):
    """
    OpenAI LLM 实现类。
    支持调用任何兼容 OpenAI 接口的服务。
    """

    def __init__(self, model: str = None, api_key: str = None, base_url: str = None, timeout: int = None):
        """
        初始化客户端。优先使用传入参数，如果未提供，则从配置加载。
        
        Args:
            model: 模型ID
            api_key: API 密钥
            base_url: API 服务地址
            timeout: 超时时间(秒)
        """
        self.model = model or settings.chat_llm.model
        api_key = api_key or settings.chat_llm.api.key
        base_url = base_url or settings.chat_llm.api.base_url
        timeout = timeout or settings.chat_llm.api.timeout

        if not all([self.model, api_key, base_url]):
            error_msg = (
                "❌ 配置错误: 缺少必要的 LLM 配置！"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        self.async_client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    def _convert_messages(self, messages: List[Union[Message, Dict]]) -> List[Dict[str, Any]]:
        """
        将 Message 对象列表转换为 OpenAI API 格式的字典列表。
        支持普通消息和工具调用消息。
        
        Args:
            messages: Message 对象列表或字典列表
            
        Returns:
            List[Dict[str, Any]]: OpenAI API 格式的消息列表
        """
        result = []
        for msg in messages:
            if isinstance(msg, dict):
                result.append(msg)
            elif hasattr(msg, 'tool_calls') and msg.tool_calls:
                # Assistant 消息带有工具调用
                result.append({
                    "role": msg.role,
                    "content": msg.content or "",
                    "tool_calls": msg.tool_calls
                })
            elif msg.role == "tool" and hasattr(msg, 'tool_call_id'):
                # 工具响应消息
                result.append({
                    "role": "tool",
                    "content": msg.content,
                    "tool_call_id": msg.tool_call_id
                })
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result

    def generate(self, messages: List[Message], **kwargs) -> Message:
        """
        非流式生成响应,返回完整的消息。
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数(如 temperature, max_tokens 等)
            
        Returns:
            Message: 完整的响应消息
        """
        default_temp = settings.chat_llm.temperature
        temperature = kwargs.get("temperature", default_temp)

        logger.info(f"正在调用 {self.model} 模型(非流式)...")

        try:
            api_messages = self._convert_messages(messages)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=api_messages,
                temperature=temperature,
                stream=False,
                **{k: v for k, v in kwargs.items() if k not in ["temperature"]}
            )

            content = response.choices[0].message.content
            logger.info(f"大语言模型响应成功,生成了 {len(content)} 个字符")

            return Message(role="assistant", content=content)

        except Exception as e:
            logger.error(f"调用LLM API时发生错误: {e}")
            raise

    def generate_with_tools(
        self, 
        messages: List[Union[Message, Dict]], 
        tools: List[Dict[str, Any]] = None,
        tool_choice: str = "auto",
        **kwargs
    ) -> ToolCallResult:
        """
        支持工具调用的非流式生成。
        
        Args:
            messages: 消息列表
            tools: 工具定义列表（OpenAI function calling 格式）
            tool_choice: 工具选择策略 ("auto", "none", "required")
            **kwargs: 其他参数
            
        Returns:
            ToolCallResult: 包含工具调用或文本响应
        """
        default_temp = settings.chat_llm.temperature
        temperature = kwargs.get("temperature", default_temp)

        logger.info(f"正在调用 {self.model} 模型(带工具)...")

        try:
            api_messages = self._convert_messages(messages)
            
            # 构建请求参数
            request_params = {
                "model": self.model,
                "messages": api_messages,
                "temperature": temperature,
                "stream": False,
            }
            
            # 如果有工具，添加工具参数
            if tools:
                request_params["tools"] = tools
                request_params["tool_choice"] = tool_choice
            
            response = self.client.chat.completions.create(**request_params)
            
            message = response.choices[0].message
            
            # 检查是否有工具调用
            if message.tool_calls:
                logger.info(f"AI 请求调用 {len(message.tool_calls)} 个工具")
                return ToolCallResult(
                    tool_calls=message.tool_calls,
                    content=message.content or "",
                    is_tool_call=True
                )
            else:
                content = message.content or ""
                logger.info(f"大语言模型响应成功,生成了 {len(content)} 个字符")
                return ToolCallResult(
                    content=content,
                    is_tool_call=False
                )

        except Exception as e:
            logger.error(f"调用LLM API时发生错误: {e}")
            raise

    async def agenerate_with_tools(
        self, 
        messages: List[Union[Message, Dict]], 
        tools: List[Dict[str, Any]] = None,
        tool_choice: str = "auto",
        **kwargs
    ) -> ToolCallResult:
        """
        支持工具调用的异步非流式生成。
        
        Args:
            messages: 消息列表
            tools: 工具定义列表（OpenAI function calling 格式）
            tool_choice: 工具选择策略 ("auto", "none", "required")
            **kwargs: 其他参数
            
        Returns:
            ToolCallResult: 包含工具调用或文本响应
        """
        default_temp = settings.chat_llm.temperature
        temperature = kwargs.get("temperature", default_temp)

        logger.info(f"正在异步调用 {self.model} 模型(带工具)...")

        try:
            api_messages = self._convert_messages(messages)
            
            # 构建请求参数
            request_params = {
                "model": self.model,
                "messages": api_messages,
                "temperature": temperature,
                "stream": False,
            }
            
            # 如果有工具，添加工具参数
            if tools:
                request_params["tools"] = tools
                request_params["tool_choice"] = tool_choice
            
            response = await self.async_client.chat.completions.create(**request_params)
            
            message = response.choices[0].message
            
            # 检查是否有工具调用
            if message.tool_calls:
                logger.info(f"AI 请求调用 {len(message.tool_calls)} 个工具")
                return ToolCallResult(
                    tool_calls=message.tool_calls,
                    content=message.content or "",
                    is_tool_call=True
                )
            else:
                content = message.content or ""
                logger.info(f"大语言模型异步响应成功,生成了 {len(content)} 个字符")
                return ToolCallResult(
                    content=content,
                    is_tool_call=False
                )

        except Exception as e:
            logger.error(f"调用LLM API时发生错误: {e}")
            raise

    async def agenerate(self, messages: List[Message], **kwargs) -> Message:
        """
        异步非流式生成响应。
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数(如 temperature, max_tokens 等)
            
        Returns:
            Message: 完整的响应消息
        """
        default_temp = settings.chat_llm.temperature
        temperature = kwargs.get("temperature", default_temp)

        logger.info(f"正在异步调用 {self.model} 模型(非流式)...")

        try:
            api_messages = self._convert_messages(messages)
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=api_messages,
                temperature=temperature,
                stream=False,
                **{k: v for k, v in kwargs.items() if k not in ["temperature"]}
            )

            content = response.choices[0].message.content
            logger.info(f"大语言模型异步响应成功,生成了 {len(content)} 个字符")

            return Message(role="assistant", content=content)

        except Exception as e:
            logger.error(f"调用LLM API时发生错误: {e}")
            raise

    def stream(self, messages: List[Message], **kwargs) -> Generator[str, None, None]:
        """
        流式生成响应。
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数(如 temperature, max_tokens 等)
            
        Yields:
            str: 流式生成的文本片段
        """
        default_temp = settings.chat_llm.temperature
        temperature = kwargs.get("temperature", default_temp)

        logger.info(f"正在调用 {self.model} 模型(流式)...")

        try:
            api_messages = self._convert_messages(messages)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=api_messages,
                temperature=temperature,
                stream=True,
                **{k: v for k, v in kwargs.items() if k not in ["temperature"]}
            )

            logger.info("大语言模型开始流式响应")
            for chunk in response:
                content = chunk.choices[0].delta.content or ""
                if content:
                    yield content

            logger.info("流式响应完成")

        except Exception as e:
            logger.error(f"调用LLM API时发生错误: {e}")
            raise

    async def astream(self, messages: List[Message], **kwargs) -> AsyncGenerator[str, None]:
        """
        异步流式生成响应。
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数(如 temperature, max_tokens 等)
            
        Yields:
            str: 流式生成的文本片段
        """
        default_temp = settings.chat_llm.temperature
        temperature = kwargs.get("temperature", default_temp)

        logger.info(f"正在异步调用 {self.model} 模型(流式)...")

        try:
            api_messages = self._convert_messages(messages)
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=api_messages,
                temperature=temperature,
                stream=True,
                **{k: v for k, v in kwargs.items() if k not in ["temperature"]}
            )

            logger.info("大语言模型开始异步流式响应")
            async for chunk in response:
                content = chunk.choices[0].delta.content or ""
                if content:
                    yield content

            logger.info("异步流式响应完成")

        except Exception as e:
            logger.error(f"调用LLM API时发生错误: {e}")
            raise


# --- 使用示例 ---
if __name__ == '__main__':
    try:
        from backend.core.logger import init_logging

        # 初始化日志系统
        init_logging(log_level="INFO")

        llm = OpenaiLlm()

        # 创建示例消息
        from backend.core.message import Message

        example_messages = [
            Message(role="system", content=SYSTEM_PROMPT_CODE_ASSISTANT),
            Message(role="user", content="写一个快速排序算法")
        ]

        logger.info("=== 测试非流式调用 ===")
        response = llm.generate(example_messages)
        logger.info(f"完整响应:\n{response.content}\n")

        logger.info("=== 测试流式调用 ===")
        collected_content = []
        for chunk in llm.stream(example_messages):
            print(chunk, end="", flush=True)
            collected_content.append(chunk)

        logger.info(f"\n流式响应收集完成,共 {len(''.join(collected_content))} 个字符")

    except ValueError as e:
        logger.error(f"配置错误: {e}")
    except Exception as e:
        logger.exception(f"发生错误: {e}")
