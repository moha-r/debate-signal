"""Restore a pinned AIFdb broadcast sample for local academic evaluation."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'results/dialogue_root_cause/moral_maze_manifest.json'
DESTINATION=ROOT/'data/raw/moral_maze'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=MANIFEST)
    parser.add_argument('--destination', type=Path, default=DESTINATION)
    args = parser.parse_args()
    manifest=json.loads(args.manifest.read_text())
    args.destination.mkdir(parents=True,exist_ok=True)
    for _, map_id, _, checksum in manifest['maps']:
        destination=args.destination/f'{map_id}.json'
        if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest()==checksum:
            continue
        with urlopen(f'https://aifdb.org/json/{map_id}',timeout=20) as response:
            data=response.read(3_000_001)
        if len(data)>3_000_000 or hashlib.sha256(data).hexdigest()!=checksum:
            raise ValueError(f'AIFdb map {map_id} differs from the pinned sample.')
        destination.write_bytes(data)
    (args.destination/'manifest.json').write_text(args.manifest.read_text())
    print(f"Verified {len(manifest['maps'])} AIFdb maps for local academic evaluation.")


if __name__=='__main__':
    main()
