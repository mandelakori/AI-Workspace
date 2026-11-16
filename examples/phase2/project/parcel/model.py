from dataclasses import dataclass


@dataclass(frozen=True)
class QuoteRequest:
    grams: int

    def __post_init__(self):
        if type(self.grams) is not int or self.grams < 1:
            raise ValueError("grams must be a positive integer")


@dataclass(frozen=True)
class Quote:
    base_cents: int
    total_cents: int
