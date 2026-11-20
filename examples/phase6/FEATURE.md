# Click ISODateTime parameter type

Baseline: pallets/click 8.3.2, commit 052c006033729bbb422cbdad0c4fee988ecb5aa5.

Add a public `click.ISODateTime` parameter type, also available as
`click.types.ISODateTime`, for applications accepting ISO 8601 dates and timestamps
with fractional seconds and timezone offsets. This is an additive API. Preserve
the existing `DateTime` type and its configurable strptime semantics.

The constructor accepts keyword arguments `require_timezone=False` and
`normalize_to_utc=False`. Default string parsing follows the running Python's
`datetime.fromisoformat` grammar, including calendar dates, datetime separators,
fractions, signed offsets and trailing Z. Successful conversion returns a datetime.
An existing datetime is returned by identity unless normalization is requested.

`require_timezone=True` rejects values whose UTC offset is None, including naive
datetime objects. `normalize_to_utc=True` likewise requires an aware value and
returns the same instant as a UTC-aware datetime. Both flags can be combined.
Neither mode silently attaches a timezone to a naive input.

Malformed or unsupported inputs raise Click BadParameter through the normal
parameter conversion/error path. Diagnostics mention ISO 8601, and timezone
policy failures mention timezone. CLI failures must have the normal parameter
hint and usage exit code 2. No raw ValueError or TypeError may escape conversion.

The type has name `iso_datetime`, metavar `ISO_DATETIME`, repr `ISODateTime`.
Its to_info_dict includes both constructor flags alongside the normal ParamType
metadata, so command introspection can describe the timezone policy.

Integrate with options, arguments, defaults, environment values and multiple
options using the existing Click conversion machinery. Add focused tests in
tests/test_iso_datetime.py, covering at least six cases including CLI integration.
Document usage, both flags, error behavior and compatibility with DateTime in
docs/parameter-types.md, and expose the type in docs/api.md.

Permitted edits: src/click/types.py, src/click/__init__.py,
tests/test_iso_datetime.py, docs/parameter-types.md, docs/api.md.
Existing tests and operator-owned public verifiers are read-only.

Implementation must be authored by the configured local open-weight worker.
Use the existing planner to assess decomposition. Preserve failed attempts and
rank candidates using the approved public corpus. Freeze before final sealed
acceptance. Sealed results must never be sent back for repair.
