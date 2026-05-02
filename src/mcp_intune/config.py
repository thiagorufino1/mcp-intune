from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    azure_tenant_id: str
    azure_client_id: str
    azure_client_secret: SecretStr

    fastmcp_transport: str = "http"
    fastmcp_host: str = "127.0.0.1"
    fastmcp_port: int = 8000

    log_level: str = "INFO"
    log_format: str = "json"
    allow_beta_apis: bool = False

    cache_ttl_device: int = 60
    cache_ttl_policy: int = 120
    cache_ttl_app: int = 300

    approval_ttl_seconds: int = 3600

    graph_timeout_connect: float = 10.0
    graph_timeout_read: float = 30.0
    graph_max_retries: int = 4
    graph_default_top: int = 50


settings = Settings()
