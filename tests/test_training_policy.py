import unittest

from training_policy import select_alert_threshold


class TrainingPolicyContracts(unittest.TestCase):
    def test_maximizes_recall_subject_to_precision(self):
        rule = select_alert_threshold([1, 1, 0, 0], [.9, .6, .55, .1], target_precision=1.0, minimum_alerts=1)
        self.assertGreater(rule['threshold'], .55)
        self.assertLessEqual(rule['threshold'], .6)
        self.assertEqual(rule['precision'], 1.0)
        self.assertEqual(rule['recall'], 1.0)
        self.assertTrue(rule['precision_target_met'])

    def test_infeasible_precision_target_is_reported(self):
        rule = select_alert_threshold([0, 1], [.9, .5], target_precision=1.0, minimum_alerts=1)
        self.assertFalse(rule['precision_target_met'])
        self.assertEqual(rule['precision'], .5)

    def test_rejects_no_positive_references(self):
        with self.assertRaises(ValueError):
            select_alert_threshold([0, 0], [.1, .2], minimum_alerts=1)

    def test_rejects_invalid_or_mismatched_scores(self):
        for labels, scores in (([1], []), ([1], [float('nan')]), ([1], [1.1])):
            with self.subTest(scores=scores), self.assertRaises(ValueError):
                select_alert_threshold(labels, scores, minimum_alerts=1)


if __name__ == '__main__':
    unittest.main()
