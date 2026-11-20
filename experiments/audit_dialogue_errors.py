"""Replay frozen fixtures and save the evidence behind each error."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from moderation_session import analyze_turn, load_resources, new_session

FIXTURES = ('argument_quality_audit', 'argument_repair_holdout', 'dialogue_quality_challenge_v3')


def link_cause(targets, prediction, trace):
    if not targets:
        return 'false_answer' if prediction['relation'] == 'answers' else 'false_argument_link'
    if prediction and prediction['relation'] == 'answers':
        return 'wrong_question'
    if trace['matched_responses']:
        return 'response_overrode_argument'
    if not trace.get('eligible_targets'):
        return 'source_or_target_role_gate'
    candidates = [row for row in trace['candidates'] if row['turn'] in targets]
    if not candidates:
        return 'target_not_retrieved' if set(targets) & set(trace['eligible_targets']) else 'target_ineligible'
    if all(row['state'] != 'ranked' for row in candidates):
        return candidates[0]['state']
    return 'wrong_ranked_target' if prediction else 'ambiguous_target'


def replay(output):
    if output.exists():
        raise FileExistsError(output)
    resources = load_resources()
    decisions, errors = [], []
    for fixture_name in FIXTURES:
        cases = json.loads((ROOT / 'data' / (fixture_name + '.json')).read_text())['cases']
        for case in cases:
            state = new_session(case['topic'], resources)
            for number, gold in enumerate(case['turns'], 1):
                trace = {}
                state = analyze_turn(state, gold['speaker'], gold['text'], resources, argument_trace=trace)
                turn = state['turns'][-1]
                link = trace['link']
                target = link['turn'] if link else None
                expected_links = gold['links']
                actual_answers = [response['turn'] for response in trace['matched_responses']
                                  if response['status'] != 'declined']
                record = {
                    'fixture': fixture_name, 'case': case['id'], 'turn': number,
                    'speaker': gold['speaker'], 'text': turn['text'], 'motion': case['topic'],
                    'expected_role': gold['role'], 'expected_links': expected_links,
                    'expected_answers': gold['answer_to'], 'actual_answers': actual_answers,
                    'latency_ms': turn['latency_ms'], **trace,
                }
                decisions.append(record)
                kinds = []
                if trace['role'] != gold['role']:
                    kinds.append('role')
                if target not in expected_links and (expected_links or target is not None):
                    kinds.append(link_cause(expected_links, link, trace))
                if set(actual_answers) != set(gold['answer_to']):
                    kinds.append('question_match')
                if turn['argument']['evidence_requested'] != gold['evidence_requested']:
                    kinds.append('evidence_request')
                if kinds:
                    errors.append({**record, 'error_types': kinds})
    output.mkdir(parents=True)
    for name, rows in [('decisions', decisions), ('errors', errors)]:
        (output / f'{name}.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))
    sources = ('argument_models.py', 'argument_link_selector.py', 'answer_extraction.py', 'conversation_insights.py',
               'dialogue_relations.py', 'moderation_session.py', 'question_tracker.py', 'relation_context.py')
    summary = {'turns': len(decisions), 'error_turns': len(errors),
               'errors': dict(Counter(kind for row in errors for kind in row['error_types'])),
               'source_hashes':{path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in sources}}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    replay(parser.parse_args().output)
