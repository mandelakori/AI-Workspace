"""Deterministic context planning from operator-supplied measurements.

This module does not query or reconfigure inference services. Estimates must be
measured for the specific model/quantization/cache/offload configuration.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math


@dataclass(frozen=True)
class ContextMeasurements:
    model: str
    provenance: str
    supported_max: int
    available_vram_bytes: int
    available_ram_bytes: int
    resident_gpu_bytes: int
    resident_cpu_bytes: int
    kv_bytes_per_token: float
    kv_gpu_fraction: float
    prefill_tokens_per_second: float
    generation_tokens_per_second: float

    def __post_init__(self):
        numbers = [v for v in asdict(self).values() if isinstance(v, (int, float))]
        if (not self.model or not self.provenance or any(not math.isfinite(v) or v < 0 for v in numbers)
                or type(self.supported_max) is not int or self.supported_max < 1024
                or not 0 <= self.kv_gpu_fraction <= 1 or self.kv_bytes_per_token <= 0
                or self.prefill_tokens_per_second <= 0 or self.generation_tokens_per_second <= 0):
            raise ValueError('complete model-specific resource/context measurements required')


def plan_context(measurements: ContextMeasurements, *, candidates: tuple[int, ...],
                 hard_max: int, input_tokens: int, output_tokens: int, reserve_tokens: int,
                 deadline_seconds: float, headroom: float = .15) -> dict:
    """Choose the smallest feasible window, with memory and latency rejection reasons."""
    if (not candidates or len(candidates) > 64 or any(type(c) is not int or c < 1024 for c in candidates)
            or any(type(v) is not int or v < 0 for v in (hard_max, input_tokens, output_tokens, reserve_tokens))
            or not math.isfinite(deadline_seconds) or deadline_seconds <= 0
            or not 0 <= headroom < 1):
        raise ValueError('invalid bounded context policy')
    m = measurements
    expected_seconds = input_tokens / m.prefill_tokens_per_second + output_tokens / m.generation_tokens_per_second
    rows = []
    for window in sorted(set(candidates)):
        kv = window * m.kv_bytes_per_token
        gpu = m.resident_gpu_bytes + kv * m.kv_gpu_fraction
        cpu = m.resident_cpu_bytes + kv * (1-m.kv_gpu_fraction)
        reasons = []
        if window > min(hard_max, m.supported_max): reasons.append('operator/model maximum')
        if window < input_tokens + output_tokens + reserve_tokens: reasons.append('task context demand')
        if gpu > m.available_vram_bytes * (1-headroom): reasons.append('VRAM including KV cache')
        if cpu > m.available_ram_bytes * (1-headroom): reasons.append('RAM including CPU offload/cache')
        if expected_seconds > deadline_seconds: reasons.append('estimated prefill/generation deadline')
        rows.append({'context': window, 'estimated_gpu_bytes': gpu, 'estimated_cpu_bytes': cpu,
                     'estimated_seconds': expected_seconds, 'rejected': reasons})
    return {'schema': 1, 'model': m.model, 'provenance': m.provenance,
            'measurements': asdict(m), 'selected': next((r['context'] for r in rows if not r['rejected']), None),
            'candidates': rows, 'applied': False,
            'limitation': 'Planning estimate only. Validate backend residency and measured performance before applying.'}
