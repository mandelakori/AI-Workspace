"""Scoped, hash-checked source mutations. No fuzzy matching or code execution."""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from time import time

from .changes import validate_changes
from .lock import file_lock
from .workspace import contained


class EditRejected(ValueError):
    def __init__(self, code: str, message: str, **details):
        super().__init__(message)
        self.diagnostic = {"code":code,"error":message,"unchanged":True,**details}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def newline(data: bytes) -> bytes | None:
    """Recognize uniform LF/CRLF only; never normalize a source file."""
    rest=data.replace(b'\r\n',b'')
    if b'\r' in rest or b'\r\n' in data and b'\n' in rest:
        raise EditRejected('unsupported_newlines','Mixed line endings or bare CR are unsupported; no bytes changed.')
    return b'\r\n' if b'\r\n' in data else b'\n' if b'\n' in data else None


def adapt(data: bytes, style: bytes | None) -> bytes:
    own=newline(data)
    return data.replace(own,style) if own and style and own!=style else data


def inspected_window(before: bytes, name: str, current: str, location: dict,
                     inspections: Path | None) -> tuple[int, int]:
    """A locator narrows matching to lines actually issued by controller focus."""
    from .execution_context import excerpt_key
    if (not isinstance(location,dict) or set(location)-{'evidence_key','line','end_line'}
            or not isinstance(location.get('evidence_key'),str)
            or not re.fullmatch('[a-f0-9]{64}',location['evidence_key'])
            or type(location.get('line')) is not int
            or type(location.get('end_line',location.get('line'))) is not int or inspections is None):
        raise EditRejected('invalid_location','Use a focus evidence_key and inspected line/end_line, bound to this hash.')
    try:
        record=json.loads((inspections/f"{location['evidence_key']}.json").read_bytes())
        if (excerpt_key(record)!=location['evidence_key'] or record['path']!=name
                or record['sha256']!=current or not record['source']):
            raise ValueError('stale or unrelated inspection')
        lines=before.decode('utf-8').splitlines(keepends=True)
        first=record['line']-1;count=len(record['source'].splitlines(keepends=True))
        low=location['line']-1;high=location.get('end_line',location['line'])
        if (not 0<=first<=low<high<=first+count<=len(lines)
                or ''.join(lines[first:first+count]).encode('utf-8')!=record['source'].encode('utf-8')):
            raise ValueError('location is outside the exact inspected bytes')
        return len(''.join(lines[:low]).encode('utf-8')),len(''.join(lines[:high]).encode('utf-8'))
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        raise EditRejected('invalid_location','Inspection missing, changed, stale or outside the requested lines. Use fresh focus evidence for this exact file/hash.') from None


def apply_edit(workspace: Path, roots: tuple[str, ...], args: dict, lock: Path,
               deadline: float | None = None, *, inspections: Path | None = None) -> dict:
    required={"path","expected_sha256","old","new","mode"}
    if (not isinstance(args,dict) or not required<=set(args) or set(args)-required-{'location'}
            or not all(isinstance(args.get(k),str) for k in required)
            or args['mode'] not in {'replace','before','after','create'}):
        raise EditRejected('invalid_arguments','Use path, expected_sha256, old, new and mode (replace/before/after/create).')
    name=args['path'];validate_changes([name],roots)
    if len(args['old'].encode('utf-8'))>1200 or len(args['new'].encode('utf-8'))>3000:
        raise EditRejected('edit_too_large','Use a short exact anchor (<=1200 bytes) and new text <=3000 bytes.',path=name)
    create=args['mode']=='create'
    if create and 'location' in args:
        raise EditRejected('invalid_location','Creation cannot use an existing-source location.',path=name)
    if (create and (args['expected_sha256']!='absent' or args['old'])
            or not create and (not re.fullmatch('[a-f0-9]{64}',args['expected_sha256']) or not args['old'])):
        raise EditRejected('invalid_anchor','Existing files require a SHA-256 from focus and nonempty exact old text. Creation requires absent and empty old.',path=name)
    def check_deadline():
        if deadline is not None and time()>=deadline:
            raise EditRejected('deadline_expired','The edit deadline has expired.',path=name)
    with file_lock(lock):
        check_deadline();path=contained(workspace,name)
        def read_current():
            with path.open('rb') as stream:data=stream.read(256*1024+1)
            if len(data)>256*1024:raise EditRejected('invalid_source','Source grew beyond 256 KiB.',path=name)
            return data
        if not path.parent.is_dir():
            raise EditRejected('missing_parent','Parent directory must already exist in the staged workspace.',path=name)
        if create:
            if path.exists():raise EditRejected('create_conflict','Path already exists; inspect its current hash.',path=name)
            before=b'';mode=0o600
        else:
            if not path.is_file() or path.stat().st_size>256*1024:
                raise EditRejected('invalid_source','Edit an existing text file <=256 KiB.',path=name)
            before=read_current();mode=stat.S_IMODE(path.stat().st_mode)
            before.decode('utf-8')
            current=sha(before)
            hint={'path':name,'line':1}
            for line in args['old'].splitlines():
                if line.strip() and before.count(line.encode())==1:
                    hint['line']=before[:before.index(line.encode())].count(b'\n')+1;break
            details={'path':name,'actual_sha256':current,'focus_arguments':hint}
            if current!=args['expected_sha256']:
                raise EditRejected('stale_source','Source hash changed. Reinspect with focus, then retry using its current SHA-256.',**details)
        old=args['old'].encode('utf-8');new=args['new'].encode('utf-8')
        style=newline(before);newline(old);new=adapt(new,style)
        if len(new)>3000:
            raise EditRejected('edit_too_large','New text exceeds 3000 bytes after line-ending adaptation.',path=name)
        adapted=False
        if create:
            after=new;position=0
        else:
            low,high=inspected_window(before,name,current,args['location'],inspections) if 'location' in args else (0,len(before))
            if before.find(old,low,high)<0:
                adapted_old=adapt(old,style)
                adapted=adapted_old!=old
                old=adapted_old
            if len(old)>1200:
                raise EditRejected('edit_too_large','Anchor exceeds 1200 bytes after line-ending adaptation.',**details)
            positions=[];at=before.find(old,low,high)
            while at>=0 and len(positions)<5:
                positions.append(at);at=before.find(old,at+1,high)  # Count overlapping occurrences too.
            if len(positions)!=1:
                raise EditRejected('anchor_mismatch' if not positions else 'ambiguous_anchor',
                    'Anchor must match exactly once. Use a unique exact anchor or focus evidence_key with a location line/end_line narrowing the inspected region. Only uniform LF/CRLF adaptation is allowed; no fuzzy replacement.',
                    **details,anchor_matches=len(positions),more_matches=at>=0,matching_lines=[before[:p].count(b'\n')+1 for p in positions])
            position=positions[0]
            if (before[max(0,position-1):position+1]==b'\r\n'
                    or before[position+len(old)-1:position+len(old)+1]==b'\r\n'):
                raise EditRejected('unsupported_newlines','Anchor splits a CRLF pair. Inspect and anchor a complete source line.',**details)
            if args['mode']=='replace':after=before[:position]+new+before[position+len(old):]
            elif args['mode']=='before':after=before[:position]+new+before[position:]
            else:after=before[:position+len(old)]+new+before[position+len(old):]
        newline(after)  # Reject unsupported endings created at splice boundaries.
        if len(after)>256*1024:raise EditRejected('result_too_large','Result exceeds 256 KiB.',path=name)
        if not create and after==before:
            raise EditRejected('no_change','The requested edit would not change the source.',**details)
        if path.suffix.lower()=='.py':
            try:ast.parse(after.decode('utf-8'),filename=name)
            except (SyntaxError,ValueError,RecursionError) as error:
                raise EditRejected('syntax_error',str(error)[:250],path=name,
                    **({'actual_sha256':sha(before),'focus_arguments':{'path':name,'line':min(getattr(error,'lineno',None) or 1,max(1,len(before.decode('utf-8').splitlines())))}} if not create else {})) from None
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.aiwork-edit-',delete=False) as stream:
                temporary=Path(stream.name);stream.write(after);stream.flush();os.fsync(stream.fileno())
            os.chmod(temporary,mode)
            # Re-resolve links and recheck content immediately before commit under the session lock.
            contained(workspace,name);check_deadline()
            if create:
                try:
                    if os.name=='nt':
                        os.rename(temporary,path)  # Windows rename refuses an existing destination.
                        temporary=None
                    else:os.link(temporary,path)  # POSIX link also refuses an existing destination.
                except FileExistsError:raise EditRejected('create_conflict','Path appeared during creation.',path=name) from None
            else:
                latest=read_current()
                if latest!=before:
                    raise EditRejected('stale_source','Source changed during edit preparation. Reinspect before retrying.',
                        path=name,actual_sha256=sha(latest),focus_arguments={'path':name,'line':1})
                os.replace(temporary,path);temporary=None
        finally:
            if temporary is not None:temporary.unlink(missing_ok=True)
        return {'path':name,'before_sha256':'absent' if create else sha(before),'sha256':sha(after),
                'newline':{b'\n':'LF',b'\r\n':'CRLF',None:'none'}[style],
                'anchor_newline_adapted':adapted,'matched_bytes':[position,position+len(old)],
                'mode':args['mode'],'line':before[:position].count(b'\n')+1,'applied':True,'passed':True,
                'stdout':'','stderr':''}
