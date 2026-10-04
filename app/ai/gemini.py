"""Thin wrapper around the google-genai SDK. Every request goes through `GeminiVision.call()`, which:

1. refuses the call if the budget is already spent (budget guard),
2. refuses the call if the model has no recorded price (no silent $0 costs),
3. sends the image as inline bytes — never a filename or path,
4. validates the answer with the caller's parser,
5. writes exactly one cost-log row per request, whatever the outcome
   (ok / invalid_output / rate_limited / error).

The SDK's own retries are switched off (attempts=1): a retry hidden inside the SDK would be a real,
billable request with no cost row. Retrying is the worker's job, where it is visible and logged.
"""

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Generic, Protocol, TypeVar

from google import genai
from google.genai import errors, types

from app.ai.pacing import Pacer
from app.ai.pricing import cost_usd, price_for
from app.ai.prompts import VISION_TAGGING_PROMPT
from app.config import Settings
from app.domain.vision import ImageTags

T = TypeVar("T")

MAX_STORED_TEXT = 4000  # chars of model output / error kept in the cost log


# --- What the wrapper reports back --------------------------------------------------------------

class BudgetExceeded(Exception):
    """Total recorded spend already reached AI_BUDGET_USD; no request was sent."""


class RateLimited(Exception):
    """429 RESOURCE_EXHAUSTED. retry_after is the server's suggested wait, if it sent one."""

    def __init__(self, retry_after: float | None, message: str):
        super().__init__(message)
        self.retry_after = retry_after


class InvalidOutput(Exception):
    """The model answered, but the answer failed validation. raw_text is kept for inspection."""

    def __init__(self, raw_text: str | None, reason: str):
        super().__init__(reason)
        self.raw_text = raw_text


class GeminiCallError(Exception):
    """Any other failure (server error, network, blocked response, ...)."""


# --- Cost log interface (implemented by the DB repository; faked in tests) -----------------------

@dataclass
class CallRecord:
    purpose: str
    model: str
    outcome: str  # ok | invalid_output | rate_limited | error
    job_id: int | None = None
    owner_type: str | None = None
    owner_id: int | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    cost_usd: Decimal = Decimal(0)
    latency_ms: int | None = None
    response_text: str | None = None
    error: str | None = None


class CostLog(Protocol):
    def total_spent_usd(self) -> Decimal: ...

    def record(self, entry: CallRecord) -> None: ...


@dataclass
class Parsed(Generic[T]):
    """A validated answer plus the exact text the model sent (kept for inspection/auditing)."""

    value: T
    raw_text: str


@dataclass
class CallContext:
    """Who the call is for — so every cost row is attributed to a job and an image/post."""

    purpose: str
    job_id: int | None = None
    owner_type: str | None = None
    owner_id: int | None = None


# --- Helpers ------------------------------------------------------------------------------------

def inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Pydantic puts enums under "$defs" and points to them with "$ref". Gemini's schema support
    is partial, so we substitute every $ref with the definition itself and drop $defs."""
    defs = schema.get("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(defs[node["$ref"].split("/")[-1]])
            return {k: resolve(v) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    return resolve(schema)


IMAGE_TAGS_SCHEMA = inline_refs(ImageTags.model_json_schema())


def retry_after_seconds(error: errors.APIError) -> float | None:
    """Find google.rpc.RetryInfo's retryDelay (e.g. "37s") anywhere in the error details."""
    match = re.search(r'"retryDelay":\s*"([\d.]+)s"', json.dumps(error.details, default=str))
    return float(match.group(1)) if match else None


def make_client(settings: Settings) -> genai.Client:
    if settings.gemini_api_key is None:
        raise GeminiCallError("GEMINI_API_KEY is not set (add it to .env)")
    return genai.Client(
        api_key=settings.gemini_api_key.get_secret_value(),
        http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)),
    )


def _clip(text: str | None) -> str | None:
    return None if text is None else text[:MAX_STORED_TEXT]


# --- The wrapper --------------------------------------------------------------------------------

class GeminiVision:
    def __init__(
        self,
        client: Any,
        model: str,
        cost_log: CostLog,
        budget_usd: float,
        pacer: Pacer | None = None,
    ):
        self._client = client
        self._model = model
        self._cost_log = cost_log
        self._budget = Decimal(str(budget_usd))
        self._pacer = pacer

    @property
    def model(self) -> str:
        return self._model

    def tag_image(self, image_bytes: bytes, ctx: CallContext) -> Parsed[ImageTags]:
        """Classify one image. Takes raw bytes only, so a filename has no way into the request."""
        return self.call(
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                VISION_TAGGING_PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=IMAGE_TAGS_SCHEMA,
            ),
            parse=ImageTags.model_validate_json,
            ctx=ctx,
        )

    def call(
        self,
        contents: list[Any],
        config: types.GenerateContentConfig,
        parse: Callable[[str], T],
        ctx: CallContext,
    ) -> Parsed[T]:
        spent = self._cost_log.total_spent_usd()
        if spent >= self._budget:
            raise BudgetExceeded(f"AI budget reached: ${spent:.4f} spent of ${self._budget:.2f}")
        price_for(self._model)  # raises UnknownModelPrice before anything is sent
        if self._pacer is not None:
            self._pacer.wait()  # every request, retries included, respects GEMINI_RPM

        record = CallRecord(
            purpose=ctx.purpose, model=self._model, outcome="error", job_id=ctx.job_id,
            owner_type=ctx.owner_type, owner_id=ctx.owner_id,
        )
        started = time.monotonic()
        try:
            response = self._client.models.generate_content(
                model=self._model, contents=contents, config=config
            )
        except errors.APIError as e:
            record.latency_ms = int((time.monotonic() - started) * 1000)
            record.error = _clip(str(e))
            if e.code == 429:
                record.outcome = "rate_limited"
                self._cost_log.record(record)
                raise RateLimited(retry_after_seconds(e), str(e)) from e
            self._cost_log.record(record)
            raise GeminiCallError(str(e)) from e
        except Exception as e:  # network errors, timeouts, ...
            record.latency_ms = int((time.monotonic() - started) * 1000)
            record.error = _clip(f"{type(e).__name__}: {e}")
            self._cost_log.record(record)
            raise GeminiCallError(record.error) from e

        record.latency_ms = int((time.monotonic() - started) * 1000)
        usage = response.usage_metadata
        if usage is not None:
            record.input_tokens = usage.prompt_token_count or 0
            record.output_tokens = usage.candidates_token_count or 0
            record.thinking_tokens = usage.thoughts_token_count or 0
        record.cost_usd = cost_usd(
            self._model, record.input_tokens, record.output_tokens, record.thinking_tokens
        )
        text = response.text  # None when the model returned no text (e.g. blocked)
        record.response_text = _clip(text)

        try:
            if text is None:
                raise ValueError("model returned no text")
            parsed = parse(text)
        except ValueError as e:  # pydantic.ValidationError is a ValueError
            record.outcome = "invalid_output"
            record.error = _clip(str(e))
            self._cost_log.record(record)
            raise InvalidOutput(text, record.error) from e

        record.outcome = "ok"
        self._cost_log.record(record)
        return Parsed(value=parsed, raw_text=text)
