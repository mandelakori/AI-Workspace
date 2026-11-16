from .model import Quote, QuoteRequest
from .policy import base_rate_cents


def quote(request: QuoteRequest) -> Quote:
    base = base_rate_cents(request.grams)
    return Quote(base_cents=base, total_cents=base)
