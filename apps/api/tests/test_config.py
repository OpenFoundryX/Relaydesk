from relaydesk.config import Settings


def test_mail_settings_default_to_the_development_stack() -> None:
    """A fresh clone must have a working mail path with no external account,
    so the defaults point at the GreenMail container in docker-compose."""
    settings = Settings(_env_file=None)

    assert settings.smtp_host == "greenmail"
    assert settings.smtp_port == 3025
    assert settings.imap_host == "greenmail"
    assert settings.imap_port == 3143
    assert settings.inbound_domain == "inbound.localhost"
    assert settings.celery_broker_url.startswith("amqp://")


def test_attachment_cap_is_twenty_five_megabytes() -> None:
    assert Settings(_env_file=None).attachment_max_bytes == 26214400
