"""Run unchanged authored tests under two explicit diagnostic clock phases."""
import sys,time
from pathlib import Path
sys.path.insert(0,str(Path('src').resolve()))
import pytest
phase=float(sys.argv[1])
@pytest.fixture(autouse=True)
def diagnostic_clock(monkeypatch):
    value=[1700000000+phase]
    monkeypatch.setattr(time,'time',lambda:value[0])
    def advance(seconds):value[0]+=seconds
    monkeypatch.setattr(time,'sleep',advance)
if __name__=='__main__':
    raise SystemExit(pytest.main(['-q','-p','no:cacheprovider','tests/test_itsdangerous/test_timedelta_max_age.py'],plugins=[sys.modules[__name__]]))
