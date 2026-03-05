"""
LLM 服务管理模块。
统一管理不同运营商的 LLM 实例创建。
"""
import logging
from typing import Optional
from backend.core.llm import Llm
from backend.config import settings

logger = logging.getLogger(__name__)

# 支持的运营商
PROVIDER_OPENAI = "openai"
PROVIDER_OLLAMA = "ollama"


def get_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: Optional[int] = None
) -> Llm:
    """
    根据运营商获取对应的 LLM 实例。
    
    Args:
        provider: 运营商名称 (openai/ollama)，默认从配置读取
        model: 模型名称，默认从配置读取
        api_key: API 密钥 (仅 openai 需要)
        base_url: API 服务地址
        timeout: 超时时间(秒)
        
    Returns:
        Llm: LLM 实例
        
    Raises:
        ValueError: 不支持的运营商
    """
    # 从配置获取默认运营商
    provider = (provider or settings.chat_llm.provider or PROVIDER_OPENAI).lower()
    
    logger.info(f"正在创建 LLM 实例: provider={provider}")
    
    if provider == PROVIDER_OLLAMA:
        from backend.utils.llm.ollama_llm import OllamaLlm
        return OllamaLlm(
            model=model,
            base_url=base_url,
            timeout=timeout
        )
    elif provider == PROVIDER_OPENAI:
        from backend.utils.llm.openai_llm import OpenaiLlm
        return OpenaiLlm(
            model=model,
            api_key=api_key,
            base_url=base_url,
            timeout=timeout
        )
    else:
        error_msg = f"❌ 不支持的 LLM 运营商: {provider}，支持的运营商: {PROVIDER_OPENAI}, {PROVIDER_OLLAMA}"
        logger.error(error_msg)
        raise ValueError(error_msg)


def get_current_provider() -> str:
    """
    获取当前配置的运营商。
    
    Returns:
        str: 运营商名称
    """
    return (settings.chat_llm.provider or PROVIDER_OPENAI).lower()


def is_provider_available(provider: str) -> bool:
    """
    检查指定运营商是否可用。
    
    Args:
        provider: 运营商名称
        
    Returns:
        bool: 是否可用
    """
    return provider.lower() in [PROVIDER_OPENAI, PROVIDER_OLLAMA]
