"""Fetch the pinned, licensed microtext corpus for diagnostic evaluation only."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import urllib.request

COMMIT='6707c133de713130cabe647f2f218681d65fdc15'
EXPECTED_SHA256='19544acd64183537314a2c836ebda0e3c40807a0cdecae538519ca951418f1d9'
ROOT=Path(__file__).resolve().parent/'data/raw/arg-microtexts'


def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    target=ROOT/'source.tar.gz'
    raw=target.read_bytes() if target.exists() else None
    if raw is None or hashlib.sha256(raw).hexdigest()!=EXPECTED_SHA256:
        with urllib.request.urlopen(f'https://codeload.github.com/peldszus/arg-microtexts/tar.gz/{COMMIT}',timeout=35) as response:
            raw=response.read(60*1024*1024+1)
        if len(raw)>60*1024*1024 or hashlib.sha256(raw).hexdigest()!=EXPECTED_SHA256:
            raise ValueError('Corpus archive does not match the pinned checksum.')
        partial=target.with_suffix('.partial');partial.write_bytes(raw);partial.replace(target)
    with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:
        for member in archive.getmembers():
            selected=('/corpus/en/' in member.name and member.name.endswith('.xml')
                      or member.name.endswith(('/README.md','/corpus/arggraph.dtd','/topics_triggers.md')))
            if selected and member.isfile():
                if member.size>2*1024*1024: raise ValueError('Unexpected corpus member size.')
                (ROOT/Path(member.name).name).write_bytes(archive.extractfile(member).read())
    files=list(ROOT.glob('*.xml'))
    if len(files)!=112: raise ValueError('Expected 112 English corpus XML documents.')
    manifest={'repository':'https://github.com/peldszus/arg-microtexts','commit':COMMIT,
              'archive_sha256':EXPECTED_SHA256,'license':'CC BY-NC-SA 4.0',
              'usage':'External diagnostic only; not training or serving data.','xml_files':len(files)}
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Verified 112 English microtexts at the pinned commit. Diagnostic-only; see EXTERNAL_DATA_NOTICE.md.')


if __name__=='__main__': main()
