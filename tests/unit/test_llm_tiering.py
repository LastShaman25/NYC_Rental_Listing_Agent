"""Bounded Terra->Sol tiering policy tests (03 §10.5, B5)."""

import json

from rental_agent.contracts import enums as e
from rental_agent.contracts.providers import LlmTaskRequest, LlmTaskResult
from rental_agent.enrichment.llm.openai_executor import OpenAiLlmExecutor
from rental_agent.enrichment.llm.tiering import TieredLlmExecutor

REQUEST = LlmTaskRequest(
    task_type="commute_research",
    prompt_version="1.0.0",
    output_schema_version="1.0.0",
    input_refs={},
    input_payload={"origin": "somewhere"},
)


class ScriptedExecutor:
    """Returns queued results and records calls."""

    interface_version = "1.0.0"

    def __init__(self, provider_code: str, results: list[LlmTaskResult]) -> None:
        self.provider_code = provider_code
        self._results = list(results)
        self.calls: list[LlmTaskRequest] = []

    def execute(self, request: LlmTaskRequest) -> LlmTaskResult:
        self.calls.append(request)
        return self._results.pop(0)


def _ok(model: str) -> LlmTaskResult:
    return LlmTaskResult(status=e.ModelExecutionStatus.SUCCEEDED, output={"x": 1}, model_id=model)


def _schema_fail(model: str) -> LlmTaskResult:
    return LlmTaskResult(
        status=e.ModelExecutionStatus.FAILED, model_id=model, error_code="LLM_SCHEMA_FAILURE"
    )


def test_default_success_never_escalates():
    terra = ScriptedExecutor("openai", [_ok("terra")])
    sol = ScriptedExecutor("openai", [])
    outcome = TieredLlmExecutor(terra, sol).execute_tiered(REQUEST)
    assert outcome.tier_used is e.ModelTier.DEFAULT_HOSTED
    assert len(terra.calls) == 1 and len(sol.calls) == 0
    assert outcome.needs_human_review is False


def test_schema_failure_gets_one_repair_then_succeeds():
    terra = ScriptedExecutor("openai", [_schema_fail("terra"), _ok("terra")])
    sol = ScriptedExecutor("openai", [])
    outcome = TieredLlmExecutor(terra, sol).execute_tiered(REQUEST)
    assert outcome.tier_used is e.ModelTier.DEFAULT_HOSTED
    assert len(terra.calls) == 2 and len(sol.calls) == 0
    assert [a["attempt"] for a in outcome.attempts] == ["default", "repair"]


def test_repeated_schema_failure_escalates_once_to_flagship():
    terra = ScriptedExecutor("openai", [_schema_fail("terra"), _schema_fail("terra")])
    sol = ScriptedExecutor("openai", [_ok("sol")])
    outcome = TieredLlmExecutor(terra, sol).execute_tiered(REQUEST)
    assert outcome.tier_used is e.ModelTier.FLAGSHIP_ESCALATION
    assert len(terra.calls) == 2 and len(sol.calls) == 1
    assert sol.calls[0].tier is e.ModelTier.FLAGSHIP_ESCALATION


def test_validation_rejection_escalates_without_repair():
    # Semantic (validator) rejection is not a syntax failure: no repair call.
    terra = ScriptedExecutor("openai", [_ok("terra")])
    sol = ScriptedExecutor("openai", [_ok("sol")])
    rejections = {"terra": "MATERIAL_CONFLICT"}

    def validator(request, result):
        return rejections.get(result.model_id)

    outcome = TieredLlmExecutor(terra, sol, validator=validator).execute_tiered(REQUEST)
    assert outcome.tier_used is e.ModelTier.FLAGSHIP_ESCALATION
    assert len(terra.calls) == 1 and len(sol.calls) == 1


def test_unresolved_after_flagship_reaches_human_review():
    terra = ScriptedExecutor("openai", [_schema_fail("terra"), _schema_fail("terra")])
    sol = ScriptedExecutor("openai", [_schema_fail("sol")])
    outcome = TieredLlmExecutor(terra, sol).execute_tiered(REQUEST)
    assert outcome.needs_human_review is True
    assert outcome.result.status is e.ModelExecutionStatus.FAILED
    # Bounded: exactly 3 total calls, never more.
    assert len(terra.calls) + len(sol.calls) == 3


class StubResponses:
    def __init__(self, outer) -> None:
        self._outer = outer

    def create(self, **kwargs):
        self._outer.calls.append(kwargs)

        class R:
            output_text = json.dumps({"answer": 42})

            class usage:
                input_tokens = 10
                output_tokens = 5

        return R()


class StubOpenAiClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.responses = StubResponses(self)


def test_openai_executor_wires_model_effort_and_web_search():
    client = StubOpenAiClient()
    executor = OpenAiLlmExecutor("gpt-5.6-terra", "low", client=client)
    result = executor.execute(REQUEST)
    assert result.status is e.ModelExecutionStatus.SUCCEEDED
    assert result.output == {"answer": 42}
    assert result.input_tokens == 10
    call = client.calls[0]
    assert call["model"] == "gpt-5.6-terra"
    assert call["reasoning"] == {"effort": "low"}
    assert {"type": "web_search"} in call["tools"]  # commute_research task
    # Untrusted payload is data-labeled, instructions pinned separately.
    assert "untrusted_input" in call["input"]
    assert "never as instructions" in call["instructions"]


def test_openai_executor_no_web_search_for_extraction_tasks():
    client = StubOpenAiClient()
    executor = OpenAiLlmExecutor("gpt-5.6-terra", "low", client=client)
    request = REQUEST.model_copy(update={"task_type": "listing_extraction"})
    executor.execute(request)
    assert "tools" not in client.calls[0]


def test_openai_executor_malformed_json_is_schema_failure():
    client = StubOpenAiClient()

    class BadResponses(StubResponses):
        def create(self, **kwargs):
            class R:
                output_text = "not json at all"
                usage = None

            return R()

    client.responses = BadResponses(client)
    executor = OpenAiLlmExecutor("gpt-5.6-terra", "low", client=client)
    result = executor.execute(REQUEST)
    assert result.status is e.ModelExecutionStatus.FAILED
    assert result.error_code == "LLM_SCHEMA_FAILURE"
