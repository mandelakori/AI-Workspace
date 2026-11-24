"""Entry point for a separate OmniParser environment. Heavy imports are lazy."""
from __future__ import annotations

import argparse
import base64
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from time import monotonic

from .local_runtime import memory_snapshot
from .perception import MAX_IMAGE, MIB, MODEL, PINS, REMOTE_TOKEN, png_size, require_memory
from .process import environment, run


def memory() -> dict:
    values = memory_snapshot()
    if sys.platform.startswith('linux'):
        for line in Path('/proc/meminfo').read_text().splitlines():
            if line.startswith('MemAvailable:'):
                values['ram_available_bytes'] = int(line.split()[1])*1024
                break
    return values


def parse(frame: bytes, source: Path, cache: Path, ocr: Path) -> dict:
    started = monotonic()
    w, h = png_size(frame)
    command = ['git','-C',str(source)]
    revision = subprocess.check_output([*command,'rev-parse','HEAD'],text=True,timeout=5).strip()
    changed = subprocess.check_output([*command,'status','--porcelain','--','util'],timeout=5)
    if revision != PINS['source'] or changed:
        raise ValueError('OmniParser checkout does not match the clean pinned detector source')
    sys.path.insert(0,str(source))
    import easyocr
    import numpy as np
    from PIL import Image
    import torch
    from huggingface_hub import snapshot_download
    from transformers import AutoProcessor
    from transformers.dynamic_module_utils import get_class_from_dynamic_module
    from util.yolov9 import YOLOv9Detector  # Official MIT-weight inference implementation.

    if not torch.cuda.is_available():
        raise RuntimeError('the optional environment requires CUDA for this GPU backend')
    before = memory()
    torch.cuda.reset_peak_memory_stats()
    image = Image.open(io.BytesIO(frame))
    if image.format != 'PNG' or image.size != (w,h):
        raise ValueError('invalid screenshot frame')
    image = image.convert('RGB')
    weights = Path(snapshot_download('microsoft/OmniParser-v2.0',revision=PINS['weights'],cache_dir=cache,
                                     local_files_only=True))
    florence = snapshot_download('microsoft/Florence-2-base',revision=PINS['florence_processor'],cache_dir=cache,
                                 local_files_only=True)
    florence_code = snapshot_download('microsoft/Florence-2-base-ft',revision=PINS['florence_code'],cache_dir=cache,
                                      local_files_only=True)
    detector = YOLOv9Detector(weights/'icon_detect_v3/model.pt',device='cuda')
    processor = AutoProcessor.from_pretrained(florence,trust_remote_code=True,local_files_only=True)
    caption_class = get_class_from_dynamic_module('modeling_florence2.Florence2ForConditionalGeneration',
                                                   florence_code,local_files_only=True)
    caption, loading = caption_class.from_pretrained(weights/'icon_caption',torch_dtype=torch.float16,
        attn_implementation='eager',local_files_only=True,use_safetensors=True,output_loading_info=True)
    if loading['missing_keys'] or loading['mismatched_keys']:
        raise ValueError('pinned Florence-2 code did not load the complete caption checkpoint')
    caption = caption.to('cuda').eval()
    reader = easyocr.Reader(['en'],gpu=False,model_storage_directory=str(ocr),download_enabled=False)
    rows = []

    def add(kind, box, description):
        scaled = [max(0,min(1,float(x)/limit)) for x,limit in zip(box,(w,h,w,h))]
        if scaled[0]<scaled[2] and scaled[1]<scaled[3]:
            rows.append({'kind':kind,'description':description,'bbox':scaled})

    for points, text, _ in reader.readtext(np.array(image),text_threshold=.8)[:192]:
        xs, ys = zip(*points)
        add('text',(min(xs),min(ys),max(xs),max(ys)),text)
    detected = detector.predict(image,conf=.05,imgsz=1280,max_det=64)[0].boxes.xyxy.cpu().tolist()
    valid = [box for box in detected if int(box[0]) < int(box[2]) and int(box[1]) < int(box[3])]
    for at in range(0,len(valid),8):
        boxes = valid[at:at+8]
        crops = [image.crop(tuple(map(int,box))).resize((64,64)) for box in boxes]
        inputs = processor(text=['<CAPTION>']*len(crops),images=crops,return_tensors='pt',do_resize=False)
        with torch.inference_mode():
            output = caption.generate(input_ids=inputs['input_ids'].to('cuda'),
                                      pixel_values=inputs['pixel_values'].to('cuda',torch.float16),
                                      max_new_tokens=20,num_beams=1,do_sample=False)
        for box, description in zip(boxes,processor.batch_decode(output,skip_special_tokens=True)):
            add('icon',box,description.strip())
    after = memory()
    return {'pins':PINS,'elements':rows,'metrics':{'server_seconds':monotonic()-started,
        'peak_cuda_bytes':torch.cuda.max_memory_allocated(),'available_ram_before':before.get('ram_available_bytes'),
        'available_ram_after':after.get('ram_available_bytes'),'free_vram_before':before.get('gpu_free_bytes'),
        'free_vram_after':after.get('gpu_free_bytes')}}


def serve(args):
    token = os.environ.get(REMOTE_TOKEN,'')
    if len(token)<24:
        raise ValueError(f'set {REMOTE_TOKEN} to a separately shared peer secret of at least 24 characters')
    state = args.state.resolve()
    env = environment(state) | {'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'}
    command = [sys.executable,'-m','aiwork.omni_worker','parse',str(args.source),str(args.cache),str(args.ocr)]

    class Peer(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self,*_):
            pass

        def reply(self,body,status=200):
            raw = json.dumps(body).encode()
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def authorized(self):
            if secrets.compare_digest(self.headers.get('Authorization',''),f'Bearer {token}'):
                return True
            self.reply({'error':'peer authorization required'},401)
            return False

        def do_GET(self):
            if not self.authorized():return
            if self.path=='/v1/models':self.reply({'data':[{'id':MODEL}]})
            elif self.path=='/v1/perception/status':
                self.reply({'pins':PINS,'max_seconds':args.timeout+5,'memory':memory()})
            else:self.reply({'error':'unknown peer path'},404)

        def do_POST(self):
            if not self.authorized():return
            try:
                length = int(self.headers.get('Content-Length','0'))
                if self.path!='/v1/perception/parse' or not 0<length<6*MIB:
                    raise ValueError('invalid screenshot request')
                frame = base64.b64decode(json.loads(self.rfile.read(length))['png'],validate=True)
                png_size(frame)
                require_memory(memory(),args.ram_mib,args.vram_mib)
                result = run(command,state,args.timeout,env,stdin=frame,output_limit=MIB)
                if result.code or result.timed_out or result.truncated:
                    raise ValueError('remote parser failed or exceeded its budget; inspect the peer installation')
                answer = json.loads(result.stdout) | {'cleanup':True}
            except (ValueError, KeyError, TypeError) as error:
                answer = {'pins':PINS,'cleanup':True,'error':str(error)}
            self.reply(answer)

    with HTTPServer(('127.0.0.1',args.port),Peer) as server:
        server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('parse','serve'))
    for name in ('source','cache','ocr'):
        parser.add_argument(name,type=lambda p:Path(p).resolve(strict=True))
    parser.add_argument('--state',type=Path,default=Path('.aiwork/omni-peer'))
    parser.add_argument('--port',type=int,default=18770)
    parser.add_argument('--timeout',type=int,default=65)
    parser.add_argument('--ram-mib',type=int,default=4096)
    parser.add_argument('--vram-mib',type=int,default=6144)
    args = parser.parse_args()
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    if args.action=='serve':
        if not (1024<=args.port<=65535 and 5<=args.timeout<=120 and 512<=args.ram_mib<=131072
                and 512<=args.vram_mib<=65536):
            parser.error('invalid peer resource limits')
        serve(args)
    else:
        with redirect_stdout(sys.stderr):
            result = parse(sys.stdin.buffer.read(MAX_IMAGE+1),args.source,args.cache,args.ocr)
        print(json.dumps(result))


if __name__=='__main__':
    main()
