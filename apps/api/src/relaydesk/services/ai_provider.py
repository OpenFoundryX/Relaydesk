"""One interface to a model, and the two implementations behind it.

A protocol rather than a direct SDK call for two reasons. The first is
testable: every other module in this slice can be exercised against
``FakeProvider`` with no network, no key, and no cost. The second is the
product's own argument -- this is an AGPL, self-hostable desk whose input is
other companies' support transcripts, and a deployment that could only send
them to a vendor Relaydesk picked would be unusable for the teams most
likely to self-host. Self-hosted inference plugs in here.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol

from relaydesk.models.ai_config import AiConfig


class ProviderUnavailable(Exception):
    """The model could not be reached, or refused to answer.

    One base type for both, because the caller's *response to a visitor* is
    the same either way -- degrade to the widget that already works (spec
    D4) -- and a visitor must not be able to tell an outage from a refusal.
    That guarantee covers ``str(exc)`` too: it is always the same fixed
    message, regardless of cause. The SDK's own text (or any other
    operator-useful detail) still reaches logs via ``exc.detail``, which
    never becomes part of the exception's public string.

    A caller that needs to tell the two apart -- ``ai_answers.stream``, for
    the audit row and the circuit breaker -- catches ``ProviderRefused``
    below *before* this one, rather than parsing ``.detail``: the type is
    the distinction, not the message, so nothing downstream of the visitor
    boundary can leak by accident.
    """

    def __init__(self, detail: str = "") -> None:
        super().__init__("the model is unavailable")
        self.detail = detail


class ProviderRefused(ProviderUnavailable):
    """The model declined to answer. A healthy outcome, not a failure.

    Still a ``ProviderUnavailable`` -- and still hides behind the same
    fixed ``str()`` -- so a caller that only catches the parent class (the
    visitor-facing degrade path) needs no changes and a visitor still
    cannot tell this from an outage. What changes is that a caller which
    *does* care, namely ``ai_answers.stream``, can catch this subclass
    first and record ``outcome=refused`` instead of ``degraded /
    provider_unavailable`` -- and, critically, the circuit breaker
    (``ai_budget.breaker_open``, which counts only genuine failures) never
    sees it. A refusal is a normal thing a model does when nothing
    grounded backs an answer; it must not look like the provider being
    down, or five declined questions turn AI off for the whole workspace.
    """


class ProviderRejectedRequest(ProviderUnavailable):
    """The provider rejected what we sent it. Our fault, not an outage.

    A 4xx means the request was malformed or unacceptable -- a `messages`
    array whose roles do not alternate, a model name that does not exist,
    a key that is not valid. None of that gets better by waiting, and none
    of it says anything about whether the provider is up.

    Split out for the same reason `ProviderRefused` is, and with the same
    mechanics: a subclass, so the visitor-facing degrade path needs no
    change and a visitor still cannot tell which happened, caught ahead of
    the parent by the one caller that cares. What it buys is that
    `ai_budget.breaker_open` cannot be tripped by it. The breaker exists
    to stop us hammering a provider that is down; a request we built
    wrongly is not evidence of that, and counting it let five crafted
    requests -- far under any rate limit on this door -- disable AI for an
    entire workspace for fifteen minutes.

    429 is deliberately NOT this. Being rate-limited is the provider
    telling us it cannot serve us right now, which is what the breaker is
    for.
    """



@dataclass
class Completion:
    text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class Turn:
    """One prior turn of the conversation, as the model receives it.

    ``role`` is ``"visitor"`` or ``"assistant"`` -- the wire vocabulary
    ``WidgetTurnIn`` uses, not yet Anthropic's ``"user"``/``"assistant"``.
    That mapping is ``AnthropicProvider``'s job, not this dataclass's: a
    fake or a future self-hosted provider may have its own wire shape to
    map onto instead.

    Visitor-supplied and unverified. See ``ai_answers.SYSTEM`` for how the
    system prompt keeps grounding absolute regardless of what a turn here
    claims an assistant said.
    """

    role: str
    text: str


class Provider(Protocol):
    def complete(
        self,
        *,
        system: str,
        question: str,
        model: str,
        history: list[Turn] | None = None,
    ) -> AsyncIterator[str]:
        """Stream the answer, chunk by chunk.

        ``history`` is prior turns of this conversation, oldest first, sent
        as real messages ahead of ``question`` -- not folded into
        ``system``. ``None`` and ``[]`` mean the same thing: no prior turns.

        ``ProviderUnavailable`` can be raised after one or more chunks have
        already been yielded -- a caller that streams chunks onward as they
        arrive must be prepared for the stream to end in failure after it
        has already sent partial text.
        """
        ...

    def usage(self) -> Completion: ...


@dataclass
class FakeProvider:
    """A scripted provider, for every test in this slice that is not about HTTP."""

    chunks: list[str] = field(default_factory=list)
    fails: bool = False
    refuses: bool = False
    received_system: str | None = field(default=None, init=False)
    received_question: str | None = field(default=None, init=False)
    # Always a list, never `None` -- `None` and `[]` mean the same thing to
    # a caller, so a test asserting what crossed this boundary should not
    # have to tell them apart either.
    received_history: list[Turn] = field(default_factory=list, init=False)
    _usage: Completion = field(default_factory=Completion)

    async def complete(
        self,
        *,
        system: str,
        question: str,
        model: str,
        history: list[Turn] | None = None,
    ) -> AsyncIterator[str]:
        # Recorded before either failure branch, exactly as a real provider
        # would have already received both by the time it decides to fail
        # or refuse -- callers assert on these to prove what actually
        # crossed this boundary (spec D6), not merely what was intended to.
        self.received_system = system
        self.received_question = question
        self.received_history = list(history or [])
        self._usage = Completion()
        if self.fails:
            raise ProviderUnavailable("scripted failure")
        if self.refuses:
            raise ProviderRefused("scripted refusal")
        for chunk in self.chunks:
            self._usage.text += chunk
            yield chunk
        self._usage.input_tokens = len(system) // 4 + len(question) // 4
        self._usage.output_tokens = len(self._usage.text) // 4

    def usage(self) -> Completion:
        return self._usage


class AnthropicProvider:
    """The real thing.

    ``thinking`` is adaptive and ``effort`` is low: support answering is a
    chat-shaped workload over a handful of retrieved paragraphs, and that is
    the shape that does not repay a high effort setting. Raise it only if
    measurement says so.

    The system prompt and the retrieved sources are a stable prefix across a
    conversation's turns while the question is not, which is what makes the
    cache breakpoint worth its placement.
    """

    def __init__(self, *, api_key: str, base_url: str | None = None) -> None:
        import anthropic

        self._client = anthropic.AsyncAnthropic(
            api_key=api_key, base_url=base_url, timeout=30.0, max_retries=1
        )
        self._usage = Completion()

    async def complete(
        self,
        *,
        system: str,
        question: str,
        model: str,
        history: list[Turn] | None = None,
    ) -> AsyncIterator[str]:
        """Stream the answer, chunk by chunk.

        ``history`` becomes real prior messages, oldest first, ``question``
        always last -- ``"visitor"`` maps to Anthropic's ``"user"``,
        ``"assistant"`` passes straight through. Not folded into ``system``:
        a message the model is shown as having said itself carries more
        weight with it than the same words quoted inside the system prompt,
        which is exactly why an untrusted, visitor-supplied "assistant" turn
        must never land there instead.

        A mid-stream API error raises ``ProviderUnavailable``; a refusal
        discovered only once the stream ends raises ``ProviderRefused``
        instead -- a subclass, so a caller that only wants the visitor-facing
        degrade still catches one type, while ``ai_answers.stream`` catches
        the subclass first to keep it out of the outage count. Either can be
        raised after chunks have already been yielded -- text already sent
        to the caller is not undone.
        """
        import anthropic

        messages = [
            {
                "role": "user" if turn.role == "visitor" else "assistant",
                "content": turn.text,
            }
            for turn in (history or [])
        ]
        messages.append({"role": "user", "content": question})

        try:
            async with self._client.messages.stream(
                model=model,
                max_tokens=1024,
                thinking={"type": "adaptive"},
                output_config={"effort": "low"},
                system=[
                    {
                        "type": "text",
                        "text": system,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    self._usage.text += text
                    yield text
                final = await stream.get_final_message()
        except anthropic.APIStatusError as error:
            # A 4xx is this code sending something unacceptable; a 429 or a
            # 5xx is the provider itself. Only the latter should count
            # toward the circuit breaker -- see `ProviderRejectedRequest`.
            status = getattr(error, "status_code", None)
            if isinstance(status, int) and 400 <= status < 500 and status != 429:
                raise ProviderRejectedRequest(str(error)) from error
            raise ProviderUnavailable(str(error)) from error
        except anthropic.APIConnectionError as error:
            raise ProviderUnavailable(str(error)) from error

        if final.stop_reason == "refusal":
            raise ProviderRefused("refused")
        # Every input token, not just the uncached ones. The system block
        # carries `cache_control`, so on a cache hit the SDK reports the
        # system prompt and the retrieved articles under
        # `cache_read_input_tokens` and leaves `input_tokens` holding
        # little more than the question itself. Reading only the latter
        # made a real answer over five articles record TEN input tokens,
        # and `ai_budget` sums this column -- so the context, which is the
        # expensive part, was invisible to the daily ceiling.
        #
        # Cached tokens are cheaper, not free, and the budget is a token
        # ceiling rather than a bill. Counting them keeps it honest in the
        # direction that matters.
        usage = final.usage
        self._usage.input_tokens = (
            (usage.input_tokens or 0)
            + (getattr(usage, "cache_read_input_tokens", 0) or 0)
            + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
        )
        self._usage.output_tokens = usage.output_tokens or 0

    def usage(self) -> Completion:
        return self._usage


def for_config(config: AiConfig) -> Provider | None:
    """The provider this workspace configured, or ``None`` if it has none.

    ``None`` is not an error -- it is the ordinary state of a workspace that
    has not set a key, and the caller degrades to the widget that already
    works rather than reporting anything (spec D4).
    """
    if not config.enabled or not config.api_key:
        return None
    if config.provider != "anthropic":
        return None
    return AnthropicProvider(api_key=config.api_key, base_url=config.base_url)
