def page(rows, *, after=None, limit=20):
    """Return records ordered by (timestamp, ID) and the next cursor."""
    ordered = sorted(rows, key=lambda row: (row["timestamp"], row["id"]))
    if after is not None:
        ordered = [row for row in ordered if row["timestamp"] > after[0]]
    result = ordered[:limit]
    cursor = (result[-1]["timestamp"], result[-1]["id"]) if len(ordered) >= limit and result else None
    return result, cursor
