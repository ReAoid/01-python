import os
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel
from dotenv import load_dotenv
from loguru import logger


class Config(BaseModel):
    """配置管理"""

    # LLM配置
    default_model: str = "gpt-3.5-turbo"
    default_provider: str = "openai"
    temperature: float = 0.7
    max_tokens: Optional[int] = None

    # 系统配置
    debug: bool = False
    log_level: str = "INFO"

    # 其他配置
    max_history_length: int = 100

    @staticmethod
    def load_env(env_file: str = ".env", silent: bool = False) -> bool:
        """
        加载环境变量配置文件。
        
        Args:
            env_file: .env 文件名,默认为 ".env"
            silent: 是否静默模式(不输出日志),默认 False
            
        Returns:
            bool: 是否成功加载
        """
        # 构建 .env 文件的完整路径 (backend/.env)
        # 假设 config.py 在 backend/core/ 目录下
        env_path = Path(__file__).parent.parent / env_file
        
        if not env_path.exists():
            if not silent:
                logger.warning(f"环境变量文件不存在: {env_path}")
            return False
        
        # 加载环境变量
        load_dotenv(dotenv_path=env_path, override=True)
        
        if not silent:
            logger.info(f"成功从 {env_path} 加载环境变量")
        
        return True

    @classmethod
    def from_env(cls) -> "Config":
        """从环境变量创建配置"""
        return cls(
            debug=os.getenv("DEBUG", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            temperature=float(os.getenv("TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("MAX_TOKENS")) if os.getenv("MAX_TOKENS") else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.dict()
