"""FakeJevClient scripting, defaults, call recording, and outage simulation."""

from __future__ import annotations

from app.jev import (
    ChoiceAnswer,
    ChoiceQuestion,
    FakeJevClient,
    JevUnavailableError,
    NoulAnswer,
    NoulQuestion,
    ScoreAnswer,
    ScoreQuestion,
)


async def test_defaults_are_synthesized_per_question_type() -> None:
    fake = FakeJevClient()
    questions = {
        "choice": ChoiceQuestion(instructions="pick", criteria={"alpha": "A", "beta": "B"}),
        "score": ScoreQuestion(instructions="rate", criteria=["0", "1", "2", "3", "4"]),
        "noul": NoulQuestion(instructions="decide"),
    }
    result = await fake.ask("state", questions)

    choice = result.answers["choice"]
    score = result.answers["score"]
    noul = result.answers["noul"]
    assert isinstance(choice, ChoiceAnswer)
    assert choice.choice == "alpha"
    assert choice.confidence == 0.9
    assert choice.probabilities == {"alpha": 0.9, "beta": 0.1}
    assert isinstance(score, ScoreAnswer)
    assert score.score == 2.0
    assert score.confidence == 0.9
    assert isinstance(noul, NoulAnswer)
    assert noul.noul == 0.9


async def test_static_answers_and_queued_answers_win_over_defaults() -> None:
    fake = FakeJevClient({"q": NoulAnswer(noul=0.2)})
    assert isinstance(
        (await fake.ask("s", {"q": NoulQuestion(instructions="i")})).answers["q"], NoulAnswer
    )

    fake.queue("q", NoulAnswer(noul=0.6))
    fake.queue("q", NoulAnswer(noul=0.8))
    first = await fake.ask("s", {"q": NoulQuestion(instructions="i")})
    second = await fake.ask("s", {"q": NoulQuestion(instructions="i")})
    third = await fake.ask("s", {"q": NoulQuestion(instructions="i")})
    first_answer = first.answers["q"]
    second_answer = second.answers["q"]
    third_answer = third.answers["q"]
    assert isinstance(first_answer, NoulAnswer)
    assert isinstance(second_answer, NoulAnswer)
    assert isinstance(third_answer, NoulAnswer)
    assert first_answer.noul == 0.6
    assert second_answer.noul == 0.8
    assert third_answer.noul == 0.2


async def test_default_choice_override() -> None:
    fake = FakeJevClient()
    fake.default_choice("beta", confidence=0.7)
    questions = {"q": ChoiceQuestion(instructions="pick", criteria={"alpha": "A", "beta": "B"})}
    result = await fake.ask("state", questions)
    answer = result.answers["q"]
    assert isinstance(answer, ChoiceAnswer)
    assert answer.choice == "beta"
    assert answer.confidence == 0.7


async def test_fail_next_raises_once_then_recovers() -> None:
    fake = FakeJevClient()
    fake.fail_next(JevUnavailableError("down"))
    question = {"q": NoulQuestion(instructions="i")}

    try:
        await fake.ask("state", question)
    except JevUnavailableError:
        pass
    else:
        raise AssertionError("expected JevUnavailableError")

    result = await fake.ask("state", question)
    assert isinstance(result.answers["q"], NoulAnswer)
    assert len(fake.calls) == 2


async def test_calls_record_state_and_question_ids() -> None:
    fake = FakeJevClient()
    questions = {
        "first": NoulQuestion(instructions="i"),
        "second": ChoiceQuestion(instructions="i", criteria={"a": "A"}),
    }
    await fake.ask({"state": "object"}, questions)
    state, question_ids = fake.calls[0]
    assert state == {"state": "object"}
    assert question_ids == ["first", "second"]


async def test_usage_is_deterministic() -> None:
    fake = FakeJevClient()
    result = await fake.ask("12345", {"q": NoulQuestion(instructions="i")})
    assert result.usage.input_tokens == 5
    assert result.usage.output_tokens == 1
    assert result.raw_model == "fake-jev"
