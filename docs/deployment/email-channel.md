# Email channel: Migadu + Amazon SES

Production setup for the email channel. Migadu receives mail into a single
catch-all mailbox that the IMAP poller reads; Amazon SES relays outbound
replies and signs them with DKIM.

Local development uses GreenMail instead and needs none of this — see the
README. Nothing in this document requires a code change.

## Topology

```
customer  ──►  support@acme.com  ──[acme's forwarding rule]──►
                                                              │
  <slug>-<token>@inbound.example.com                          │
                     │                                        │
                     ▼                                        ▼
              MX → Migadu ──► one catch-all mailbox ──IMAP poll──► Relaydesk
                                                                      │
              customer's server ◄── SMTP ── Amazon SES ◄──────────────┘
```

Inbound and outbound run through different providers on the same domain.
MX governs inbound; SPF and DKIM govern outbound. They do not conflict.

Throughout, `inbound.example.com` stands for the subdomain you dedicate to
`INBOUND_DOMAIN`. Use a subdomain, not your apex: it keeps ticket traffic's
sending reputation separate from your corporate mail, and it means a
catch-all cannot swallow addresses you use for anything else.

## Part 1 — Migadu (inbound)

1. **Add the domain.** In the Migadu admin, add `inbound.example.com` and
   publish the verification record it shows you. Wait for it to go green
   before continuing; nothing below works until it does.

2. **Create one mailbox.** Something like `catchall@inbound.example.com`.
   This is the only mailbox you will ever create. Every workspace's ingest
   address resolves into it.

3. **Set the catch-all.** In the domain's settings, route unmatched
   recipients to that mailbox.

   This step is the whole design. A provider that files each literal
   recipient into its own mailbox drops every ticket, silently, because the
   poller only ever logs into one. Verify it explicitly in Part 5.

4. **Enable spam filtering, into a separate folder.** A catch-all accepts
   every dictionary-attack address at the domain, and the poller downloads
   whatever is in the folder it reads. Junk must land somewhere other than
   `IMAP_MAILBOX`.

5. **Set a retention rule** on the polled mailbox — delete mail older than
   30 days.

   This is not optional. `services/imap.py` never issues `EXPUNGE`; the
   poller's cursor is a UID high-water mark, so it never deletes anything
   it has read. Without a provider-side rule the mailbox grows forever,
   eventually hits quota, and then inbound mail bounces at the edge —
   where Relaydesk cannot see it and will report nothing at all.

   Deleting old mail is safe: the poller only ever asks for UIDs *above*
   its stored `last_uid`, so removing messages below it changes nothing.

6. **Note the IMAP details**: `imap.migadu.com`, port `993`, SSL, the
   mailbox address as the username.

## Part 2 — Amazon SES (outbound)

1. **Pick a region** and stay in it. SES SMTP endpoints are regional.

2. **Verify the domain** `inbound.example.com` and enable **Easy DKIM**.
   SES gives you three CNAME records. Publish all three and wait for
   verification.

   Verifying the domain (not individual addresses) is what allows SES to
   send as `<slug>-<token>+c<n>@inbound.example.com` — a different `From`
   for every workspace and every thread, all covered by one verification.

3. **Request production access.** A new SES account is sandboxed: it can
   only send to verified addresses, at roughly 200 messages per 24 hours.
   Do this on day one, not on launch day — approval is not instant.

4. **Create SMTP credentials.** In the SES console, *SMTP settings →
   Create SMTP credentials*. These are SES-specific credentials derived
   from an IAM user; a raw IAM access key will not authenticate against
   the SMTP endpoint.

5. **Note the endpoint**: `email-smtp.<region>.amazonaws.com`, port `587`,
   STARTTLS.

### Bounces need no configuration

SES reports a bounce by mailing it to the envelope sender.
`services/mailer.py` hands `aiosmtplib` a built message without an explicit
sender, so the envelope sender is the message's `From` header — which
`outbound.build_reply` sets to the tokenized, conversation-tagged workspace
address.

A bounce therefore returns to `<slug>-<token>+c<n>@inbound.example.com`,
lands in the Migadu catch-all, is polled like any other mail, and is
recognised by `email_parse/classify.py` as `Disposition.bounce`.
`ingest._handle_bounce` then threads it onto the conversation it belongs to
as a system message and stamps `contacts.bounced_at`.

SNS bounce notifications are a possible future improvement, not a
requirement.

Note also that SES maintains its own account-level suppression list and
stops delivering to addresses that hard-bounce repeatedly. That partially
covers for the fact that Relaydesk writes `contacts.bounced_at` but does not
yet read it (see Known gaps).

## Part 3 — DNS

Publish all of these on `inbound.example.com`. Copy the exact values from
the two consoles; the shapes below are illustrative.

```dns
; inbound — Migadu
inbound.example.com.        MX     10 aspmx1.migadu.com.
inbound.example.com.        MX     20 aspmx2.migadu.com.
inbound.example.com.        TXT    "<migadu verification value>"

; outbound — SES DKIM (three CNAMEs from the SES console)
<token1>._domainkey.inbound.example.com.  CNAME  <token1>.dkim.amazonses.com.
<token2>._domainkey.inbound.example.com.  CNAME  <token2>.dkim.amazonses.com.
<token3>._domainkey.inbound.example.com.  CNAME  <token3>.dkim.amazonses.com.

; outbound — SPF
inbound.example.com.        TXT    "v=spf1 include:amazonses.com -all"

; policy
_dmarc.inbound.example.com. TXT    "v=DMARC1; p=none; rua=mailto:dmarc@example.com"
```

Three things worth stating plainly:

**SPF names SES, not Migadu.** Migadu receives for this domain but never
sends for it. Adding `include:spf.migadu.com` would authorise a sender you
do not use.

**Start DMARC at `p=none`.** Read the aggregate reports for two weeks, then
move to `p=quarantine`. Going straight to enforcement risks silently
discarding your own mail.

**A custom MAIL FROM domain in SES is optional.** DMARC passes on DKIM
alignment alone, and SES's Easy DKIM signs as `d=inbound.example.com`,
which aligns. Configure a custom MAIL FROM only if you also want SPF
alignment.

## Part 4 — Configuration

```sh
INBOUND_DOMAIN=inbound.example.com

IMAP_HOST=imap.migadu.com
IMAP_PORT=993
IMAP_USE_SSL=true
IMAP_USERNAME=catchall@inbound.example.com
IMAP_PASSWORD=<secret store>
IMAP_MAILBOX=INBOX
IMAP_POLL_SECONDS=60

SMTP_HOST=email-smtp.<region>.amazonaws.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=<SES SMTP username>
SMTP_PASSWORD=<SES SMTP password>
SMTP_FROM_NAME=<your product name>
```

`IMAP_USE_SSL` and `SMTP_USE_TLS` both default to `false` for GreenMail.
Leaving them false in production sends a mailbox password in the clear.

`TRUSTED_PROXY_IPS` must also be set to whatever address the API actually
sees your proxy arrive from — it is pinned to a Compose-static address for
local development and will be wrong in any other topology. The README
explains the consequences.

## Part 5 — Verification

Run these in order. Each one fails in a way that is otherwise silent.

**1. The catch-all really is a catch-all.** Mail an address that does not
exist:

```sh
# to garbage-$(random)@inbound.example.com, from anywhere
```

Then confirm it is in the polled mailbox:

```sh
docker compose exec api python -c "
import imaplib
from relaydesk.config import get_settings
s = get_settings()
c = imaplib.IMAP4_SSL(s.imap_host, s.imap_port)
c.login(s.imap_username, s.imap_password)
print(c.select(s.imap_mailbox))
print(c.search(None, 'ALL'))
"
```

If it is not there, stop. Nothing else will work.

**2. A forwarded ticket becomes a ticket.** Set up forwarding from a real
support address to a workspace's ingest address, mail it from an outside
account, and confirm it appears in the inbox within `IMAP_POLL_SECONDS`.

If it does not, check `relaydesk unrouted` — a row there means the mail
arrived but carried no recognisable ingest address, which is almost always
a forwarding rule pointing at the wrong place.

**3. A reply is delivered and authenticated.** Reply from the console to an
address at Gmail, and in the received message check that SPF, DKIM, and
DMARC all pass. Gmail's *Show original* reports all three.

**4. Threading survives a round trip.** Reply to that reply from the
customer side and confirm it appends to the same conversation rather than
opening a second one.

**5. Bounces come home.** Reply to a conversation whose contact address does
not exist. Within a few minutes the conversation should show a
`Delivery failed` system message.

## Part 6 — Operations

**Watch the pipeline:**

```sh
docker compose logs -f worker beat
docker compose exec api relaydesk unrouted
```

**Mail that could not be turned into a ticket** keeps its original bytes and
is replayable once you fix the cause:

```sh
docker compose exec api relaydesk reingest <raw-message-id>
```

**`beat` must be a singleton.** Two schedulers means two pollers racing on
the same `poll_state` row, which is read without a lock. Correctness
survives — the unique constraint on `(mailbox, uidvalidity, uid)` makes the
duplicate fetch a no-op — but the work is done twice. Workers scale out
freely; `beat` does not.

**Warm up the sending domain.** Do not go from zero to thousands of
messages a day on a freshly verified domain. Follow SES's ramp guidance.

**Alarms worth having:** SES bounce and complaint rates (SES enforces
thresholds and will pause an account that exceeds them), mailbox size at
Migadu, and the count of `raw_messages` sitting in `fetched` or `failed`.

## Known gaps

These are real and unaddressed. None block launch; all are worth knowing.

- **`contacts.bounced_at` is written but never read.** A hard-bounced
  address keeps receiving replies. SES's own suppression list limits the
  damage but does not remove it.
- **No mail retention job in Relaydesk.** Retention is entirely a
  provider-side rule you configure by hand (Part 1, step 5).
- **Unrouted mail is CLI-only.** A customer with a broken forwarding rule
  is invisible until they complain.
- **No custom sending domains.** Replies come from
  `<slug>-<token>@inbound.example.com`, not from the customer's own domain.
  Per-workspace DKIM would change only the `From` construction in
  `services/outbound.py` and add a domain-verification flow.
- **Throughput ceiling.** One mailbox, one poller, 200 messages per poll.
  SES inbound receipt rules or another provider's inbound webhooks would
  remove it: a webhook adapter produces the same `InboundMessage` and
  reuses classification, routing, and threading unchanged. Only
  `services/imap.py` is IMAP-specific.
