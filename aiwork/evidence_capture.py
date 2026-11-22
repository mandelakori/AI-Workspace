"""Bounded provider payload storage. Reserve before reads; archive before relay."""
from contextlib import contextmanager
import hashlib
import json
import os
import errno
from pathlib import Path
import shutil
from threading import RLock

DEFAULT_CAPTURE_BYTES = 64 * 1024 * 1024
DEFAULT_HEADROOM_BYTES = 32 * 1024 * 1024


class EvidenceExhausted(ValueError):
    pass


class EvidenceIOError(OSError):
    pass


def storage_error(error):
    if error.errno==errno.ENOSPC:
        return EvidenceExhausted('provider evidence disk space exhausted')
    return EvidenceIOError('provider evidence storage failed: '+type(error).__name__)


class EvidenceCapture:
    def __init__(self, root: Path, limit: int, headroom: int):
        if (type(limit) is not int or not 1 <= limit <= 512*1024*1024
                or type(headroom) is not int or not 0 <= headroom <= 1024*1024*1024):
            raise ValueError('invalid provider evidence byte/headroom limits')
        self.root,self.limit,self.headroom=root,limit,headroom
        self.lock=RLock();self.used=0;self.reserved=0;self.files={};self.hashes={}

    @contextmanager
    def reserve(self, amount: int, *, exact: bool = False):
        with self.lock:
            try:free=shutil.disk_usage(self.root).free-self.headroom-self.reserved
            except OSError as error:raise storage_error(error) from error
            available=min(self.limit-self.used-self.reserved,free)
            if available<=0 or exact and amount>available:
                raise EvidenceExhausted('provider evidence byte limit or disk headroom exhausted')
            size=min(amount,available);self.reserved+=size
        lease=[size]
        try:yield lease
        finally:
            with self.lock:self.reserved-=lease[0]

    @contextmanager
    def open(self, name: str):
        # Names are controller-generated, never model paths. Never overwrite evidence.
        if Path(name).name!=name or name in self.files:
            raise ValueError('invalid or reused evidence filename')
        try:stream=(self.root/name).open('xb',buffering=0)
        except OSError as error:raise storage_error(error) from error
        with stream:
            with self.lock:
                self.hashes[name]=hashlib.sha256()
                self.files[name]={'bytes':0,'sha256':self.hashes[name].hexdigest(),'complete':False}
            try:yield stream
            finally:
                try:os.fsync(stream.fileno())
                except OSError as error:raise storage_error(error) from error

    def append(self, name: str, stream, data: bytes, lease: list):
        if len(data)>lease[0]:raise ValueError('unreserved evidence write')
        with self.lock:
            # Unbuffered writes account partial disk writes before any exception.
            at=0
            while at<len(data):
                try:
                    written=stream.write(memoryview(data)[at:])
                    if not written:raise OSError('short evidence write')
                except OSError as error:
                    self.files[name].update(unarchived_bytes=len(data)-at,
                        unarchived_sha256=hashlib.sha256(data[at:]).hexdigest(),storage_error=type(error).__name__)
                    raise storage_error(error) from error
                self.hashes[name].update(data[at:at+written]);at+=written
                self.used+=written;self.reserved-=written;lease[0]-=written
                self.files[name].update(bytes=self.files[name]['bytes']+written,
                                        sha256=self.hashes[name].hexdigest())

    def complete(self, name: str):
        with self.lock:self.files[name]['complete']=True

    def store(self, name: str, data: bytes):
        with self.reserve(len(data),exact=True) as lease:
            with self.open(name) as stream:self.append(name,stream,data,lease)
            self.complete(name)

    def summary(self):
        with self.lock:
            return {'limit_bytes':self.limit,'headroom_bytes':self.headroom,
                    'captured_bytes':self.used,'reserved_bytes':self.reserved,
                    'files':{k:dict(v) for k,v in self.files.items()}}


class UsageLines:
    """Parse usage incrementally; oversized lines remain archived byte-for-byte."""
    def __init__(self):self.pending=b'';self.skipping=False;self.oversized=False;self.usage=None

    def line(self, data):
        if not data.startswith(b'data:'):return
        try:
            value=json.loads(data[5:])
            if isinstance(value,dict) and isinstance(value.get('usage'),dict):self.usage=value['usage']
        except (ValueError,UnicodeError):pass

    def feed(self, data: bytes):
        for part in data.splitlines(keepends=True):
            ended=part.endswith(b'\n')
            if not self.skipping:
                if len(self.pending)+len(part)>256*1024:
                    self.pending=b'';self.skipping=True;self.oversized=True
                else:self.pending+=part
            if ended:
                if not self.skipping:self.line(self.pending)
                self.pending=b'';self.skipping=False

    def finish(self):
        if self.pending and not self.skipping:self.line(self.pending)
