"""Stable build identity across workers; never hash databases, secrets or timestamps."""
import hashlib
from pathlib import Path


def release_version(root):
    root=Path(root)
    files=list(root.glob('*.py'))
    for name in ('templates','static'):
        files.extend(path for path in (root/name).rglob('*') if path.is_file())
    files.extend(root/name for name in ('translations.json','requirements.txt') if (root/name).is_file())
    digest=hashlib.sha256()
    for path in sorted(files,key=lambda p:p.relative_to(root).as_posix()):
        name=path.relative_to(root).as_posix().encode()
        data=path.read_bytes()
        digest.update(len(name).to_bytes(8,'big'));digest.update(name)
        digest.update(len(data).to_bytes(8,'big'));digest.update(data)
    return digest.hexdigest()[:24]
