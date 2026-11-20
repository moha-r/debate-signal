"""Prepare the pinned research checkpoint in the Hugging Face cache."""
import hashlib
from huggingface_hub import hf_hub_download, snapshot_download
from dialogue_relations import MODEL_ID, MODEL_REVISION


def main():
    snapshot_download(
        MODEL_ID, revision=MODEL_REVISION,
        allow_patterns=['config.json', 'tokenizer.json', 'tokenizer_config.json', 'pytorch_model.bin', 'README.md'],
    )
    path = hf_hub_download(MODEL_ID, revision=MODEL_REVISION, filename='pytorch_model.bin', local_files_only=True)
    with open(path, 'rb') as checkpoint:
        digest = hashlib.file_digest(checkpoint, 'sha256').hexdigest()
    expected = '144db6725e51503d48468295b0ce1fd80c2a10901be4d8cefd74dc9de9dd7ebb'
    if digest != expected:
        raise ValueError('The dialogue checkpoint does not match the pinned weight checksum.')
    print('Verified pinned dialogue relation checkpoint. License CC BY-NC-SA 4.0.')


if __name__ == '__main__':
    main()
