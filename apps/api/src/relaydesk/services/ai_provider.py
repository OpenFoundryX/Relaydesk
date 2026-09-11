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

    Deliberately one exception for both. The caller's response is the same
    either way -- degrade to the widget that already works (spec D4) -- and
    a visitor must not be able to tell an outage from a refusal.
    """


@dataclass
class Completion:
    text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


class Provider(Protocol):
    def complete(
        self, *, system: str, question: str, model: str
    ) -> AsyncIterator[str]: ...

    def usage(self) -> Completion: ...


@dataclass
class FakeProvider:
    """A scripted provider, for every test in this slice that is not about HTTP."""

    chunks: list[str] = field(default_factory=list)
    fails: bool = False
    _usage: Completion = field(default_factory=Completion)

    async def complete(
        self, *, system: str, question: str, model: str
    ) -> AsyncIterator[str]:
        if self.fails:
            raise ProviderUnavailable("scripted failure")
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
        self, *, system: str, question: str, model: str
    ) -> AsyncIterator[str]:
        import anthropic

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
                messages=[{"role": "user", "content": question}],
            ) as stream:
                async for text in stream.text_stream:
                    self._usage.text += text
                    yield text
                final = await stream.get_final_message()
        except anthropic.APIStatusError as error:
            raise ProviderUnavailable(str(error)) from error
        except anthropic.APIConnectionError as error:
            raise ProviderUnavailable(str(error)) from error

        if final.stop_reason == "refusal":
            raise ProviderUnavailable("refused")
        self._usage.input_tokens = final.usage.input_tokens
        self._usage.output_tokens = final.usage.output_tokens

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
