import base64
from contextlib import contextmanager
import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
from time import monotonic
import unittest
from unittest.mock import patch
import zlib

from aiwork.controller import Controller
from aiwork.perception import MIB, PINS, REMOTE_TOKEN, UNCERTAIN, Perception, PerceptionConfig, observations, png_size
from aiwork.process import Result
from aiwork.schema import Config, Profile


def synthetic_png():
    def chunk(kind, data):
        return struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR',struct.pack('!IIBBBBB',2,1,8,2,0,0,0)) +
            chunk(b'IDAT',zlib.compress(b'\x00\xff\xff\xff\x12\x34\x55'))+chunk(b'IEND',b''))


FRAME = synthetic_png()
MEMORY = {'ram_available_bytes':8*1024*MIB,'gpu_free_bytes':8*1024*MIB}
PAYLOAD = {'pins':PINS,'cleanup':True,'elements':[
    {'kind':'text','bbox':[0,0,.5,1],'description':'Untrusted visible text'},
    {'kind':'icon','bbox':[.5,0,1,1],'description':'Example icon'}],
    'metrics':{'peak_cuda_bytes':1024,'arbitrary_data':999}}


class PerceptionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.cfg = Config(self.root/'state',ssh={'alias':'fixture','remote_port':18080},
                          execution_state=self.root/'shared')
        self.controller = Controller(self.cfg)

    def test_observation_contract(self):
        self.assertEqual(png_size(FRAME),(2,1))
        result = observations(FRAME,PAYLOAD,'local',1.5)
        self.assertEqual(result['coordinate_system'],'normalized_xyxy_image')
        self.assertEqual([x['id'] for x in result['elements']],[1,2])
        self.assertTrue(result['untrusted_screen_content'])
        self.assertEqual(result['metrics'],{'peak_cuda_bytes':1024,'elapsed_seconds':1.5})
        for data in (PAYLOAD | {'pins':{}},PAYLOAD | {'cleanup':False},PAYLOAD | {'metrics':None},
                     PAYLOAD | {'elements':[PAYLOAD['elements'][0] | {'bbox':[0,0,0,1]}]},
                     PAYLOAD | {'elements':[PAYLOAD['elements'][0] | {'bbox':[float('nan'),0,1,1]}]}):
            with self.assertRaises(ValueError):
                observations(FRAME,data,'local',1.5)
        for invalid in (b'GIF',FRAME[:16]+struct.pack('!II',1000000,1)+FRAME[24:]):
            with self.assertRaises(ValueError):
                png_size(invalid)

    def test_local_admission_and_exclusive_owned_worker(self):
        backend = Perception(self.controller,PerceptionConfig(python='isolated-python',source='pinned-source'))
        lane = self.controller.planes['local']
        probe = Profile('other','model','http://127.0.0.1:11434/v1')

        def worker(argv,cwd,timeout,env,stop,**options):
            with self.assertRaises(TimeoutError), lane.reserve(probe,.02):
                self.fail('perception must share the engineering GPU reservation')
            self.assertEqual(argv[:4],['isolated-python','-m','aiwork.omni_worker','parse'])
            self.assertEqual(env['HF_HUB_OFFLINE'],'1')
            self.assertEqual(options['stdin'],FRAME)
            self.assertEqual(stop,self.cfg.state/'STOP')
            self.assertLessEqual(timeout,90)
            return Result(0,.05,json.dumps(PAYLOAD),'',False,False)

        with patch('aiwork.perception.run',side_effect=worker) as run, patch(
                'aiwork.perception.memory_snapshot',side_effect=[{},MEMORY]):
            with self.assertRaisesRegex(ValueError,'insufficient'):
                backend.observe(FRAME,'local')
            run.assert_not_called()
            self.assertEqual(backend.observe(FRAME,'local')['location'],'local')
            run.assert_called_once()
        with lane.reserve(probe,.5):
            pass

    def test_stop_and_deadline_skip_worker(self):
        backend = Perception(self.controller,PerceptionConfig(python='isolated'))
        with patch('aiwork.perception.run') as run:
            (self.cfg.state/'STOP').touch()
            with self.assertRaisesRegex(TimeoutError,'stopped'):
                backend.observe(FRAME,'local')
            with self.assertRaisesRegex(TimeoutError,'deadline'):
                backend.local(FRAME,monotonic()-1)
            run.assert_not_called()

    def test_a100_requires_affirmative_per_frame_consent_and_a_dedicated_port(self):
        backend = Perception(self.controller,PerceptionConfig(enable_remote=True))
        with patch('aiwork.perception.a100_session') as tunnel:
            for consent in (False,'true',1):
                with self.assertRaisesRegex(ValueError,'consent'):
                    backend.observe(FRAME,'a100',consent)
            with self.assertRaisesRegex(ValueError,'ports distinct'):
                Perception(self.controller,PerceptionConfig(enable_remote=True,remote_port=18080)
                           ).observe(FRAME,'a100',True)
            tunnel.assert_not_called()

    def test_a100_uses_owned_tunnel_marking_dispatch_until_clean_close(self):
        backend = Perception(self.controller,PerceptionConfig(enable_remote=True))
        marker = self.cfg.execution_state/UNCERTAIN
        tunnel_events = []

        @contextmanager
        def tunnel(config,profile,**options):
            self.assertFalse(options['dispatch'])
            self.assertEqual(config.ssh['remote_port'],18770)
            self.assertEqual(profile.endpoint,'http://127.0.0.1:18771/v1')
            tunnel_events.append('start')
            try:
                yield
            finally:
                self.assertTrue(marker.exists())
                tunnel_events.append('cleanup')
        mode = 'success'

        def request(url, method='GET', body=None, **options):
            if method=='GET':
                self.assertFalse(marker.exists())
                return {'pins':PINS,'max_seconds':10,'memory':MEMORY}
            self.assertTrue(marker.exists())
            self.assertEqual(base64.b64decode(body['png']),FRAME)
            if mode=='clean failure':
                return {'pins':PINS,'cleanup':True,'error':'isolated peer refused'}
            if mode=='interrupt':
                raise TimeoutError('transport lost')
            return PAYLOAD

        with patch('aiwork.perception.a100_session',side_effect=tunnel), patch(
                'aiwork.perception.request',side_effect=request), patch.dict('os.environ',{REMOTE_TOKEN:'x'*24}):
            self.assertEqual(backend.observe(FRAME,'a100',True)['location'],'a100')
            self.assertFalse(marker.exists())
            mode = 'clean failure'
            with self.assertRaisesRegex(RuntimeError,'peer refused'):
                backend.observe(FRAME,'a100',True)
            self.assertFalse(marker.exists())
            mode = 'interrupt'
            with self.assertRaisesRegex(RuntimeError,'completion uncertain'):
                backend.observe(FRAME,'a100',True)
            self.assertTrue(marker.exists())
            with self.assertRaisesRegex(RuntimeError,'cleanup is unconfirmed'):
                backend.observe(FRAME,'a100',True)
        self.assertEqual(tunnel_events,['start','cleanup']*3)


if __name__=='__main__':
    unittest.main()
