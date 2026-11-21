import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import contextmanager
from dataclasses import replace
from time import monotonic

from aiwork.local_runtime import MIB, admit_context, copy_model, calibrated_runtime
from aiwork.schema import Profile,Task
from aiwork.local_calibration import capacity64


class LocalExecutionTests(unittest.TestCase):
    def test_calibrated_runtime_binds_hash_store_context_and_owned_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();store=root/'model-store';manifest=store/'manifests/registry.ollama.ai/library/inert/test'
            manifest.parent.mkdir(parents=True);manifest.write_text('{}');artifacts=root/'artifacts';artifacts.mkdir()
            report={'model':'inert','engineering_benchmark':False,'contexts':[self.row(x) for x in (8192,16384)],
                    'plan':{'gpu_headroom_mib':512},'model_copy':{'destination':str(store),
                    'manifest':'registry.ollama.ai/library/inert/test','manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()}}
            path=root/'calibration.json';path.write_text(json.dumps(report))
            profile=Profile('inert','inert','http://127.0.0.1:11434/v1',engine='ollama',context=32768,
                            local_calibration=str(path),calibration_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            task=Task('Scoped test',root,'agent','inert',(),(),(),context_input_tokens=7440)
            @contextmanager
            def isolated(*args,**kwargs):
                args[3].mkdir(parents=True)
                yield 'http://127.0.0.1:19999',monotonic()+300,123
            with patch('aiwork.local_runtime.memory_snapshot',return_value={'gpu_free_bytes':7500*MIB,'ram_available_bytes':8000*MIB}),\
                 patch('aiwork.local_runtime.executable',return_value='pinned-ollama'),\
                 patch('aiwork.local_runtime.isolated_ollama',side_effect=isolated) as launched,\
                 patch('aiwork.local_runtime.local_json',return_value={'models':[{'name':'inert','context_length':16384}]}):
                with calibrated_runtime(profile,task,artifacts,monotonic()+300) as selected:
                    self.assertEqual(selected.context,16384)
                    self.assertEqual(selected.endpoint,'http://127.0.0.1:19999/v1')
                self.assertEqual(profile.context,32768)
                self.assertEqual(launched.call_args.args[2],16384)
                with self.assertRaisesRegex(ValueError,'hash changed'):
                    with calibrated_runtime(replace(profile,calibration_sha256='0'*64),task,artifacts,monotonic()+300):pass
    def test_cold_prefill_and_masked_ram_cannot_evade_admission(self):
        rows=[self.row(x) for x in (8192,16384,32768)]
        rows[1].update(ram_increment_bytes=5000*MIB,load_seconds=50,initial_prefill_overhead_seconds=48)
        rows[2].update(ram_increment_bytes=0,load_seconds=45,initial_prefill_overhead_seconds=35)
        p=dict(input_tokens=7440,output_tokens=2048,reserve_tokens=512,maximum=32768,
               memory={'gpu_free_bytes':7500*MIB,'ram_available_bytes':8000*MIB},deadline_seconds=200)
        result=admit_context({'contexts':rows},**p)
        self.assertEqual(result['selected'],16384)
        self.assertEqual(result['candidates'][2]['required_ram_bytes'],5000*MIB)
        self.assertIsNone(admit_context({'contexts':rows},**(p|{'deadline_seconds':30}))['selected'])
        self.assertIsNone(admit_context({'contexts':rows},**(p|{'memory':p['memory']|{'ram_available_bytes':6000*MIB}}))['selected'])
    def row(self,size=8192):
        return {'context':size,'status':'measured','gpu_increment_bytes':5000*MIB,
                'ram_increment_bytes':1000*MIB,'prefill_tokens_per_second':1000,
                'generation_tokens_per_second':100}

    def test_smallest_measured_window_demand_headroom_and_deadline(self):
        report={'contexts':[self.row(x) for x in (8192,16384,32768)]}
        policy=dict(input_tokens=7440,output_tokens=2048,reserve_tokens=512,maximum=32768,
                    memory={'gpu_free_bytes':7500*MIB,'ram_available_bytes':8000*MIB},deadline_seconds=120)
        selected=admit_context(report,**policy)
        self.assertEqual(selected['selected'],16384)
        self.assertEqual(admit_context(report,**(policy|{'input_tokens':1000}))['selected'],8192)
        for change in [{'maximum':8192},{'deadline_seconds':1},{'memory':{}},
                       {'memory':{'gpu_free_bytes':5000*MIB,'ram_available_bytes':8000*MIB}},
                       {'memory':{'gpu_free_bytes':7500*MIB,'ram_available_bytes':2000*MIB}}]:
            self.assertIsNone(admit_context(report,**(policy|change))['selected'])
        report['contexts'][1]['status']='failed';report['contexts'][2]['status']='unmeasured'
        self.assertIsNone(admit_context(report,**policy)['selected'])

    def test_64k_requires_both_measured_contexts_and_resource_margin(self):
        memory={'gpu_free_bytes':7500*MIB,'ram_available_bytes':8000*MIB}
        self.assertFalse(capacity64([self.row(32768)],memory)['run'])
        rows=[self.row(16384),self.row(32768)]
        self.assertTrue(capacity64(rows,memory)['run'])
        self.assertFalse(capacity64(rows,memory|{'gpu_free_bytes':5000*MIB})['run'])
        rows[-1]['generation_tokens_per_second']=1
        self.assertFalse(capacity64(rows,memory)['run'])

    def test_model_copy_verifies_blobs_and_keeps_original_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'original';(source/'blobs').mkdir(parents=True)
            data=b'owned synthetic model bytes';digest=hashlib.sha256(data).hexdigest()
            blob=source/'blobs'/('sha256-'+digest);blob.write_bytes(data)
            name='registry.ollama.ai/library/synthetic/test'
            manifest=source/'manifests'/name;manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({'config':{'digest':'sha256:'+digest,'size':len(data)},'layers':[]}))
            receipt=copy_model(source,root/'isolated',name)
            self.assertEqual(receipt['blobs']['sha256:'+digest]['sha256'],digest)
            copied=root/'isolated/blobs'/blob.name;copied.write_bytes(b'changed private copy')
            self.assertEqual(blob.read_bytes(),data)
            with self.assertRaises(ValueError):copy_model(source,root/'isolated',name)
            with self.assertRaises(ValueError):copy_model(source,root/'another','../bad')
            blob.write_bytes(b'x'*len(data))
            with self.assertRaisesRegex(ValueError,'hash mismatch'):copy_model(source,root/'invalid',name)
