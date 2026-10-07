"""Package only tracked source; never walk a deployment's data directory."""
import hashlib
import io
from pathlib import Path
import re
import subprocess
import tarfile


def package(output=Path('/tmp/bgl-package')):
    root=Path(__file__).resolve().parents[1]
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    if not re.fullmatch(r'[0-9a-f]{40}',commit):raise RuntimeError('Invalid commit')
    output.mkdir(parents=True,exist_ok=True)
    data=subprocess.check_output(['git','archive','--format=tar',commit],cwd=root)
    # Defense in depth: reject accidental tracked private files before publishing.
    with tarfile.open(fileobj=io.BytesIO(data)) as source:
        members=source.getmembers()
        for member in members:
            parts=Path(member.name).parts
            if any(p in ('instance','backups','.git','.venv','__pycache__') for p in parts) or (
                member.name!='.env.example' and any(p.startswith('.env') for p in parts)
            ) or member.name.endswith(('.db','.pem','.key','.sqlite','.sqlite3')):
                raise RuntimeError('Private file is tracked: '+member.name)
        dest=output/'blackgoldlink-source.tar.gz'
        with tarfile.open(dest,'w:gz') as target:
            for member in members:
                target.addfile(member,source.extractfile(member) if member.isfile() else None)
            marker=(commit+'\n').encode();info=tarfile.TarInfo('.bgl-commit');info.size=len(marker)
            target.addfile(info,io.BytesIO(marker))
    (output/'SHA256SUMS').write_text(hashlib.sha256(dest.read_bytes()).hexdigest()+'  blackgoldlink-source.tar.gz\n')
    return dest


if __name__=='__main__':print(package())
