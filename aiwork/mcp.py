"""Task-local MCP stdio server exposing one operator-defined public check."""
from __future__ import annotations

import json
import hashlib
import sys
from pathlib import Path
from time import time, monotonic

from .changes import delta, git_patch, validate_changes
from .schema import Check
from .verify import pipeline
from .workspace import contained, ignore, inventory, snapshot
from .index import python_symbols
from .source_edit import apply_edit, EditRejected
from .execution_context import ExecutionContext, ResourcePolicy, excerpt_key


def reserve_trial_call(spec: Path, limit: int) -> int:
    """Reconnects cannot reset a measured session's public-tool allowance."""
    from .lock import file_lock
    from .trial_budget import write
    path = spec.with_name("trial-tool-calls.json")
    with file_lock(path.with_suffix(".lock")):
        used = json.loads(path.read_bytes())["used"] if path.exists() else 0
        if used >= limit:
            raise ValueError("measured public-tool budget exhausted")
        write(path, {"used": used + 1})
        return used + 1


def focus(workspace: Path, args: dict) -> dict:
    """Read a bounded public source window without exporting a whole file."""
    if (not isinstance(args, dict) or set(args) - {"path", "line", "symbol", "query"}
            or not isinstance(args.get("path"), str)
            or type(args.get("line", 1)) is not int or args.get("line", 1) < 1
            or not isinstance(args.get("symbol", ""), str) or len(args.get("symbol", "")) > 160
            or not isinstance(args.get("query", ""), str) or len(args.get("query", "")) > 160
            or args.get("symbol") and args.get("query")):
        raise ValueError("focus requires a relative path and optional line or Python symbol")
    name = args["path"]
    if any(ignore(part) for part in name.split("/")):
        raise ValueError("excluded inspection path")
    path = contained(workspace, name)
    if not path.is_file() or path.stat().st_size > 256 * 1024:
        raise ValueError("inspection requires a text file no larger than 256 KiB")
    with path.open("rb") as stream:
        data = stream.read(256 * 1024 + 1)
    if len(data) > 256 * 1024:
        raise ValueError("inspection source grew beyond 256 KiB")
    text = data.decode("utf-8")
    lines = text.splitlines(keepends=True)
    first = args.get("line", 1)
    end = len(lines)
    definitions = []
    if path.suffix == ".py":
        try:
            definitions = python_symbols(text)
        except (SyntaxError, RecursionError, ValueError):
            if args.get("symbol"):
                raise ValueError("symbol inspection requires parseable Python") from None
    selected_symbol = args.get("symbol", "")
    query = args.get("query", "").strip().casefold()
    matching = [d for d in definitions if query in d['symbol'].casefold()] if query else []
    if query:
        if matching:
            selected_symbol = min(matching, key=lambda d: (d['symbol'].casefold()!=query, len(d['symbol']), d['line']))['symbol']
        else:
            matches = [i for i, line in enumerate(lines, 1) if query in line.casefold()]
            if not matches:
                raise ValueError("query did not match; open the path to discover symbols")
            first = max(1, matches[0]-3)
    if selected_symbol:
        found = [(d['line'],d['end_line']) for d in definitions if d['symbol']==selected_symbol]
        if len(found) != 1:
            raise ValueError("Python symbol must match exactly once; use Class.method for methods")
        symbol_first, end = found[0]
        first = max(symbol_first, args.get("line", symbol_first))
        if first > end:
            raise ValueError("inspection line is past the selected symbol")
    if first > max(1, len(lines)):
        raise ValueError("inspection line is past EOF")
    selected = []
    size = 0
    for line in lines[first-1:min(end, first+59)]:
        width = len(line.encode("utf-8"))
        if size + width > 3000:
            break
        selected.append(line)
        size += width
    if not selected and lines:
        raise ValueError("source line exceeds the 3000-byte inspection budget")
    following = first + len(selected)
    outline = []
    candidates = matching or sorted(definitions, key=lambda d: ('.' in d['symbol'], d['kind']!='class', d['line']))
    for definition in candidates:
        if len(json.dumps([*outline, definition]).encode('utf-8')) > 1200 or len(outline)>=12:
            break
        outline.append(definition)
    return {"path": name, "sha256": hashlib.sha256(data).hexdigest(), "line": first,
            "source": "".join(selected), "next_line": following if following <= end else None,
            "total_lines": len(lines), "selected_symbol":selected_symbol, "symbols":outline,
            "symbols_truncated":len(outline)<len(candidates)}


def inspect_source(spec: Path, workspace: Path, args: dict) -> dict:
    """Suppress unchanged duplicate excerpts, including across MCP reconnects."""
    from .lock import file_lock
    from .trial_budget import write
    value=focus(workspace,args)
    key=excerpt_key(value)
    context = ExecutionContext(spec)
    managed = context.path.exists()
    if managed:
        epoch, duplicate = context.excerpt(key, value)
        value.update(context_epoch=epoch, evidence_key=key)
    path=spec.with_name('source-navigation.json')
    with file_lock(path.with_suffix('.lock')):
        if not managed:
            evidence=spec.parent/'source-excerpts';evidence.mkdir(exist_ok=True)
            if not (evidence/f'{key}.json').exists():write(evidence/f'{key}.json',value)
            value['evidence_key']=key
        history=json.loads(path.read_bytes()) if path.exists() else []
        if not managed:
            duplicate=key in history
        recovery=spec.with_name('edit-reinspection.json')
        if recovery.exists():
            permit=json.loads(recovery.read_bytes())
            if permit.get('path')==value['path'] and permit.get('sha256')==value['sha256'] and permit.get('remaining')==1:
                duplicate=False;permit['remaining']=0;write(recovery,permit)
                value['reinspection_after_edit_error']=True
        if not duplicate:
            history.append(key);write(path,history[-16:])
    if duplicate:
        value.update(source='',already_inspected=True,
                     navigation_hint='Unchanged excerpt already supplied. Select a listed symbol, use query or next_line, or edit and run a public check.')
    return value


def edit_failure(spec: Path, workspace: Path, roots: tuple[str, ...], args: dict, diagnostic: dict) -> dict:
    """Durable circuit breaker for equivalent failures on unchanged source.

    Changing insertion text/mode cannot repair an ambiguous/missing anchor.
    Reinspection is allowed but does not refund repetitions or tool budgets.
    """
    from .lock import file_lock
    from .trial_budget import write
    try:
        name=args['path'];validate_changes([name],roots)
        path=contained(workspace,name)
        with path.open('rb') as stream:data=stream.read(256*1024+1)
        if len(data)>256*1024:return diagnostic
        current=hashlib.sha256(data).hexdigest()
        if diagnostic.get('actual_sha256',current)!=current:return diagnostic
        identity={k:args.get(k) for k in ('path','expected_sha256','old','location')}
        if isinstance(identity['old'],str):identity['old']=identity['old'].replace('\r\n','\n')
        identity.update(source_sha256=current,code=diagnostic['code'])
        if diagnostic['code'] not in {'anchor_mismatch','ambiguous_anchor','invalid_anchor'}:
            identity.update(mode=args.get('mode'),new=args.get('new'))
        fingerprint=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    except (KeyError,ValueError,OSError,TypeError):return diagnostic
    ledger=spec.with_name('edit-recovery.json')
    with file_lock(ledger.with_suffix('.lock')):
        entries=json.loads(ledger.read_bytes()) if ledger.exists() else {}
        count=entries.get(fingerprint,0)+1;entries[fingerprint]=count;write(ledger,entries)
    value={'path':name,'actual_sha256':current,'focus_arguments':{'path':name,'line':1},
           **diagnostic,'failure_fingerprint':fingerprint,'equivalent_failures':count}
    if count>=3:
        value.update(original_code=diagnostic['code'],code='repeated_edit_failure',
            error='Repeated equivalent edit failure on unchanged source. Reinspect and use a DIFFERENT unique anchor or inspected location. Repeating again stops this session; reinspection does not reset this counter.')
    if count>=4:
        reason='repeated equivalent source-edit failures exhausted recovery'
        value.update(code='edit_recovery_exhausted',error=reason,recovery_exhausted=True)
        context=ExecutionContext(spec)
        if context.path.exists():
            with context.state() as state:
                state['exhausted']=state['exhausted'] or reason
                state['events'].append({'event':'edit_recovery_exhausted','fingerprint':fingerprint,'count':count,'epoch':state['epoch']})
    return value


def serve(spec_path: Path) -> None:
    config = json.loads(spec_path.read_text(encoding="utf-8"))
    checks = [Check.read(item) for item in config["checks"]]
    setup = tuple(Check.read(item) for item in config.get("setup", []))
    workspace = Path(config["workspace"])
    build = config.get("engineering", False)
    stop = Path(config["stop"]) if config.get("stop") else None
    baseline = Path(config["baseline"]) if build else None
    context = ExecutionContext(spec_path)
    if build and 'resources' in config:
        context.initialize(ResourcePolicy(**config['resources']))
    managed = build and context.path.exists()
    budget = config.get('resources', {}).get('operations', 16) if build else 6
    calls = 0
    for line in iter(lambda: sys.stdin.buffer.readline(32769), b""):
        if len(line) > 32768:
            return
        message = json.loads(line)
        if "id" not in message:
            continue
        method = message.get("method")
        response = {"jsonrpc": "2.0", "id": message["id"]}
        if method == "initialize":
            response["result"] = {
                "protocolVersion": "2025-03-26", "capabilities": {"tools": {}},
                "serverInfo": {"name": "aiwork", "version": "0.1.0"},
            }
        elif method == "ping":
            response["result"] = {}
        elif method == "tools/list":
            available = [{
                "name": "check", "description": "Run an approved public command by index in a disposable copy.",
                "inputSchema": {"type": "object", "properties": {
                    "index": {"type": "integer", "minimum": 0, "maximum": len(checks) - 1},
                }, "required": ["index"], "additionalProperties": False},
            }] if checks else []
            if build:
                available.append({"name": "focus", "description": "Discover qualified symbols and read bounded source (60 lines, 3000 UTF-8 bytes). query is a case-insensitive literal substring of a qualified symbol or source line. Use symbol=Class.method for exact lookup. Follow next_line; unchanged repeated excerpts are suppressed.",
                                  "inputSchema": {"type": "object", "properties": {
                                      "path": {"type": "string"}, "line": {"type": "integer", "minimum": 1},
                                      "symbol": {"type": "string"}, "query": {"type":"string"}}, "required": ["path"], "additionalProperties": False}})
                available.append({"name": "diff", "description": "Review a Git diff of current workspace edits.",
                                  "inputSchema": {"type": "object", "properties": {},
                                                  "additionalProperties": False}})
                available.append({"name":"edit","description":"Apply a SHORT source edit with current SHA-256 from focus. replace consumes old and inserts new. before/after KEEP old; new is ONLY the insertion. old must match uniquely; uniform LF/CRLF is adapted to source endings, never fuzzy matched. For repeated anchors supply location={evidence_key: focus.evidence_key, line: inspected line, end_line: optional inclusive last line}; old must match exactly once within those inspected lines. Stale hashes/locations fail. After three equivalent failures use a DIFFERENT unique anchor or inspected location; another equivalent failure stops inference, even after reinspection. create requires expected_sha256=absent and old empty. Python results must parse.",
                    "inputSchema":{"type":"object","properties":{k:{"type":"string"} for k in ['path','expected_sha256','old','new']}|
                        {'mode':{'type':'string','enum':['replace','before','after','create']},
                         'location':{'type':'object','properties':{'evidence_key':{'type':'string','pattern':'^[a-f0-9]{64}$'},
                             'line':{'type':'integer','minimum':1},'end_line':{'type':'integer','minimum':1}},
                             'required':['evidence_key','line'],'additionalProperties':False}},
                        'required':['path','expected_sha256','old','new','mode'],'additionalProperties':False}})
            response["result"] = {"tools": available}
        elif method == "tools/call":
            params = message.get("params", {})
            args = params.get("arguments", {})
            index = args.get("index") if isinstance(args, dict) else None
            name = params.get("name")
            error = True
            if calls >= budget or (stop and stop.exists()):
                value = {"error": "tool stopped or call limit reached"}
            elif not ((name in {"focus","edit"} and build and isinstance(args, dict)) or
                      (name == "diff" and build and args == {}) or
                      (name == "check" and isinstance(args, dict) and set(args) == {"index"}
                       and type(index) is int and 0 <= index < len(checks))):
                value = {"error": "invalid tool or command index"}
            else:
                try:
                    operation_start = monotonic()
                    calls = (context.charge_tool(name) if managed else
                             reserve_trial_call(spec_path, budget) if build or config.get("trial") else calls + 1)
                    if not managed and spec_path.with_name('edit-recovery.json').exists() and any(
                            n>=4 for n in json.loads(spec_path.with_name('edit-recovery.json').read_bytes()).values()):
                        raise ValueError('repeated equivalent source-edit failures exhausted recovery')
                    if build:
                        changed = delta(inventory(baseline), inventory(workspace))
                        validate_changes(changed, tuple(config["write_roots"]))
                    if name == 'edit':
                        deadline=config.get('deadline',time()+900)
                        if config.get('trial'):deadline=min(deadline,config['trial']['deadline'])
                        value=apply_edit(workspace,tuple(config['write_roots']),args,spec_path.with_name('source-edit.lock'),deadline,
                                         inspections=spec_path.parent/'source-excerpts')
                    elif name == "focus":
                        value = {**inspect_source(spec_path, workspace, args),
                                 "passed": True, "stdout": "", "stderr": ""}
                    elif name == "diff":
                        patch = git_patch(baseline, workspace, changed,
                                          spec_path.parent / f"agent-diff-{calls:02}")
                        patch_path = spec_path.parent / f"agent-diff-{calls:02}.patch"
                        patch_path.write_bytes(patch.encode("utf-8", "surrogateescape"))
                        value = {"stdout": patch, "stderr": "", "passed": True}
                    else:
                        check_root = spec_path.parent / f"public-check-{calls:02}"
                        snapshot(workspace, check_root, ())
                        remaining = config.get("deadline", time() + 900) - time()
                        value = pipeline(setup, checks[index], check_root, spec_path.parent / "check-home",
                                         config["image"], timeout=remaining, stop=stop, trial=config.get("trial"))
                    value["stdout"] = value["stdout"][-4000:]
                    value["stderr"] = value["stderr"][-4000:]
                    if build:
                        value.update(objective=config.get('objective','')[:1000],
                                     objective_truncated=len(config.get('objective',''))>1000,
                                     write_roots=config['write_roots'],remaining_calls=budget-calls)
                    error = not value["passed"]
                except EditRejected as exc:
                    diagnostic=edit_failure(spec_path,workspace,tuple(config['write_roots']),args,exc.diagnostic)
                    value={**diagnostic,'passed':False,'stdout':'','stderr':diagnostic['error']}
                    if value.get('actual_sha256'):
                        from .lock import file_lock
                        from .trial_budget import write
                        with file_lock(spec_path.with_name('source-navigation.lock')):
                            write(spec_path.with_name('edit-reinspection.json'),{'path':value['path'],
                                'sha256':value['actual_sha256'],'remaining':1})
                except (ValueError, OSError, RuntimeError) as exc:
                    value = {"error": str(exc)}
                finally:
                    if managed:
                        context.elapsed({'focus':'inspection','diff':'inspection','edit':'editing',
                                         'check':'verification'}[name], monotonic()-operation_start)
                        value['resource_status'] = context.summary()
                with spec_path.with_name("mcp.jsonl").open("a", encoding="utf-8") as log:
                    log.write(json.dumps({"tool": name, "index": index, "call": calls,
                                          **({'arguments':args} if name=='edit' else {}), **value}) + "\n")
                if build and name == "check" and "passed" in value:
                    value = {key: value[key] for key in ("passed", "code", "stdout", "stderr", "objective", "objective_truncated", "write_roots", "remaining_calls", "resource_status") if key in value}
                    value["stdout"] = value.get("stdout", "")[-450:]
                    value["stderr"] = value.get("stderr", "")[-900:]
            response["result"] = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}], "isError": error}
        else:
            response["error"] = {"code": -32601, "message": "method unavailable"}
        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    serve(Path(sys.argv[1]))
