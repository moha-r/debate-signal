"""Local extractive answer scoring against the model's no-answer token."""
from functools import lru_cache
from threading import Lock

MODEL_ID = 'deepset/minilm-uncased-squad2'
REVISION = '934656cdda79824eabf503ed56e15c01ddbdbe3f'
FILES = ('config.json', 'vocab.txt', 'special_tokens_map.json',
         'tokenizer_config.json', 'model.safetensors')
_lock = Lock()


def checkpoint(local_only=True):
    from huggingface_hub import snapshot_download
    return snapshot_download(MODEL_ID, revision=REVISION, local_files_only=local_only,
                             allow_patterns=FILES)


@lru_cache(maxsize=1)
def load_extractor():
    from huggingface_hub.errors import LocalEntryNotFoundError
    try:
        path = checkpoint()
    except LocalEntryNotFoundError:
        return None
    from transformers import AutoModelForQuestionAnswering, AutoTokenizer
    return (AutoTokenizer.from_pretrained(path, local_files_only=True),
            AutoModelForQuestionAnswering.from_pretrained(path, local_files_only=True).eval())


def best_span(starts, ends, offsets, context_indices, null_index=0):
    """Return character offsets and answer logit minus the null logit."""
    null = starts[null_index] + ends[null_index]
    indices = list(context_indices)
    selected = None
    for i, start in enumerate(indices):
        for end in indices[i:i + 24]:
            score = float(starts[start] + ends[end] - null)
            if selected is None or score > selected[2]:
                selected = (offsets[start][0], offsets[end][1], score)
    return selected


def extract_answers(questions, statement):
    if not questions:
        return []
    import torch
    with _lock:
        extractor = load_extractor()
        if extractor is None:
            return [None] * len(questions)
        tokenizer, model = extractor
        # Bound the query as well as the extractable passage, including unusual ASR strings.
        questions = [tokenizer.decode(tokenizer(q, add_special_tokens=False, truncation=True,
                                                max_length=80)['input_ids']) for q in questions]
        encoded = tokenizer(questions, [statement] * len(questions), padding=True,
                            truncation='only_second', max_length=320, return_tensors='pt',
                            return_offsets_mapping=True)
        offsets = encoded.pop('offset_mapping').tolist()
        with torch.inference_mode():
            logits = model(**encoded)
        answers = []
        for n, mapping in enumerate(offsets):
            indices = [i for i, sequence in enumerate(encoded.sequence_ids(n))
                       if sequence == 1 and mapping[i][0] < mapping[i][1]]
            span = best_span(logits.start_logits[n].tolist(), logits.end_logits[n].tolist(),
                             mapping, indices)
            if span is None:
                answers.append(None)
            else:
                start, end, margin = span
                answers.append({'text':statement[start:end], 'start':start, 'end':end, 'margin':margin})
        return answers


if __name__ == '__main__':
    print(checkpoint(local_only=False))
