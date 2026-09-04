from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Relaydesk"
    app_env: str = "development"
    database_url: str = (
        "postgresql+asyncpg://relaydesk:relaydesk@postgres:5432/relaydesk"
    )
    cors_origins: str = "http://localhost:3000"
    session_ttl_days: int = 30
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15
    google_client_id: str = ""
    google_client_secret: str = ""
    web_url: str = "http://localhost:3000"

    celery_broker_url: str = "amqp://guest:guest@rabbitmq:5672//"

    inbound_domain: str = "inbound.localhost"

    imap_host: str = "greenmail"
    imap_port: int = 3143
    imap_username: str = "relaydesk"
    imap_password: str = "relaydesk"
    imap_use_ssl: bool = False
    imap_mailbox: str = "INBOX"
    imap_poll_seconds: int = 60

    smtp_host: str = "greenmail"
    smtp_port: int = 3025
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = False
    smtp_from_name: str = "Relaydesk"

    attachment_dir: str = "/var/lib/relaydesk/attachments"
    attachment_max_bytes: int = 26214400

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
