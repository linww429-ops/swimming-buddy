"""Verify the exact distributable file set and hashes, without modifying it."""
import hashlib,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'PACKAGE_MANIFEST.json').read_text(encoding='utf-8'))
errors=[]
listed=set(manifest['files'])
actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p!=root/'PACKAGE_MANIFEST.json' and p.relative_to(root).parts[0]!='.git' and '__pycache__' not in p.parts and p.suffix!='.pyc'}
for name in sorted(actual-listed):errors.append('UNLISTED '+name)
for name,expected in manifest['files'].items():
 p=root/name
 if not p.resolve().is_relative_to(root.resolve()):errors.append('UNSAFE PATH '+name)
 elif not p.is_file():errors.append('MISSING '+name)
 elif hashlib.sha256(p.read_bytes()).hexdigest()!=expected:errors.append('HASH MISMATCH '+name)
print(json.dumps({'version':manifest['version'],'files':len(listed),'ok':not errors,'errors':errors},ensure_ascii=False,indent=2))
sys.exit(bool(errors))
