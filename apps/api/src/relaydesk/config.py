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
    # The root a workspace subdomain is resolved against: a workspace with
    # slug "acme" is reachable at "acme.<portal_domain>". Not read anywhere
    # in the API today -- `relaydesk.api.public` resolves a workspace from
    # the `{slug}` path parameter it is handed, not from a hostname. The
    # value that is actually consumed for host-to-slug resolution is
    # apps/web/middleware.ts, via its own NEXT_PUBLIC_PORTAL_DOMAIN env var,
    # which this setting's default is kept in sync with by convention.
    portal_domain: str = "localhost:3000"

    celery_broker_url: str = "amqp://guest:guest@rabbitmq:5672//"

    inbound_domain: str = "inbound.localhost"

    imap_host: str = "greenmail"
    imap_port: int = 3143
    # GreenMail (auth disabled) keys a mailbox by the exact login string, and
    # separately by the exact RCPT TO address at delivery time — a bare
    # "relaydesk" and "relaydesk@localhost" are two different mailboxes. The
    # single polled inbox is only reachable this way, so the default must be
    # address-shaped to match where dev/test mail is actually delivered.
    imap_username: str = "relaydesk@localhost"
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
    kb_image_max_bytes: int = 5242880

    # Comma-separated peer addresses whose X-Forwarded-For we believe. Empty
    # means believe nobody, which is correct for a directly-exposed API: a
    # forged header must never let a caller pick its own rate-limit bucket.
    trusted_proxy_ips: str = ""

    # Portal ticket submissions allowed from one address per hour. Low on
    # purpose: a genuine customer opens one ticket, not five.
    ticket_ip_hourly_cap: int = 5
    ticket_message_max_chars: int = 10000
    ticket_attachment_max_count: int = 5

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
