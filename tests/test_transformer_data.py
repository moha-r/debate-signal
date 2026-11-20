"""Data boundary and readable-input contracts for the transformer candidate."""

import unittest

import pandas as pd

from prepare_transformer_data import clean_transformer_text, split_fit_validation, validate_supplement


class TransformerDataContracts(unittest.TestCase):
    def test_keeps_negation_punctuation_and_quoted_speech(self):
        text = 'I do not think you are an "idiot".'
        self.assertEqual(clean_transformer_text(text), text)

    def test_restores_export_markers_and_removes_markup_and_links(self):
        text = 'NEWLINE_TOKEN <b>You are not wrong.</b> TAB_TOKEN https://example.org'
        self.assertEqual(clean_transformer_text(text), 'You are not wrong.')

    def test_normalizes_typographic_apostrophe_without_stemming(self):
        self.assertEqual(clean_transformer_text('You aren’t discussing policies.'), "You aren't discussing policies.")

    def test_stratified_validation_does_not_overlap_fitting(self):
        frame = pd.DataFrame({'rev_id': range(100), 'label': [0] * 80 + [1] * 20})
        fit, validation = split_fit_validation(frame, seed=1842, fraction=.2)
        self.assertEqual(len(fit), 80)
        self.assertEqual(len(validation), 20)
        self.assertFalse(set(fit.rev_id) & set(validation.rev_id))
        self.assertEqual(int(validation.label.sum()), 4)

    def test_supplement_rejects_audit_overlap_after_normalization(self):
        with self.assertRaises(ValueError):
            validate_supplement([{'text': '<p>You are an idiot.</p>', 'label': 1}], {'you are an idiot'})

    def test_supplement_rejects_duplicate_or_conflicting_text(self):
        with self.assertRaises(ValueError):
            validate_supplement([{'text': 'The idea is weak.', 'label': 0}, {'text': 'THE IDEA IS WEAK', 'label': 1}], set())

    def test_supplement_returns_readable_text_and_binary_labels(self):
        result = validate_supplement([{'text': 'The estimates need checking.', 'label': 0}], set())
        self.assertEqual(result[0]['text'], 'The estimates need checking.')
        self.assertEqual(result[0]['label'], 0)


if __name__ == '__main__':
    unittest.main()
