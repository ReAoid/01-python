import os
from typing import List, Generator, Dict
from openai import OpenAI
from loguru import logger
from backend.core.message import Message
from backend.core.llm import Llm
from backend.utils.config_manager import get_core_config


class OpenaiLlm(Llm):
    """
    OpenAI LLM 实现类。
    支持调用任何兼容 OpenAI 接口的服务。
    """

    def __init__(self, model: str = None, api_key: str = None, base_url: str = None, timeout: int = None):
        """
        初始化客户端。优先使用传入参数,如果未提供,则从配置管理器加载(支持配置文件和环境变量)。
        
        Args:
            model: 模型ID
            api_key: API密钥
            base_url: API服务地址
            timeout: 超时时间(秒)
        """
        config = get_core_config()
        
        self.model = model or config.get("LLM_MODEL_ID")
        api_key = api_key or config.get("LLM_API_KEY")
        base_url = base_url or config.get("LLM_BASE_URL")
        timeout = timeout or config.get("LLM_TIMEOUT", 60)
        
        if not all([self.model, api_key, base_url]):
            raise ValueError("模型ID、API密钥和服务地址必须被提供或在配置文件/环境变量中定义。")
        
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, str]]:
        """
        将 Message 对象列表转换为 OpenAI API 格式的字典列表。
        
        Args:
            messages: Message 对象列表
            
        Returns:
            List[Dict[str, str]]: OpenAI API 格式的消息列表
        """
        return [{"role": msg.role, "content": msg.content} for msg in messages]

    def generate(self, messages: List[Message], **kwargs) -> Message:
        """
        非流式生成响应,返回完整的消息。
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数(如 temperature, max_tokens 等)
            
        Returns:
            Message: 完整的响应消息
        """
        temperature = kwargs.get("temperature", 0)
        
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
            logger.success(f"大语言模型响应成功,生成了 {len(content)} 个字符")
            
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
        temperature = kwargs.get("temperature", 0)
        
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
            
            logger.success("大语言模型开始流式响应")
            for chunk in response:
                content = chunk.choices[0].delta.content or ""
                if content:
                    yield content
            
            logger.info("流式响应完成")
            
        except Exception as e:
            logger.error(f"调用LLM API时发生错误: {e}")
            raise


# --- 使用示例 ---
if __name__ == '__main__':
    try:
        from backend.core.logger import setup_logger
        # 移除 Config 依赖
        # from backend.core.config import Config
        
        # 初始化日志系统
        setup_logger(log_level="INFO")
        
        # 加载环境变量 (如果需要)
        from dotenv import load_dotenv
        load_dotenv()
        
        llm = OpenaiLlm()
        
        # 创建示例消息
        from backend.core.message import Message
        example_messages = [
            Message(role="system", content="You are a helpful assistant that writes Python code."),
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
