"""Unit tests para JudgeDispatcher (US-1A-06-04-V2)."""

from __future__ import annotations

import pytest

from app.services.matching.judge_dispatcher import (
    DispatchResult,
    JudgeDispatcher,
    _MonthCounter,
)
from app.services.matching.vlm_judge import JudgeResult


class _FakeJudge:
    def __init__(self, result: JudgeResult, *, raises: Exception | None = None) -> None:
        self._result = result
        self._raises = raises
        self.calls = 0

    async def judge(self, *, canonical_image_url: str, candidate_image_url: str, context=None):
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return self._result


@pytest.fixture(autouse=True)
def _enable_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")


@pytest.mark.asyncio
async def test_disabled_when_live_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MT_LIVE_NETWORK", "false")
    d = JudgeDispatcher(backends={"openai": _FakeJudge(JudgeResult("match", 0.9, "x"))})
    res = await d.dispatch(canonical_image_url="a", candidate_image_url="b")
    assert res.verdict == "uncertain"
    assert res.fallback_reason == "live_disabled"


@pytest.mark.asyncio
async def test_no_backend_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    d = JudgeDispatcher()
    res = await d.dispatch(canonical_image_url="a", candidate_image_url="b")
    assert res.verdict == "uncertain"
    assert res.fallback_reason == "no_backend"


@pytest.mark.asyncio
async def test_single_backend_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUDGE_BACKEND", "openai")
    fake = _FakeJudge(JudgeResult("match", 0.92, "looks identical"))
    d = JudgeDispatcher(backends={"openai": fake})
    res = await d.dispatch(canonical_image_url="a", candidate_image_url="b")
    assert res.verdict == "match"
    assert res.confidence == pytest.approx(0.92)
    assert res.backends_used == ["openai"]
    assert fake.calls == 1


@pytest.mark.asyncio
async def test_consensus_both_agree(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUDGE_BACKEND", "both")
    f1 = _FakeJudge(JudgeResult("match", 0.9, "openai says match"))
    f2 = _FakeJudge(JudgeResult("match", 0.8, "anthropic says match"))
    d = JudgeDispatcher(backends={"openai": f1, "anthropic": f2})
    res = await d.dispatch(canonical_image_url="a", candidate_image_url="b")
    assert res.verdict == "match"
    assert res.confidence == pytest.approx(0.85)
    assert not res.disagreement
    assert set(res.backends_used) == {"openai", "anthropic"}


@pytest.mark.asyncio
async def test_consensus_disagreement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUDGE_BACKEND", "both")
    f1 = _FakeJudge(JudgeResult("match", 0.9, "yes"))
    f2 = _FakeJudge(JudgeResult("reject", 0.7, "no"))
    d = JudgeDispatcher(backends={"openai": f1, "anthropic": f2})
    res = await d.dispatch(canonical_image_url="a", candidate_image_url="b")
    assert res.disagreement is True
    assert res.verdict == "uncertain"
    assert res.confidence == pytest.approx(0.7)


@pytest.mark.asyncio
async def test_one_backend_fails_other_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUDGE_BACKEND", "both")
    f1 = _FakeJudge(JudgeResult("match", 0.0, ""), raises=RuntimeError("boom"))
    f2 = _FakeJudge(JudgeResult("drift", 0.6, "minor diff"))
    d = JudgeDispatcher(backends={"openai": f1, "anthropic": f2})
    res = await d.dispatch(canonical_image_url="a", candidate_image_url="b")
    assert res.verdict == "drift"
    assert res.backends_used == ["anthropic"]


@pytest.mark.asyncio
async def test_all_backends_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUDGE_BACKEND", "both")
    f1 = _FakeJudge(JudgeResult("match", 0.0, ""), raises=RuntimeError("a"))
    f2 = _FakeJudge(JudgeResult("match", 0.0, ""), raises=RuntimeError("b"))
    d = JudgeDispatcher(backends={"openai": f1, "anthropic": f2})
    res = await d.dispatch(canonical_image_url="a", candidate_image_url="b")
    assert res.verdict == "uncertain"
    assert res.fallback_reason == "all_failed"


@pytest.mark.asyncio
async def test_cost_cap_breaker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUDGE_BACKEND", "openai")
    counter = _MonthCounter()
    counter.add(50.0)
    d = JudgeDispatcher(
        backends={"openai": _FakeJudge(JudgeResult("match", 0.9, "x"))},
        cap_monthly_usd=50.0,
        cost_counter=counter,
    )
    res = await d.dispatch(canonical_image_url="a", candidate_image_url="b")
    assert res.fallback_reason == "cost_cap"
    assert res.verdict == "uncertain"


@pytest.mark.asyncio
async def test_invalid_backend_flag_falls_back_to_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUDGE_BACKEND", "garbage")
    fake = _FakeJudge(JudgeResult("match", 0.95, "ok"))
    d = JudgeDispatcher(backends={"openai": fake, "anthropic": _FakeJudge(JudgeResult("reject", 0.9, "x"))})
    res = await d.dispatch(canonical_image_url="a", candidate_image_url="b")
    assert res.verdict == "match"
    assert res.backends_used == ["openai"]
