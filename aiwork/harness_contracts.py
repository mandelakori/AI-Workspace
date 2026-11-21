"""Fail-closed adapter admission; declared capabilities are not live certification."""
from dataclasses import asdict, dataclass
from pathlib import Path

from .trial_budget import write


@dataclass(frozen=True)
class Capabilities:
    scoped_tools: bool = False
    exact_hash_editor: bool = False
    provider_catalog_gate: bool = False
    persistent_contract: bool = False
    context_visibility: bool = False
    durable_resource_limits: bool = False
    owned_cleanup: bool = False


ADAPTERS = {
    'opencode': Capabilities(True, True, True, True, True, True, True),
    # Existing Qwen adapter uses native edit/write_file, and has no provider gate.
    'qwen': Capabilities(scoped_tools=True, owned_cleanup=True),
    'pi': Capabilities(), 'mini-swe-agent': Capabilities(), 'deepseek-harness': Capabilities(),
}


def admit(name: str, artifacts: Path) -> dict:
    offered = asdict(ADAPTERS.get(name, Capabilities()))
    missing = [key for key, value in offered.items() if not value]
    receipt = {'schema': 1, 'adapter': name, 'required': list(offered), 'declared': offered,
               'missing': missing, 'admitted': not missing,
               'verification': 'declared; provider-facing gate and owned cleanup still required per session'}
    write(artifacts / 'harness-capabilities.json', receipt)
    if missing:
        write(artifacts / 'execution-receipt.json', {'schema':1, 'adapter':name,
              'status':'capability_rejected', 'raw_exit_code':None, 'elapsed':0,
              'timed_out':False, 'cleanup_passed':None, 'provider_gate_passed':False,
              'independent_verification':'not_started'})
        raise ValueError(f'{name} cannot satisfy engineering contract: {", ".join(missing)}')
    return receipt
