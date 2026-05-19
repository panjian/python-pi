import os
from pydantic_settings import BaseSettings, SettingsConfigDict

# 🔥 新增：动态获取 config.py 所在的绝对主目录
AGENT_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
GLOBAL_ENV_PATH = os.path.join(AGENT_ROOT_DIR, ".env")

class Settings(BaseSettings):
    llm_provider: str = "openai"
    
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    
    openai_base_url: str = ""
    anthropic_base_url: str = ""
    
    openai_model: str = "gpt-4o"
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    
    # 🔥 修改：将 env_file 指向全局固定的 .env 路径
    model_config = SettingsConfigDict(env_file=GLOBAL_ENV_PATH, env_file_encoding="utf-8", extra="ignore")

settings = Settings()