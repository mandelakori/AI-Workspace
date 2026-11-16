def base_rate_cents(grams: int) -> int:
    return 250 + ((grams + 99) // 100) * 15
