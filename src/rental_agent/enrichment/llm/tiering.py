"""Bounded Terra→Sol tiering policy (03 §10.5, 08 §19.1, owner decision B5).

Attempt sequence, strictly bounded:

1. One default-tier (Terra) call.
2. One repair call on syntactic/schema failure only.
3. One flagship (Sol) escalation — only when the default output repeatedly fails
   validation or a validator reports unresolved material conflict.
4. Terminal failure flagged for human review. Never loop.

Validation is caller-supplied (schema/business rules); this class owns only the
attempt/escalation bookkeeping so every task type shares one bounded policy.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from rental_agent.config.logging import get_logger
from rental_agent.contracts import enums as e
from rental_agent.contracts.providers import LlmExecutor, LlmTaskRequest, LlmTaskResult

log = get_logger(__name__)

Validator = Callable[[LlmTaskRequest, LlmTaskResult], str | None]
"""Returns None when output is acceptable, else a rejection reason code."""


@dataclass
class TieredOutcome:
    result: LlmTaskResult
    tier_used: e.ModelTier
    attempts: list[dict[str, str]] = field(default_factory=list)
    needs_human_review: bool = False


class TieredLlmExecutor:
    """Composes default and flagship executors under the bounded policy."""

    interface_version = "1.0.0"

    def __init__(
        self,
        default: LlmExecutor,
        flagship: LlmExecutor,
        *,
        validator: Validator | None = None,
    ) -> None:
        self._default = default
        self._flagship = flagship
        self._validator = validator
        self.provider_code = getattr(default, "provider_code", "unknown")

    def execute_tiered(self, request: LlmTaskRequest) -> TieredOutcome:
        attempts: list[dict[str, str]] = []

        def attempt(
            executor: LlmExecutor, tier: e.ModelTier, label: str
        ) -> tuple[LlmTaskResult, str | None]:
            tier_request = request.model_copy(update={"tier": tier})
            result = executor.execute(tier_request)
            rejection: str | None
            if result.status is not e.ModelExecutionStatus.SUCCEEDED:
                rejection = result.error_code or "EXECUTION_FAILED"
            elif self._validator is not None:
                rejection = self._validator(tier_request, result)
            else:
                rejection = None
            attempts.append(
                {"attempt": label, "tier": tier.value, "rejection": rejection or "ACCEPTED"}
            )
            return result, rejection

        # 1. Initial default-tier call.
        result, rejection = attempt(self._default, e.ModelTier.DEFAULT_HOSTED, "default")
        if rejection is None:
            return TieredOutcome(
                result=result, tier_used=e.ModelTier.DEFAULT_HOSTED, attempts=attempts
            )

        # 2. One repair call for syntactic/schema failure only.
        if rejection in ("LLM_SCHEMA_FAILURE", "EMPTY_OUTPUT"):
            result, rejection = attempt(self._default, e.ModelTier.DEFAULT_HOSTED, "repair")
            if rejection is None:
                return TieredOutcome(
                    result=result, tier_used=e.ModelTier.DEFAULT_HOSTED, attempts=attempts
                )

        # 3. One flagship escalation (documented trigger: default repeatedly
        #    failed validation or could not resolve a material conflict).
        log.info("flagship_escalation", task_type=request.task_type, trigger=rejection)
        result, rejection = attempt(self._flagship, e.ModelTier.FLAGSHIP_ESCALATION, "flagship")
        if rejection is None:
            return TieredOutcome(
                result=result, tier_used=e.ModelTier.FLAGSHIP_ESCALATION, attempts=attempts
            )

        # 4. Terminal: unresolved cases reach human review, never a retry loop.
        failed = (
            result
            if result.status is not e.ModelExecutionStatus.SUCCEEDED
            else LlmTaskResult(
                status=e.ModelExecutionStatus.FAILED,
                model_id=result.model_id,
                error_code=rejection,
            )
        )
        return TieredOutcome(
            result=failed,
            tier_used=e.ModelTier.FLAGSHIP_ESCALATION,
            attempts=attempts,
            needs_human_review=True,
        )


def build_tiered_executor_from_settings(settings) -> TieredLlmExecutor:
    """Factory wiring Terra/Sol from typed configuration (never hard-coded IDs)."""
    from rental_agent.enrichment.llm.openai_executor import OpenAiLlmExecutor

    providers = settings.providers
    api_key = providers.openai_api_key.get_secret_value() if providers.openai_api_key else None
    default = OpenAiLlmExecutor(
        providers.llm_default_model_id,
        providers.llm_default_reasoning_effort,
        api_key=api_key,
    )
    flagship = OpenAiLlmExecutor(
        providers.llm_flagship_model_id,
        providers.llm_flagship_reasoning_effort,
        api_key=api_key,
    )
    return TieredLlmExecutor(default, flagship)
