import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Type, Tuple
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, PydanticBaseSettingsSource
from .migration import migration

# =============================================================================
# 子配置模型
# =============================================================================

class LLMConfig(BaseModel):
    default_model: str = "gpt-3.5-turbo"
    default_provider: str = "openai"
    temperature: float = 0.7
    max_tokens: Optional[int] = None

class ApiConfig(BaseModel):
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_timeout: int = 60
    serpapi_api_key: Optional[str] = None

class SystemConfig(BaseModel):
    debug: bool = False
    log_level: str = "INFO"
    data_dir: Optional[str] = None

class MemoryConfig(BaseModel):
    max_history_length: int = 10
    embedding_model: str = "Qwen/Qwen3-Embedding-8B"

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

class ASRConfig(BaseModel):
    enabled: bool = False
    engine: str = "whisper"
    model: str = "base"
    language: str = "zh"

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
        # 使用 migration 模块找到配置文件路径
        config_path = migration.get_config_path('core_config.json')
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
    支持从 core_config.json 和 环境变量 (.env) 加载
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
    
    # 扁平化映射: 允许通过 LLM_API_KEY 直接设置 api.llm_api_key
    # 这需要我们在 settings_customise_sources 处理，或者使用 Pydantic 的 extra='ignore' 配合手动映射
    # 这里我们采用简单的映射属性
    
    @property
    def LLM_API_KEY(self) -> Optional[str]:
        return self.api.llm_api_key
        
    @property
    def LLM_BASE_URL(self) -> Optional[str]:
        return self.api.llm_base_url

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
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
            JsonConfigSettingsSource(settings_cls), # 我们的自定义 JSON 源
            file_secret_settings,
        )

# =============================================================================
# 辅助函数
# =============================================================================

def load_settings() -> Settings:
    """加载配置单例"""
    # 1. 确保目录结构和配置文件存在
    migration.migrate_all()
    
    # 2. 实例化 Settings (会自动加载 JSON 和 ENV)
    return Settings()

# 全局单例
settings = load_settings()
