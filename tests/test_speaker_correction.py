from unittest import TestCase

from moderation_session import correct_voice_speaker


class SpeakerCorrectionTests(TestCase):
    def test_correction_updates_linked_alert_and_preserves_review(self):
        initial = {
            "turns": [{"number": 1, "speaker": "Unknown", "source": "voice"},
                      {"number": 2, "speaker": "A", "source": "text"}],
            "alerts": [{"turn": 1, "speaker": "Unknown", "status": "Reviewed"},
                       {"turn": 2, "speaker": "A", "status": "Pending"}],
        }
        corrected = correct_voice_speaker(initial, 1, "B")
        self.assertEqual([turn["speaker"] for turn in corrected["turns"]], ["B", "A"])
        self.assertEqual([alert["speaker"] for alert in corrected["alerts"]], ["B", "A"])
        self.assertEqual(corrected["alerts"][0]["status"], "Reviewed")
        self.assertEqual(initial["turns"][0]["speaker"], "Unknown")
        with self.assertRaises(ValueError):
            correct_voice_speaker(initial, 2, "B")
