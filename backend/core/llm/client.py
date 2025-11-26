import os
from typing import List, Generator, Optional, Dict, Any
from openai import OpenAI, APIError
from dotenv import load_dotenv

from backend.core.llm.llm_interface import LLMInterface
from backend.core.memory.message import Message, AssistantMessage
from backend.core.logger.log_system import logger

load_dotenv()

class OpenAIClient(LLMInterface):
    def __init__(self, model: str = "gpt-3.5-turbo", api_key: Optional[str] = None):
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model

    def generate(self, messages: List[Message], tools: Optional[List[Dict]] = None, **kwargs) -> AssistantMessage:
        """
        非流式生成。
        """
        formatted_messages = [msg.to_dict() for msg in messages]
        
        try:
            params = {
                "model": self.model,
                "messages": formatted_messages,
                **kwargs
            }
            if tools:
                params["tools"] = tools

            logger.debug(f"调用 OpenAI，消息数量: {len(messages)}")
            response = self.client.chat.completions.create(**params)
            
            choice = response.choices[0]
            message_data = choice.message
            
            content = message_data.content
            tool_calls = message_data.tool_calls
            
            return AssistantMessage(
                content=content or "",
                tool_calls=[tc.model_dump() for tc in tool_calls] if tool_calls else None
            )

        except Exception as e:
            logger.error(f"OpenAI API 调用失败: {e}")
            raise

    def stream(self, messages: List[Message], **kwargs) -> Generator[str, None, None]:
        """
        流式生成 (仅内容)。
        """
        formatted_messages = [msg.to_dict() for msg in messages]
        
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=formatted_messages,
                stream=True,
                **kwargs
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"OpenAI 流式调用失败: {e}")
            raise
