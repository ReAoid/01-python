import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Type, Tuple
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, PydanticBaseSettingsSource

# =============================================================================
# 子配置模型
# =============================================================================

class LLMApiConfig(BaseModel):
    """LLM API 端点配置（聊天或嵌入）"""
    key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: int = 60

class ChatLLMConfig(BaseModel):
    """聊天大语言模型配置"""
    model: str = "gpt-3.5-turbo"
    provider: str = "openai"
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    api: LLMApiConfig = Field(default_factory=LLMApiConfig)

class EmbeddingLLMConfig(BaseModel):
    """向量嵌入模型配置"""
    model: str = "Qwen/Qwen3-Embedding-8B"
    api: LLMApiConfig = Field(default_factory=LLMApiConfig)

class ThirdPartyApiConfig(BaseModel):
    """第三方服务 API 配置"""
    serpapi_api_key: Optional[str] = None

class SystemConfig(BaseModel):
    debug: bool = False
    log_level: str = "INFO"
    data_dir: Optional[str] = None

class MemoryConfig(BaseModel):
    # 短期记忆配置
    max_history_length: int = 10  # 短期记忆保留的对话轮数
    
    # 结构化处理配置
    min_summaries_for_structuring: int = 3  # 触发结构化的最小总结数
    structuring_batch_size: int = 5  # 每次结构化处理的总结数量
    
    # 检索配置
    retrieval_top_k: int = 5  # 默认检索数量
    retrieval_threshold: float = 0.6  # 相似度阈值

class UserProfileConfig(BaseModel):
    """用户档案配置（简化版）"""
    name: Optional[str] = None  # 用户姓名
    nickname: Optional[str] = None  # 用户昵称
    age: Optional[int] = None  # 用户年龄
    gender: Optional[str] = None  # 用户性别
    relationship_with_ai: Optional[str] = None  # 与AI的关系（如：朋友、助手、老师等）

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


class ASRVADConfig(BaseModel):
    """ASR VAD 配置"""
    enabled: bool = True
    energy_threshold: float = 0.01
    aggressiveness: int = 3

class ASRPreprocessingConfig(BaseModel):
    """ASR 音频预处理配置"""
    noise_reduction: bool = False
    auto_gain_control: bool = False

class ASRConfig(BaseModel):
    enabled: bool = False
    engine: str = "dummy"
    model: str = "base"
    model_path: Optional[str] = None
    device: str = "cpu"
    language: str = "zh"
    min_audio_length: float = 1.0
    audio: ASRAudioConfig = Field(default_factory=ASRAudioConfig)
    vad: ASRVADConfig = Field(default_factory=ASRVADConfig)
    preprocessing: ASRPreprocessingConfig = Field(default_factory=ASRPreprocessingConfig)

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
            # 从 JSON 根目录获取配置 (例如 chat_llm, embedding_llm, third_party_api)
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
    
    配置结构：
    - chat_llm: 聊天大语言模型配置
    - embedding_llm: 向量嵌入模型配置
    - system: 系统配置
    - memory: 记忆系统配置
    - tts: 文本转语音配置
    - asr: 语音识别配置
    - user_profile: 用户档案配置
    - third_party_api: 第三方服务 API 配置
    """
    # ========== LLM 配置 ==========
    chat_llm: ChatLLMConfig = Field(default_factory=ChatLLMConfig)
    embedding_llm: EmbeddingLLMConfig = Field(default_factory=EmbeddingLLMConfig)
    
    # ========== 系统配置 ==========
    system: SystemConfig = Field(default_factory=SystemConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    asr: ASRConfig = Field(default_factory=ASRConfig)
    user_profile: UserProfileConfig = Field(default_factory=UserProfileConfig)
    third_party_api: ThirdPartyApiConfig = Field(default_factory=ThirdPartyApiConfig)
    
    # ========== 应用信息 ==========
    app_name: str = "灵依"

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",  # 允许 CHAT_LLM__MODEL 覆盖 chat_llm.model
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
