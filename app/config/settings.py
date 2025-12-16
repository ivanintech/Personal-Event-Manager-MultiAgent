# Copyright 2024
# Directory: yt-agentic-rag/app/config/settings.py

"""
Application Settings - Environment Variable Management.

Loads and validates all configuration from environment variables:
- Supabase credentials for vector database
- OpenAI/Anthropic API keys for LLM
- Google service account for calendar/email tools
- Application settings (log level, environment, etc.)

Uses Pydantic Settings for automatic .env file loading and validation.
"""

from typing import Literal, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Required environment variables:
    - SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY
    - OPENAI_API_KEY
    
    Optional environment variables:
    - ANTHROPIC_API_KEY (for Claude support)
    - GOOGLE_SERVICE_ACCOUNT_PATH, GOOGLE_CALENDAR_EMAIL (for tools)
    """
    
    # =========================================================================
    # Supabase Configuration
    # =========================================================================
    supabase_url: str = Field(..., env="SUPABASE_URL")
    supabase_anon_key: str = Field(..., env="SUPABASE_ANON_KEY")
    supabase_service_role_key: str = Field(..., env="SUPABASE_SERVICE_ROLE_KEY")

    # =========================================================================
    # AI Provider Configuration
    # =========================================================================
    ai_provider: Literal["openai", "anthropic", "nebius"] = Field(
        default="openai",
        env="AI_PROVIDER",
    )

    # OpenAI Configuration
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    openai_embed_model: str = Field(
        default="text-embedding-3-small",
        env="OPENAI_EMBED_MODEL",
    )
    openai_chat_model: str = Field(
        default="gpt-4o",
        env="OPENAI_CHAT_MODEL",
    )

    # Anthropic Configuration (optional)
    anthropic_api_key: str = Field(default="", env="ANTHROPIC_API_KEY")
    anthropic_chat_model: str = Field(
        default="claude-3-5-sonnet-20240620",
        env="ANTHROPIC_CHAT_MODEL",
    )

    # =========================================================================
    # Nebius Configuration
    # =========================================================================
    nebius_api_key: str = Field(default="", env="NEBIUS_API_KEY")
    nebius_base_url: str = Field(
        default="https://tokenfactory.nebius.com",
        env="NEBIUS_BASE_URL",
    )
    # Defaults alineados con modelos confirmados como accesibles en Nebius
    nebius_chat_model: str = Field(default="deepseek-ai/DeepSeek-R1-0528", env="NEBIUS_MODEL_CHAT")
    nebius_specialist_model: str = Field(default="Qwen/Qwen3-32B", env="NEBIUS_MODEL_SPECIALIST")
    nebius_router_model: str = Field(default="openai/gpt-oss-20b", env="NEBIUS_MODEL_ROUTER")
    nebius_embed_model: str = Field(default="BAAI/bge-multilingual-gemma2", env="NEBIUS_MODEL_EMBED")
    nebius_guard_model: str = Field(default="Meta-Llama-Guard-3-8B", env="NEBIUS_MODEL_GUARD")

    # =========================================================================
    # Voz (STT/TTS)
    # =========================================================================
    voice_tts_backend: str = Field(default="mock", env="VOICE_TTS_BACKEND")  # mock | vibevoice | elevenlabs
    vibevoice_base_url: str = Field(default="", env="VIBEVOICE_BASE_URL")
    vibevoice_model: str = Field(default="", env="VIBEVOICE_MODEL")
    elevenlabs_api_key: str = Field(default="", env="ELEVENLABS_API_KEY")
    elevenlabs_voice_id: str = Field(default="", env="ELEVENLABS_VOICE_ID")

    voice_stt_backend: str = Field(default="mock", env="VOICE_STT_BACKEND")  # mock | whisper
    stt_provider: str = Field(default="mock", env="STT_PROVIDER")  # groq | openai | mock
    groq_api_key: str = Field(default="", env="GROQ_API_KEY")
    groq_whisper_model: str = Field(default="whisper-large-v3", env="GROQ_WHISPER_MODEL")
    openai_whisper_model: str = Field(default="whisper-1", env="OPENAI_WHISPER_MODEL")

    # =========================================================================
    # MCP / TOOLS
    # =========================================================================
    use_mock_mcp: bool = Field(default=True, env="USE_MOCK_MCP")
    mcp_config_path: str = Field(default="app/mcp/mcp_servers.json", env="MCP_CONFIG_PATH")
    mcp_mapping_path: str = Field(default="app/mcp/mapping.json", env="MCP_MAPPING_PATH")

    # =========================================================================
    # Google API Configuration (OAuth usuario y Service Account)
    # =========================================================================
    google_oauth_client_path: str = Field(default="credentials/google_oauth_client.json", env="GOOGLE_OAUTH_CLIENT_PATH")
    google_oauth_token_path: str = Field(default="credentials/google_oauth_token.json", env="GOOGLE_OAUTH_TOKEN_PATH")
    google_oauth_redirect_uri: str = Field(default="http://localhost:8090/", env="GOOGLE_OAUTH_REDIRECT_URI")

    google_service_account_json: str = Field(default="", env="GOOGLE_SERVICE_ACCOUNT_JSON")
    google_service_account_path: str = Field(default="credentials/google_service_account.json", env="GOOGLE_SERVICE_ACCOUNT_PATH")
    google_calendar_email: str = Field(default="", env="GOOGLE_CALENDAR_EMAIL")
    google_calendar_id: str = Field(default="primary", env="GOOGLE_CALENDAR_ID")
    gmail_impersonate: str = Field(default="", env="GMAIL_IMPERSONATE")

    # SMTP email (alternativa a Gmail API)
    smtp_host: str = Field(default="", env="SMTP_HOST")
    smtp_port: int = Field(default=587, env="SMTP_PORT")
    smtp_user: str = Field(default="", env="SMTP_USER")
    smtp_pass: str = Field(default="", env="SMTP_PASS")
    smtp_from: str = Field(default="", env="SMTP_FROM")
    smtp_use_tls: bool = Field(default=True, env="SMTP_USE_TLS")

    # IMAP email (para leer emails: Thunderbird, Outlook, Gmail IMAP)
    imap_host: str = Field(default="", env="IMAP_HOST")
    imap_port: int = Field(default=993, env="IMAP_PORT")
    imap_user: str = Field(default="", env="IMAP_USER")
    imap_pass: str = Field(default="", env="IMAP_PASS")
    imap_use_ssl: bool = Field(default=True, env="IMAP_USE_SSL")

    # =========================================================================
    # Calendly / Twilio
    # =========================================================================
    calendly_api_key: str = Field(default="", env="CALENDLY_API_KEY")
    calendly_client_id: str = Field(default="", env="CALENDLY_CLIENT_ID")
    calendly_client_secret: str = Field(default="", env="CALENDLY_CLIENT_SECRET")
    calendly_redirect_uri: str = Field(default="http://localhost:8000/api/v1/calendly/callback", env="CALENDLY_REDIRECT_URI")
    calendly_webhook_secret: str = Field(default="", env="CALENDLY_WEBHOOK_SECRET")
    twilio_account_sid: str = Field(default="", env="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = Field(default="", env="TWILIO_AUTH_TOKEN")
    twilio_whatsapp_from: str = Field(default="", env="TWILIO_WHATSAPP_FROM")
    huggingface_hub_token: str = Field(default="", env="HUGGINGFACE_HUB_TOKEN")

    # =========================================================================
    # Application Configuration
    # =========================================================================
    environment: str = Field(default="development", env="ENVIRONMENT")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    langgraph_agent: bool = Field(default=False, env="LANGGRAPH_AGENT")
    execute_tools_in_graph: bool = Field(default=False, env="EXECUTE_TOOLS_IN_GRAPH")
    use_mock_voice: bool = Field(default=True, env="USE_MOCK_VOICE")

    # =========================================================================
    # RAG Configuration
    # =========================================================================
    default_top_k: int = Field(default=3)
    chunk_size: int = Field(default=400)
    chunk_overlap: int = Field(default=60)
    temperature: float = Field(default=0.1)
    embedding_dimensions: int = Field(default=1024)
    
    # Embedding Cache Configuration
    embedding_cache_enabled: bool = Field(default=True, env="EMBEDDING_CACHE_ENABLED")
    embedding_cache_ttl: int = Field(default=3600, env="EMBEDDING_CACHE_TTL")  # 1 hora en segundos
    embedding_cache_max_size: int = Field(default=1000, env="EMBEDDING_CACHE_MAX_SIZE")  # Máximo de entradas

    # =========================================================================
    # Agent Configuration
    # =========================================================================
    max_agent_iterations: int = Field(default=2)

    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """
    Get application settings instance.
    
    Returns:
        Settings instance with all configuration values
    """
    return settings
