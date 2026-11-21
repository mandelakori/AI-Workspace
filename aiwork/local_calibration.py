"""Bounded, synthetic capacity calibration. This is not an engineering benchmark."""
from __future__ import annotations

import http.client
import hashlib
import json
from pathlib import Path
import re
import subprocess
from threading import Event, Thread
from time import monotonic
from urllib.parse import urlsplit

from .local_runtime import MIB, copy_model, isolated_ollama, local_json, memory_snapshot
from .trial_budget import write

DEFAULT_PLAN = {'contexts':[8192,16384,32768], 'conditional_context':65536,
                'requests_per_context':{'load_only':1,'short_generation':1,'long_generation':1},
                'max_generation_requests':8,'max_load_requests':4,'output_tokens':128,
                'request_seconds':90,'context_seconds':210,'total_seconds':900,
                'gpu_headroom_mib':512,'ram_headroom_mib':2048,
                'seed':1729,'temperature':0,'thinking':False,'parallel':1,
                'cache_type':'f16','flash_attention':True,'long_fraction':.75}


def seal_report(root: Path) -> dict:
    """Derive admission fields from preserved raw measurements, without inference."""
    raw=(root/'report.json').read_bytes();report=json.loads(raw)
    report['source_report_sha256']=hashlib.sha256(raw).hexdigest()
    report['measurement_kind']='synthetic capacity; not engineering correctness'
    for row in report['contexts']:
        target=root/f"context-{row['context']}"
        log=(target/'server.log').read_text(errors='replace') if (target/'server.log').exists() else ''
        kv={}
        for device,size in re.findall(r'([A-Za-z0-9_]+) KV buffer size\s*=\s*([0-9.]+) MiB',log):
            kv[device]=int(float(size)*MIB)
        row['kv_cache_bytes']=kv
        layers=re.findall(r'offloaded (\d+)/(\d+) layers to GPU',log)
        row['offloaded_layers']={'gpu':int(layers[-1][0]),'total':int(layers[-1][1])} if layers else None
        load=target/'load-response.json'
        load_time=json.loads(load.read_bytes()).get('load_duration',0)/1e9 if load.exists() else 0
        load_log=re.findall(r'\|\s*200\s*\|\s*([0-9.]+)(ms|s|µs)\s*\|[^\n]*POST\s+"/api/generate"',log)
        if load_log:
            amount,unit=load_log[-1];load_time=float(amount)*{'s':1,'ms':.001,'µs':.000001}[unit]
        row['load_seconds']=load_time
        row['load_seconds_source']='server HTTP load timing' if load_log else 'API load_duration'
        short=row.get('short',{}).get('usage',{})
        rate=row.get('prefill_tokens_per_second',0)
        row['initial_prefill_overhead_seconds']=max(0,short.get('prompt_eval_duration',0)/1e9-
                                                   short.get('prompt_eval_count',0)/rate) if rate else 0
        resident=row.get('resident',{})
        row['resident_cpu_estimate_bytes']=max(0,resident.get('size',0)-resident.get('size_vram',0))
        row['ram_delta_masked']=row['ram_increment_bytes']<row['resident_cpu_estimate_bytes']
    path=root/'calibration.json'
    if path.exists():raise ValueError('sealed calibration already exists; do not rewrite it')
    write(path,report)
    return report


def generation(endpoint: str, model: str, context: int, prompt: str, output: int,
               directory: Path, deadline: float) -> dict:
    directory.mkdir()
    body={'model':model,'messages':[{'role':'user','content':prompt}],
          'think':False,'stream':True,'keep_alive':'3m',
          'options':{'num_ctx':context,'num_predict':output,'temperature':0,'seed':1729}}
    write(directory/'request.json',body)
    started=monotonic();host=urlsplit(endpoint);connection=http.client.HTTPConnection(host.hostname,host.port,
                                                                                 timeout=max(.01,deadline-started))
    first=None;final={};visible='';thinking='';consumed=0
    try:
        connection.request('POST','/api/chat',json.dumps(body),{'Content-Type':'application/json','Connection':'close'})
        transport=connection.sock
        response=connection.getresponse()
        if response.status!=200:raise RuntimeError(f'local inference HTTP {response.status}')
        with (directory/'response.jsonl').open('wb') as out:
            while monotonic()<deadline:
                transport.settimeout(max(.01,deadline-monotonic()))
                raw=response.readline(1_048_577)
                if not raw:break
                consumed+=len(raw)
                if len(raw)>1_048_576 or consumed>4*1024*1024:raise ValueError('calibration response limit')
                out.write(raw);out.flush();row=json.loads(raw)
                if row.get('error'):raise RuntimeError(str(row['error']))
                text=row.get('message',{}).get('content','');reason=row.get('message',{}).get('thinking','')
                if (text or reason) and first is None:first=monotonic()-started
                visible+=text;thinking+=reason
                if row.get('done'):final=row;break
            else:raise TimeoutError('calibration inference deadline')
        if not final:raise RuntimeError('calibration stream ended without final usage')
        result={'wall_seconds':monotonic()-started,'first_token_seconds':first,'visible':visible,
                'thinking':thinking,'usage':{k:v for k,v in final.items() if k!='message'},
                'prefill_tokens_per_second':(final.get('prompt_eval_count',0)/(final.get('prompt_eval_duration',0)/1e9)
                                             if final.get('prompt_eval_duration') else 0),
                'generation_tokens_per_second':(final.get('eval_count',0)/(final.get('eval_duration',0)/1e9)
                                               if final.get('eval_duration') else 0)}
        write(directory/'result.json',result)
        return result
    except (OSError,ValueError,RuntimeError) as error:
        write(directory/'failure.json',{'error':type(error).__name__,'detail':str(error),
                                       'wall_seconds':monotonic()-started,'visible':visible,'thinking':thinking})
        raise
    finally:connection.close()


def capacity64(rows: list[dict], memory: dict) -> dict:
    """Extrapolation can authorize a probe, never qualify an unmeasured context."""
    measured={r['context']:r for r in rows if r.get('status')=='measured'}
    if not {16384,32768}<=measured.keys():return {'run':False,'reason':'16K and 32K measurements required'}
    a,b=measured[16384],measured[32768]
    gpu=b['gpu_increment_bytes']+max(0,b['gpu_increment_bytes']-a['gpu_increment_bytes'])*2
    ram=b['ram_increment_bytes']+max(0,b['ram_increment_bytes']-a['ram_increment_bytes'])*2
    seconds=65536*.75/b['prefill_tokens_per_second']+128/b['generation_tokens_per_second']
    feasible=(gpu+512*MIB<=memory.get('gpu_free_bytes',0)
              and ram+2048*MIB<=memory.get('ram_available_bytes',0) and seconds<=90)
    return {'run':feasible,'projected_gpu_bytes':gpu,'projected_ram_bytes':ram,
            'projected_long_request_seconds':seconds,'memory':memory,
            'reason':'qualified to attempt only' if feasible else 'projected memory headroom or deadline insufficient'}


def calibrate(binary: str, source: Path, manifest: str, model: str, root: Path) -> dict:
    source=source.resolve(strict=True);root=root.resolve()
    if root.is_relative_to(source) or source.is_relative_to(root):
        raise ValueError('calibration output must be independent of original model storage')
    root.mkdir(parents=True,exist_ok=False)
    started=monotonic();deadline=started+DEFAULT_PLAN['total_seconds']
    write(root/'plan.json',DEFAULT_PLAN|{'model':model,'manifest':manifest,'source':str(source.resolve()),
                                      'purpose':'synthetic capacity, not software engineering'})
    before=local_json('http://127.0.0.1:11434','api/ps')
    write(root/'shared-before.json',before)
    if before.get('models'):raise ValueError('shared GPU model is resident; do not disturb it for calibration')
    copy=copy_model(source,root/'model-store',manifest,deadline=deadline)
    report={'model':model,'model_copy':copy,'contexts':[],'plan':DEFAULT_PLAN,'engineering_benchmark':False}
    sizes=[8192,16384,32768]
    for size in sizes:
        row={'context':size,'status':'failed'};target=root/f'context-{size}';baseline=memory_snapshot()
        samples=[baseline];stop=Event();worker=None
        def sample():
            while not stop.wait(.5):
                try:samples.append(memory_snapshot())
                except (OSError,ValueError,subprocess.TimeoutExpired):pass
        try:
            if baseline.get('ram_available_bytes',0)<3072*MIB or baseline.get('gpu_free_bytes',0)<1024*MIB:
                raise ValueError('insufficient baseline RAM/GPU headroom')
            with isolated_ollama(binary,root/'model-store',size,target,
                                 min(210,max(.01,deadline-monotonic()))) as (endpoint,limit,pid):
                worker=Thread(target=sample,daemon=True);worker.start()
                write(target/'load-request.json',{'model':model,'keep_alive':'3m','options':{'num_ctx':size}})
                load=local_json(endpoint,'api/generate',{'model':model,'keep_alive':'3m','options':{'num_ctx':size}},
                                timeout=min(90,max(.01,limit-monotonic())))
                write(target/'load-response.json',load)
                resident=local_json(endpoint,'api/ps');write(target/'resident.json',resident)
                current=next((m for m in resident['models'] if m['name']==model),None)
                if not current or current.get('context_length')!=size:
                    raise ValueError('requested context not confirmed by server')
                short=generation(endpoint,model,size,'Short capacity probe. '+('the '*1000)+
                                 '\nPrint consecutive integers separated by spaces, starting with 1. Continue until stopped.',
                                 128,target/'short',min(monotonic()+90,limit))
                long=generation(endpoint,model,size,'Long capacity probe. Ignore this filler:\n'+('the '*(size*3//4))+
                                '\nNow print consecutive integers separated by spaces, starting with 1. Continue until stopped.',
                                128,target/'long',min(monotonic()+90,limit))
                if short['thinking'] or long['thinking'] or not short['visible'] or not long['visible']:
                    raise ValueError('disabled-thinking probe returned reasoning or unusable output')
                if long['usage'].get('prompt_eval_count',0)<size//2:
                    raise ValueError('long prompt did not exercise half the requested window')
                samples.append(memory_snapshot())
                row.update(status='measured',resident=current,short=short,long=long,
                           prefill_tokens_per_second=long['prefill_tokens_per_second'],
                           generation_tokens_per_second=min(short['generation_tokens_per_second'],long['generation_tokens_per_second']))
        except (OSError,ValueError,RuntimeError) as error:
            row.update(error=type(error).__name__,detail=str(error))
        finally:
            stop.set()
            if worker:worker.join(timeout=4)
            if worker and worker.is_alive():raise RuntimeError('calibration sampler cleanup failed')
        if target.exists():
            write(target/'memory-samples.json',samples)
            ownership=json.loads((target/'ownership.json').read_bytes()) if (target/'ownership.json').exists() else {}
            if ownership and not ownership.get('cleanup_passed'):raise RuntimeError('private inference cleanup failed')
        row['baseline']=baseline
        row['gpu_increment_bytes']=max(0,max(s.get('gpu_used_bytes',0) for s in samples)-baseline.get('gpu_used_bytes',0))
        row['ram_increment_bytes']=max(0,baseline.get('ram_available_bytes',0)-min(s.get('ram_available_bytes',baseline.get('ram_available_bytes',0)) for s in samples))
        if target.exists():
            log=(target/'server.log').read_text(errors='replace')
            row['allocation_evidence']=[line for line in log.splitlines() if re.search(r'KV|cache|offload|layers|buffer|memory',line,re.I)][-45:]
        report['contexts'].append(row);report['elapsed_seconds']=monotonic()-started
        write(root/'report.json',report)
        shared=local_json('http://127.0.0.1:11434','api/ps')
        if shared.get('models'):raise RuntimeError('shared inference became active; stop calibration')
        if size==32768:
            report['conditional64']=capacity64(report['contexts'],memory_snapshot())
            if report['conditional64']['run']:sizes.append(65536)
    write(root/'shared-after.json',local_json('http://127.0.0.1:11434','api/ps'))
    write(root/'report.json',report)
    return report
