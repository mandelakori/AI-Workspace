"""Experimental pinned Pi SDK adapter using the common isolated stage and MCP."""
from dataclasses import dataclass
import json
from pathlib import Path
from time import monotonic, time
from typing import ClassVar

from .execution_context import ExecutionContext, ResourcePolicy
from .harness import OpenCode, mcp_catalog, request_options, tool_command
from .harness_contracts import admit
from .inference import Inference
from .process import environment, executable, run
from .provider_gate import ProviderGate, finish_execution, CleanupFailure
from .trial_budget import write

VERSION = '1.6.0'


def pi_path(configured: str, state: Path) -> Path | None:
    root=Path(configured).resolve() if configured else state/'pi-dependency/node_modules/@earendil-works/pi-coding-agent'
    try:
        package=json.loads((root/'package.json').read_bytes())
        if (package['name']=='@earendil-works/pi-coding-agent' and package['version']==VERSION
                and (root/'dist/index.js').is_file() and executable('node')):
            return root.resolve()
    except (OSError,ValueError,KeyError):pass
    return None


@dataclass(frozen=True)
class Pi(OpenCode):
    sdk: Path
    keep_recent_tokens: int = 2048
    adapter: ClassVar[str] = 'pi'

    def run_session(self, profile, task, work, artifacts, prompt, timeout, tool_spec, stop):
        started=monotonic()
        if task.mode!='engineering' or not tool_spec:
            raise ValueError('Pi supports only scoped engineering sessions')
        if pi_path(str(self.sdk),self.sdk) is None:
            raise ValueError('Pi SDK version/inventory mismatch; no inference started')
        if not 0<=self.keep_recent_tokens<=profile.context:
            raise ValueError('invalid Pi context-retention setting')
        admit('pi',artifacts)
        config=json.loads(tool_spec.read_bytes())
        context=ExecutionContext(tool_spec)
        context.initialize(ResourcePolicy(**config.get('resources',{})))
        catalog=mcp_catalog(tool_spec,artifacts/'catalog-home',min(3,timeout),stop)
        write(artifacts/'mcp-catalog.json',catalog)
        deadline=started+timeout
        env=environment(artifacts/'harness-home')
        try:
            with ProviderGate(profile.endpoint,profile.model,Inference(profile).key(),artifacts,deadline,
                              context=context,pi_compaction=True) as gate:
                spec={'sdk':str(self.sdk),'workspace':str(work),'home':env['HOME'],'endpoint':gate.endpoint,
                      'model':profile.model,'context':profile.context,'output_tokens':profile.output_tokens,
                      'deadline':time()+max(0,deadline-monotonic()),'keep_recent_tokens':self.keep_recent_tokens,
                      'catalog':catalog['tools'],'command':tool_command(tool_spec),
                      'request_options':request_options(profile),'prompt':prompt}
                write(artifacts/'pi-settings.json',spec)
                result=run([self.binary,str(Path(__file__).parent/'pi/bridge.mjs')],work,
                           max(0,deadline-monotonic()),env|{'AIWORK_PI_TOKEN':gate.token},stop,
                           stdin=json.dumps(spec).encode(),output_limit=8*1024*1024,
                           stdout_path=artifacts/'agent-live.jsonl')
            # run() returns after its owned job and pipe readers are closed.
            write(artifacts/'catalog-readiness.json',{'ready':any(r['passed'] for r in gate.receipts),'owned':True,
                  'private_server':False,'sdk':VERSION,'cleanup_passed':True})
            with context.state() as state:
                state['seconds']['cleanup']=None  # Charged in total; not separately timed by run().
            return finish_execution('pi',gate,result,context,artifacts,started,True)
        except (OSError,ValueError,RuntimeError) as error:
            write(artifacts/'execution-receipt.json',{'schema':1,'adapter':'pi',
                  'status':'cleanup_failure' if isinstance(error,CleanupFailure) else 'harness_failure',
                  'raw_exit_code':None,'elapsed':monotonic()-started,'timed_out':False,'cleanup_passed':False,
                  'provider_gate_passed':False,'independent_verification':'not_started',
                  'error_class':type(error).__name__})
            raise
