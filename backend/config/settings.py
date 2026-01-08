import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Type, Tuple
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, PydanticBaseSettingsSource

# =============================================================================
# 子配置模型
# =============================================================================

class LLMConfig(BaseModel):
    default_model: str = "gpt-3.5-turbo"
    default_provider: str = "openai"
    temperature: float = 0.7
    max_tokens: Optional[int] = None

class ApiConfig(BaseModel):
    # 对话 LLM 配置
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_timeout: int = 60
    
    # Embedding 配置（独立）
    embedding_api_key: Optional[str] = None
    embedding_base_url: Optional[str] = None
    embedding_timeout: int = 60
    
    # 其他 API
    serpapi_api_key: Optional[str] = None

class SystemConfig(BaseModel):
    debug: bool = False
    log_level: str = "INFO"
    data_dir: Optional[str] = None

class MemoryConfig(BaseModel):
    # 短期记忆配置
    max_history_length: int = 10  # 短期记忆保留的对话轮数
    
    # Embedding 配置
    embedding_model: str = "Qwen/Qwen3-Embedding-8B"
    
    # 结构化处理配置
    min_summaries_for_structuring: int = 3  # 触发结构化的最小总结数
    structuring_batch_size: int = 5  # 每次结构化处理的总结数量
    
    # 检索配置
    retrieval_top_k: int = 5  # 默认检索数量
    retrieval_threshold: float = 0.6  # 相似度阈值

class TTSServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8001
    auto_start: bool = False

class TTSConfig(BaseModel):
    enabled: bool = True
    engine: str = "genie"
    genie_data_dir: Optional[str] = None
    active_character: str = "feibi"
    language: str = "zh"
    server: TTSServerConfig = Field(default_factory=TTSServerConfig)

class ASRAudioConfig(BaseModel):
    sample_rate: int = 16000
    channels: int = 1
    sample_width: int = 2


class ASRConfig(BaseModel):
    enabled: bool = False
    engine: str = "whisper"
    model: str = "base"
    language: str = "zh"
    audio: ASRAudioConfig = Field(default_factory=ASRAudioConfig)

# =============================================================================
# 自定义 JSON Source
# =============================================================================

class JsonConfigSettingsSource(PydanticBaseSettingsSource):
    """
    从 core_config.json 加载配置的源。
    优先级低于环境变量。
    """
    def get_field_value(
        self, field: Any, field_name: str
    ) -> Tuple[Any, str, bool]:
        # 不在此处实现，使用 __init__ 预加载的数据
        return super().get_field_value(field, field_name)

    def __init__(self, settings_cls: Type[BaseSettings]):
        super().__init__(settings_cls)
        self.config_data = self._load_json_config()

    def _load_json_config(self) -> Dict[str, Any]:
        # 使用 paths 模块找到配置文件路径
        from . import paths
        config_path = paths.CONFIG_DIR / 'core_config.json'
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load config from {config_path}: {e}")
        return {}

    def __call__(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        for field_name, field in self.settings_cls.model_fields.items():
            # 尝试从 JSON 根目录获取 (例如 llm, api)
            if field_name in self.config_data:
                d[field_name] = self.config_data[field_name]
        return d

# =============================================================================
# 主配置类
# =============================================================================

class Settings(BaseSettings):
    """
    应用全局配置
    支持从 core_config.json 加载
    """
    # 子模块配置
    llm: LLMConfig = Field(default_factory=LLMConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    system: SystemConfig = Field(default_factory=SystemConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    asr: ASRConfig = Field(default_factory=ASRConfig)

    # 顶层配置 (如果有)
    app_name: str = "灵依"
    
    @property
    def LLM_API_KEY(self) -> Optional[str]:
        return self.api.llm_api_key
        
    @property
    def LLM_BASE_URL(self) -> Optional[str]:
        return self.api.llm_base_url
    
    @property
    def EMBEDDING_API_KEY(self) -> Optional[str]:
        """Embedding API Key"""
        return self.api.embedding_api_key
    
    @property
    def EMBEDDING_BASE_URL(self) -> Optional[str]:
        """Embedding Base URL"""
        return self.api.embedding_base_url

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",  # 允许 LLM__DEFAULT_MODEL 覆盖 llm.default_model
        extra="ignore"
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            JsonConfigSettingsSource(settings_cls),  # 我们的自定义 JSON 源
            file_secret_settings,
        )

# =============================================================================
# 辅助函数
# =============================================================================

def load_settings() -> Settings:
    """加载配置单例"""
    # 实例化 Settings (会自动加载 JSON 和 ENV)
    return Settings()

# 全局单例
settings = load_settings()
