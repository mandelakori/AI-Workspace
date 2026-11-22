"""Replay saved rejected edits on isolated copies; never runs a model/candidate.

Usage: .venv/Scripts/python scripts/replay_source_edits.py --output PATH
Output must be a new directory. The two historical trials are read-only inputs.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import tempfile
from time import monotonic
from zipfile import ZipFile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aiwork.source_edit import apply_edit, EditRejected, sha

ROOT=Path(__file__).resolve().parents[1]
NAME='src/itsdangerous/timed.py'
SOURCE_SHA='4fab550338d97c65ba6ea124f0ac021fb1e4b50299a725d7d66f9924957f7fcf'


def replay(output: Path) -> dict:
    started=monotonic();output.mkdir(parents=True,exist_ok=False)
    trace=ROOT/'docs/evidence/a100-duration-trial-result/attempt/mcp.jsonl'
    archive=ROOT/'docs/evidence/milestone-e-a100/itsdangerous-pinned-source.zip'
    with ZipFile(archive) as bundle:source=bundle.read(NAME)
    if sha(source)!=SOURCE_SHA:raise ValueError('frozen source drift')
    proposals=[json.loads(line) for line in trace.read_text(encoding='utf-8').splitlines()
               if json.loads(line).get('tool')=='edit']
    if len(proposals)!=37:raise ValueError('saved proposal count drift')
    rows=[]
    with tempfile.TemporaryDirectory(prefix='aiwork-editor-replay-') as directory:
        work=Path(directory).resolve();target=work/NAME;target.parent.mkdir(parents=True)
        for original in proposals:
            target.write_bytes(source);args=original['arguments']
            if args['path']!=NAME or args['expected_sha256']!=SOURCE_SHA:raise ValueError('proposal input drift')
            row={'original_call':original['call'],'original_code':original['code'],'arguments':args,
                 'proposal_sha256':sha(json.dumps(args,sort_keys=True).encode())}
            try:
                receipt=apply_edit(work,(NAME,),args,work/'edit.lock')
                after=target.read_bytes();start,end=receipt['matched_bytes']
                # Independent byte witness: only the authorized span/insertion changes.
                new=args['new'].replace('\r\n','\n').replace('\n','\r\n').encode()
                expected=(source[:start]+new+source[end:] if args['mode']=='replace' else
                          source[:start]+new+source[start:] if args['mode']=='before' else
                          source[:end]+new+source[end:])
                if after!=expected:raise AssertionError('unrelated bytes changed')
                if original['code']!='anchor_mismatch' or not receipt['anchor_newline_adapted']:
                    raise AssertionError('unexpected accepted classification')
                candidate=f"proposal-{original['call']:02}.py"
                (output/candidate).write_bytes(after)
                row.update(outcome='applied',receipt=receipt,candidate=candidate,unrelated_bytes_preserved=True)
            except EditRejected as exc:
                if target.read_bytes()!=source:raise AssertionError('rejection changed source')
                row.update(outcome='rejected',receipt=exc.diagnostic,unrelated_bytes_preserved=True)
            rows.append(row)
    applied=[r for r in rows if r['outcome']=='applied']
    counts=dict(Counter(r['receipt'].get('code','applied') for r in rows))
    if counts!={'ambiguous_anchor':24,'applied':11,'anchor_mismatch':1,'invalid_anchor':1}:
        raise AssertionError(counts)
    summary={'kind':'deterministic_saved_proposal_replay_not_feature_evaluation',
        'source_sha256':SOURCE_SHA,'trace_sha256':sha(trace.read_bytes()),'archive_sha256':sha(archive.read_bytes()),
        'proposals':len(rows),'outcomes':counts,'accepted_calls':[r['original_call'] for r in applied],
        'unique_accepted_argument_objects':len({r['proposal_sha256'] for r in applied}),
        'unique_accepted_source_hashes':len({r['receipt']['sha256'] for r in applied}),
        'each_proposal_starts_from_identical_original':True,'unrelated_bytes_preserved':True,
        'behavioral_correctness':'NOT_EVALUATED','inference_requests':0,'seconds':monotonic()-started}
    (output/'replay.json').write_bytes((json.dumps({'summary':summary,'proposals':rows},indent=2)+'\n').encode())
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    print(json.dumps(replay(parser.parse_args().output.resolve()),indent=2))
