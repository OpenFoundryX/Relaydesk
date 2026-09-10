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
    # A reset link is a password in transit. One hour is long enough to
    # find the mail and short enough that a link left sitting in an inbox
    # or a mail archive stops being useful quickly.
    password_reset_ttl_minutes: int = 60
    # Both caps are deliberately low. They are what bounds the residual
    # timing channel documented in section 6.2 of the design: telling two
    # addresses apart through a noisy timing difference needs repeated
    # samples per address, and these deny the sample volume.
    password_reset_ip_hourly_cap: int = 5
    password_reset_email_hourly_cap: int = 3
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
    # The address outbound replies are sent *from*. Empty means send from the
    # workspace's own tagged ingest address, which is what routing needs but
    # reads as machine-generated to a recipient and to spam filters. Setting
    # it moves only the From; `Reply-To` keeps the tagged address, because
    # that is what actually carries a reply back onto the conversation.
    outbound_from_address: str = ""

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
    # Submissions one embed may accept per hour, on top of the per-IP cap. An
    # abused embed exhausts this before it touches the workspace's own budget.
    widget_key_hourly_cap: int = 60
    ticket_message_max_chars: int = 10000
    ticket_attachment_max_count: int = 5

    # The largest request body this API will let a route read. Enforced from
    # the declared Content-Length before anything is parsed, because
    # `POST /api/public/{slug}/tickets` declares multipart Form/File
    # parameters: Starlette parses and spools the whole body while resolving
    # those dependencies, which is *before* the route body -- and so before
    # the rate limiter -- ever runs. Without this, an anonymous caller
    # already over its cap could still make the process read an unbounded
    # body on every request.
    #
    # 32 MiB comfortably clears a legitimate submission: attachments share a
    # single `attachment_max_bytes` (25 MiB) budget across at most
    # `ticket_attachment_max_count` files, plus a 10,000-character message
    # and multipart framing.
    max_request_bytes: int = 33554432

    # Calls one API key may make per minute. Generous for an integration
    # syncing tickets, and low enough that a runaway loop is bounded before
    # it becomes the database's problem. A fixed window, so a caller can see
    # up to twice this across a boundary -- see the note in migration 0017.
    api_key_rate_limit_per_minute: int = 120

    # A webhook URL is supplied by a workspace and fetched by the server, so
    # the default assumes it is hostile: https only, and nothing that
    # resolves off the public internet. Setting this admits private and
    # loopback addresses -- correct for a self-hoster whose tools live on the
    # same network, wrong for anyone else. See spec D8; it relaxes the
    # address check and nothing else.
    webhook_allow_private: bool = False
    webhook_timeout_seconds: float = 10.0
    # Generous for someone debugging an endpoint, far short of useful for
    # turning the console into a request proxy.
    webhook_test_hourly_cap: int = 60

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
