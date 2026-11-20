import unittest
from unittest.mock import patch

import app


class GradioClassifierTests(unittest.TestCase):
    def test_displayed_class_uses_the_moderation_threshold(self):
        with patch.object(app, "load_attack_bundle", return_value={"threshold": 0.35}), \
                patch.object(app, "score_attack", side_effect=[0.35, 0.349]):
            flagged, processed = app.analyze_sentence("I don't think so.")
            below_threshold, _ = app.analyze_sentence("I don't think so.")

        self.assertEqual(processed, "i do not think so")
        self.assertIn("<h3>Personal attack</h3>", flagged)
        self.assertIn("35.00%", flagged)
        self.assertIn("65.00%", flagged)
        self.assertIn("<h3>No personal attack</h3>", below_threshold)

    def test_empty_or_noise_only_input_does_not_load_the_model(self):
        with patch.object(app, "load_attack_bundle") as load:
            for text in (None, "  ", "!!! https://example.com"):
                with self.subTest(text=text):
                    message, processed = app.analyze_sentence(text)
                    self.assertIn("Enter an English sentence", message)
                    self.assertEqual(processed, "")
        load.assert_not_called()

    def test_sentence_check_is_the_first_tab(self):
        components = app.build_app().get_config_file()["components"]
        labels = [item["props"]["label"] for item in components if item["type"] == "tabitem"]
        self.assertEqual(labels, ["Sentence check", "Debate workspace"])
