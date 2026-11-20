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


if __name__=='__main__':unittest.main()
