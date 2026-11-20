"""Download and verify the pinned, noncommercial Part 2 research corpus."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import urllib.request

COMMIT='99b652352212d69b76200f7ad85660b5b597c42a'
EXPECTED_SHA256='78584bc829bbc0d6d347356d2f9b5c31dccbb1da0bf64901dd16f2be165b6e87'
ROOT=Path(__file__).resolve().parent/'data/raw/arg-microtexts-part2'


def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    target=ROOT/'source.tar.gz'
    raw=target.read_bytes() if target.exists() else None
    if raw is None or hashlib.sha256(raw).hexdigest()!=EXPECTED_SHA256:
        with urllib.request.urlopen(f'https://codeload.github.com/discourse-lab/arg-microtexts-part2/tar.gz/{COMMIT}',timeout=35) as response:
            raw=response.read(30*1024*1024+1)
        if len(raw)>30*1024*1024 or hashlib.sha256(raw).hexdigest()!=EXPECTED_SHA256:
            raise ValueError('The archive does not match the pinned Part 2 checksum.')
        partial=target.with_suffix('.partial');partial.write_bytes(raw);partial.replace(target)
    with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:
        for member in archive.getmembers():
            selected=('/corpus/' in member.name and member.name.endswith('.xml')
                      or member.name.endswith(('/README.md','/topics_triggers.md','/arggraph.dtd')))
            if selected and member.isfile():
                if member.size>2*1024*1024: raise ValueError('Unexpected corpus member size.')
                (ROOT/Path(member.name).name).write_bytes(archive.extractfile(member).read())
    files=list(ROOT.glob('*.xml'))
    if len(files)!=171: raise ValueError('Expected 171 original English XML documents.')
    manifest={'repository':'https://github.com/discourse-lab/arg-microtexts-part2','commit':COMMIT,
              'archive_sha256':EXPECTED_SHA256,'license':'CC BY-NC-SA 4.0',
              'usage':'Research training/development/test with document-level partitions. Part 1 remains external diagnostic only.',
              'xml_files':len(files)}
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Verified 171 English Part 2 documents; see artifacts/ARGUMENT_MODEL_NOTICE.md.')


if __name__=='__main__':main()
