"""List prices used for cost tracking (USD per 1M tokens, paid "Standard" tier).

We run on the free tier, so actual spend is $0. We still record what each call *would* cost at
list price, so cost tracking and the budget guard are meaningful (and would be real on a paid key).

Every price records where it came from and when it was checked. A model with no entry here
cannot be called: pricing it at $0 would silently break cost tracking.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

PRICING_PAGE = "https://ai.google.dev/gemini-api/docs/pricing"
EMBEDDING_GA_POST = "https://developers.googleblog.com/gemini-embedding-available-gemini-api/"
PER_MILLION = Decimal(1_000_000)


@dataclass(frozen=True)
class Price:
    input_per_million: Decimal   # prompt tokens: text + image
    output_per_million: Decimal  # response tokens AND thinking tokens (billed at the same rate)
    source: str
    checked_on: date


PRICES: dict[str, Price] = {
    # Section "Gemini 3.5 Flash-Lite", Standard, paid tier: input "$0.30 (text / image / video /
    # audio)", output "$2.50" "including thinking tokens".
    "gemini-3.5-flash-lite": Price(Decimal("0.30"), Decimal("2.50"), PRICING_PAGE, date(2026, 10, 4)),
    # Section "Gemini 2.5 Flash", Standard, paid tier: input "$0.30 (text / image / video)",
    # output "$2.50" incl. thinking. Kept only as a configurable alternative (access is restricted).
    "gemini-2.5-flash": Price(Decimal("0.30"), Decimal("2.50"), PRICING_PAGE, date(2026, 10, 4)),
    # Not on the current pricing page; $0.15 per 1M input tokens per Google's GA announcement.
    # Embeddings have no output tokens. Used from Phase 3.
    "gemini-embedding-001": Price(Decimal("0.15"), Decimal("0"), EMBEDDING_GA_POST, date(2026, 10, 4)),
}


class UnknownModelPrice(Exception):
    pass


def price_for(model: str) -> Price:
    try:
        return PRICES[model]
    except KeyError:
        raise UnknownModelPrice(
            f"No list price recorded for model '{model}'. Add it to app/ai/pricing.py "
            f"(from {PRICING_PAGE}) before using it."
        ) from None


def cost_usd(model: str, input_tokens: int, output_tokens: int, thinking_tokens: int) -> Decimal:
    """input × input price + (output + thinking) × output price, all per 1M tokens."""
    price = price_for(model)
    return (
        Decimal(input_tokens) * price.input_per_million
        + Decimal(output_tokens + thinking_tokens) * price.output_per_million
    ) / PER_MILLION
