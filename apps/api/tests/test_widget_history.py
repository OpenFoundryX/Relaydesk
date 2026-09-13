"""What `WidgetAskIn` does to a conversation before the model sees it.

The Messages API rejects a `messages` array that does not start with a
user turn, or whose roles do not strictly alternate, or that carries an
empty content block. Each is a 400, and `AnthropicProvider.complete`
turns a 400 into `ProviderUnavailable` -- which `ai_budget.breaker_open`
counts. Five of them disables AI for the whole workspace for fifteen
minutes.

So this shape cannot be left to the client. The browser is only one
caller of an anonymous route whose key sits in any customer's page
source, and the bundled client is not even a well-behaved one: it
appends the escalation offer directly after an answer, which is two
assistant turns in a row.
"""

import pytest

from relaydesk.schemas.widget import (
    HISTORY_MAX_TURNS,
    HISTORY_TURN_MAX_CHARS,
    WidgetAskIn,
)


def ask(*turns: tuple[str, str]) -> list[tuple[str, str]]:
    parsed = WidgetAskIn.model_validate(
        {
            "question": "and after that?",
            "history": [{"role": role, "text": text} for role, text in turns],
        }
    )
    return [(turn.role, turn.text) for turn in parsed.history]


def test_the_result_is_always_a_shape_the_messages_api_accepts():
    # The property, stated once over a deliberately hostile input: starts
    # with a visitor turn, alternates, ends ready for the question to be
    # appended as the next user turn, and carries no empty content.
    turns = ask(
        ("assistant", "Hi!"),
        ("assistant", "Anything I can help with?"),
        ("visitor", "   "),
        ("visitor", "refunds?"),
        ("assistant", "Within 14 days."),
        ("visitor", "and shipping?"),
    )

    assert turns, "a usable conversation must not be emptied"
    assert turns[0][0] == "visitor"
    assert turns[-1][0] == "assistant"
    assert all(text.strip() for _, text in turns)
    roles = [role for role, _ in turns]
    assert all(a != b for a, b in zip(roles, roles[1:]))


def test_a_leading_assistant_turn_is_dropped():
    # A greeting bubble is an assistant turn with nothing before it. It is
    # the first thing every conversation has, and it is a 400.
    assert ask(("assistant", "Hi!"), ("visitor", "refunds?"), ("assistant", "14 days.")) == [
        ("visitor", "refunds?"),
        ("assistant", "14 days."),
    ]


def test_the_offer_that_follows_an_answer_does_not_become_two_turns():
    # What the bundled client actually sends on the fourth question: the
    # escalation offer is appended straight after the answer, with no
    # visitor turn between them.
    assert ask(
        ("visitor", "refunds?"),
        ("assistant", "Within 14 days."),
        ("assistant", "Would you like me to pass this to the team?"),
    ) == [
        ("visitor", "refunds?"),
        ("assistant", "Within 14 days.\n\nWould you like me to pass this to the team?"),
    ]


def test_a_trailing_visitor_turn_is_dropped_because_the_question_follows_it():
    # The question is appended as a user turn after all of these, so a
    # history ending on the visitor would put two user turns together.
    assert ask(("visitor", "refunds?"), ("assistant", "14 days."), ("visitor", "hello?")) == [
        ("visitor", "refunds?"),
        ("assistant", "14 days."),
    ]


def test_a_conversation_of_only_assistant_turns_is_emptied_not_sent():
    # The cheapest deliberate 400 there is, and the one that opens the
    # breaker: five of these and the workspace loses AI entirely.
    assert ask(("assistant", "x"), ("assistant", "y")) == []


def test_blank_turns_never_reach_the_model():
    assert ask(("visitor", "  \n "), ("visitor", "refunds?"), ("assistant", "14 days.")) == [
        ("visitor", "refunds?"),
        ("assistant", "14 days."),
    ]


def test_merging_happens_before_the_window_so_the_window_still_alternates():
    # Six turns arrive as three merged pairs; the cap must not slice a
    # merged conversation back into a non-alternating one.
    turns = ask(
        ("visitor", "one"),
        ("visitor", "two"),
        ("assistant", "three"),
        ("assistant", "four"),
        ("visitor", "five"),
        ("assistant", "six"),
    )
    roles = [role for role, _ in turns]
    assert all(a != b for a, b in zip(roles, roles[1:]))
    assert turns[0] == ("visitor", "one\n\ntwo")


def test_the_turn_cap_still_holds():
    long_conversation = []
    for index in range(20):
        long_conversation.append(("visitor", f"q{index}"))
        long_conversation.append(("assistant", f"a{index}"))

    assert len(ask(*long_conversation)) == HISTORY_MAX_TURNS


def test_a_merged_turn_is_still_clipped():
    # Merging must not become a way to smuggle past the per-turn cap by
    # sending the same role twice.
    half = "x" * HISTORY_TURN_MAX_CHARS
    turns = ask(("visitor", half), ("visitor", half), ("assistant", "ok"))

    assert len(turns[0][1]) == HISTORY_TURN_MAX_CHARS


@pytest.mark.parametrize(
    "history",
    [
        [],
        [("visitor", "only me")],
        [("assistant", "only me")],
    ],
)
def test_degenerate_histories_do_not_raise(history):
    # A visitor must never be blocked by the shape of their own
    # conversation -- this truncates, it does not 422.
    ask(*history)
