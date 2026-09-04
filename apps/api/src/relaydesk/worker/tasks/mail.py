from relaydesk.services import mailer
from relaydesk.worker import bridge
from relaydesk.worker.app import app


@app.task(
    name="relaydesk.send_system_email",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=5,
)
def send_system_email(
    to: str, subject: str, text_body: str, html_body: str | None = None
) -> None:
    bridge.run(
        mailer.send(
            to=to,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            headers=mailer.system_headers(),
        )
    )
