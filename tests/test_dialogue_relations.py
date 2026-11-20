"""Contracts for loading, mapping and bounded pair inference."""
import unittest
from unittest.mock import patch


class DialogueRelationsContracts(unittest.TestCase):
    def test_rephrase_stays_separate_from_argumentative_support(self):
        from dialogue_relations import map_probabilities
        score=map_probabilities([.1,.2,.3,.4])
        self.assertAlmostEqual(score['support'],.2)
        self.assertAlmostEqual(score['attack'],.3)
        self.assertAlmostEqual(score['none'],.5)
        self.assertAlmostEqual(sum(score[k] for k in ('support','attack','none')),1.)

    def test_only_six_retrieved_candidates_are_sent_to_cross_encoder(self):
        from dialogue_relations import score_candidates
        candidates=[{'number':i,'text':f'Candidate statement {i}'} for i in range(12)]
        predicted=[{'support':.8,'attack':.1,'none':.1}]*6
        class PairModel:
            def score(self,pairs):
                self.pairs=pairs
                return predicted
        model=PairModel()
        scores=score_candidates(model,'A new statement.',candidates)
        self.assertEqual(len(model.pairs),6)
        self.assertEqual(model.pairs[0],('A new statement.','Candidate statement 0'))
        self.assertEqual(len(scores),12)
        self.assertEqual(scores[8],{'support':0.,'attack':0.,'none':1.})

    def test_current_backend_metadata_identifies_fallback(self):
        from dialogue_relations import relation_backend
        with patch('dialogue_relations.load_cross_encoder',return_value=None):
            self.assertEqual(relation_backend()['backend'],'local-logistic')

    def test_model_label_mismatch_is_rejected(self):
        from dialogue_relations import validate_labels
        with self.assertRaises(ValueError):
            validate_labels({0:'Conflict',1:'Inference',2:'No-Relation',3:'Rephrase'})

    def test_contextual_selector_can_abstain_or_choose_a_different_target(self):
        from argument_link_selector import choose_link

        candidates = [(0.84, 2, 'support'), (0.78, 5, 'attack')]
        self.assertIsNone(choose_link(candidates, threshold=.63, margin=.14))
        self.assertEqual(choose_link(candidates, threshold=.63, margin=.04), candidates[0])
        self.assertIsNone(choose_link([(0.61, 2, 'support')], threshold=.63, margin=.14))

    def test_contextual_selection_uses_candidate_competition(self):
        from argument_link_selector import contextual_features

        source = {'number': 7, 'speaker': 'B', 'text': 'Borrowing the kits leaves work unfinished.'}
        raw = {'support': .8, 'attack': .1, 'none': .1, 'rephrase': .0}
        candidates = [
            {'number': 2, 'speaker': 'A', 'text': 'We should lend kits to students.', 'similarity': .7, 'raw': raw},
            {'number': 6, 'speaker': 'B', 'text': 'Kits can have missing components.', 'similarity': .5, 'raw': raw},
        ]
        rows = contextual_features(source, candidates)
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(rows[0][-5], .2)
        self.assertAlmostEqual(rows[1][-5], -.2)

    def test_direct_reply_anchor_requires_the_immediately_previous_turn(self):
        from relation_context import is_grounded_reply

        prior = {'number': 5, 'speaker': 'A', 'text': 'Students should give oral exams.'}
        source = {'number': 6, 'speaker': 'B', 'text': 'That would penalize nervous students.'}
        self.assertTrue(is_grounded_reply(source, prior, 'attack', probability=.54, similarity=.37, candidate_count=1))
        self.assertFalse(is_grounded_reply({**source, 'number': 8}, prior, 'attack', probability=.95, similarity=.7, candidate_count=1))
        self.assertFalse(is_grounded_reply({**source, 'text': 'Oral exams should use different rooms.'}, prior,
                                           'support', probability=.8, similarity=.63, candidate_count=1))


if __name__=='__main__':unittest.main()
