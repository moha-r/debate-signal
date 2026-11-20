"""Deterministic workflow contracts, separate from linguistic model accuracy."""

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

import numpy as np

import app
from moderation_session import analyze_turn, new_session, review_alert
from nlp_pipeline import preprocess_text
from topic_relevance import TopicMonitor


TOPIC = "Schools should require uniforms"


class FakeEncoder:
    def encode(self, text, normalize_embeddings=True):
        # Explicit fixture scores; this does not test MiniLM's language understanding.
        if text == TOPIC or "uniform" in text.lower():
            return np.array([1.0, 0.0])
        return np.array([0.0, 1.0])


class FakePipeline:
    def decision_function(self, texts):
        return np.array([0.8 if "idiot" in text.lower() else 0.1 for text in texts])


class FakeSigmoid:
    def predict_proba(self, margins):
        p = margins[:, 0]
        return np.column_stack([1 - p, p])


def resources(threshold=0.35):
    return (
        {"pipeline": FakePipeline(), "sigmoid": FakeSigmoid(), "threshold": threshold},
        {"threshold": 0.5, "backend": "minilm", "use_context": True},
        FakeEncoder(),
    )


class TopicContracts(unittest.TestCase):
    def monitor(self):
        return TopicMonitor(TOPIC, 0.5, encoder=FakeEncoder())

    def test_requires_two_off_topic_turns(self):
        monitor = self.monitor()
        self.assertFalse(monitor.process("My cat is sleeping.")["alert"])
        self.assertTrue(monitor.process("Its blanket is blue.")["alert"])

    def test_latch_prevents_repeated_alerts(self):
        monitor = self.monitor()
        alerts = [monitor.process(text)["alert"] for text in ("My cat sleeps", "Its bed is red", "It ate fish", "It likes toys")]
        self.assertEqual(alerts, [False, True, False, False])

    def test_return_rearms_next_drift(self):
        monitor = self.monitor()
        results = [monitor.process(text)["alert"] for text in (
            "My cat sleeps", "Its bed is red", "Uniform costs matter", "A guitar is blue", "Its strings broke"
        )]
        self.assertEqual(results, [False, True, False, False, True])

    def test_acknowledgement_preserves_drift_count(self):
        monitor = self.monitor()
        monitor.process("My cat sleeps")
        ack = monitor.process("Okay!")
        self.assertEqual(ack["state"], "unclear")
        self.assertEqual(ack["off_topic_count"], 1)
        self.assertFalse(ack["alert"])
        self.assertTrue(monitor.process("Its bed is blue")["alert"])

    def test_short_followup_can_inherit_previous_direct_relevance(self):
        monitor = self.monitor()
        monitor.process("A uniform needs funding")
        result = monitor.process("Who pays?")
        self.assertTrue(result["used_context"])
        self.assertEqual(result["state"], "on_topic")

    def test_inherited_context_cannot_chain_indefinitely(self):
        monitor = self.monitor()
        monitor.process("A uniform needs funding")
        monitor.process("Who pays?")
        result = monitor.process("How much?")
        self.assertFalse(result["used_context"])
        self.assertEqual(result["state"], "off_topic")

    def test_long_followup_does_not_inherit(self):
        monitor = self.monitor()
        monitor.process("A uniform needs funding")
        result = monitor.process("What about the very large blue guitar that I purchased yesterday?")
        self.assertFalse(result["used_context"])

    def test_ack_breaks_context_inheritance(self):
        monitor = self.monitor()
        monitor.process("A uniform needs funding")
        monitor.process("Yes")
        self.assertFalse(monitor.process("Who pays?")["used_context"])

    def test_empty_text_does_not_create_drift(self):
        monitor = self.monitor()
        for text in ("", "   ", "!!!"):
            result = monitor.process(text)
            self.assertEqual(result["state"], "unclear")
            self.assertEqual(result["off_topic_count"], 0)

    def test_floor_management_does_not_count_as_drift_even_without_punctuation(self):
        monitor = self.monitor()
        for text in ("What do you think?", "Um, what do you think about that", "Okay, and you?",
                     "what do you", "think", "Go ahead.", "Can you repeat that?",
                     "Yeah, okay. Tell me more."):
            with self.subTest(text=text):
                result = monitor.process(text)
                self.assertEqual(result["state"], "unclear")
                self.assertEqual(result["reason"], "conversation_management")
                self.assertEqual(result["off_topic_count"], 0)
                self.assertFalse(result["alert"])

    def test_generic_opening_cannot_hide_a_specific_detour(self):
        monitor = self.monitor()
        detour = monitor.process("What do you think about football?")
        self.assertEqual(detour["state"], "off_topic")
        self.assertFalse(detour["alert"])
        self.assertTrue(monitor.process("Football scores.")["alert"])

    def test_named_subject_is_scored_without_the_generic_prompt(self):
        monitor = self.monitor()
        # The generic wording can skew cosine scores in either direction.
        with patch.object(monitor, "similarity", side_effect=lambda text: 0.0 if text == "football" else 1.0) as similarity:
            result = monitor.process("Well, what do you think about football?")
        similarity.assert_called_once_with("football")
        self.assertEqual(result["state"], "off_topic")

    def test_neutral_phrases_do_not_interrupt_or_extend_a_genuine_detour(self):
        monitor = self.monitor()
        self.assertFalse(monitor.process("Video games.")["alert"])
        neutral = monitor.process("What do you think of that?")
        self.assertEqual(neutral["off_topic_count"], 1)
        self.assertFalse(neutral["alert"])
        self.assertTrue(monitor.process("Football scores.")["alert"])

    def test_constructor_rejects_invalid_policy(self):
        for topic, threshold in (("Too short", .5), (TOPIC, 0), (TOPIC, 1), (TOPIC, float("nan"))):
            with self.subTest(topic=topic, threshold=threshold), self.assertRaises(ValueError):
                TopicMonitor(topic, threshold, encoder=FakeEncoder())


class SessionContracts(unittest.TestCase):
    def setUp(self):
        self.resources = resources()
        self.state = new_session(TOPIC, self.resources)

    def add(self, state, text, speaker="A"):
        return analyze_turn(state, speaker, text, self.resources)

    def test_opening_turn_exchange_cannot_create_a_topic_drift_alert(self):
        state = self.add(self.state, "What do you think?")
        state = self.add(state, "Well, you first.", speaker="B")
        self.assertEqual(state["alerts"], [])
        for turn in state["turns"]:
            self.assertEqual(turn["topic"]["reason"], "conversation_management")
        self.assertEqual(state["turns"][0]["argument"]["role"], "question")

    def test_new_sessions_have_distinct_identifiers_and_state(self):
        other = new_session(TOPIC, self.resources)
        updated = self.add(self.state, "You are an idiot")
        self.assertNotEqual(self.state["id"], other["id"])
        self.assertEqual(other["turns"], [])
        self.assertEqual(other["alerts"], [])
        self.assertEqual(self.state["turns"], [])
        self.assertEqual(len(updated["turns"]), 1)

    def test_previous_state_not_mutated(self):
        snapshot = deepcopy(self.state)
        updated = self.add(self.state, "Uniform prices vary", "B")
        self.assertEqual(self.state, snapshot)
        updated["monitor"]["previous_text"] = "changed"
        self.assertEqual(self.state, snapshot)

    def test_speaker_and_turn_numbers_are_preserved(self):
        state = self.add(self.state, "Uniform costs matter", "B")
        state = self.add(state, "You are an idiot", "A")
        self.assertEqual([(t["number"], t["speaker"]) for t in state["turns"]], [(1, "B"), (2, "A")])
        self.assertEqual(state["alerts"][0]["speaker"], "A")
        self.assertEqual(state["alerts"][0]["turn"], 2)

    def test_both_alert_types_can_trigger_same_turn(self):
        state = self.add(self.state, "My cat sleeps")
        state = self.add(state, "You are an idiot", "B")
        self.assertEqual([a["kind"] for a in state["alerts"]], ["Personal attack", "Topic drift"])
        self.assertEqual([a["id"] for a in state["alerts"]], ["R1", "R2"])
        self.assertTrue(all(a["speaker"] == "B" and a["turn"] == 2 for a in state["alerts"]))

    def test_attack_on_topic_is_still_an_attack(self):
        state = self.add(self.state, "You are an idiot about uniform costs")
        self.assertTrue(state["turns"][0]["personal_attack"])
        self.assertEqual(state["turns"][0]["topic"]["state"], "on_topic")

    def test_threshold_equality_is_positive(self):
        state = analyze_turn(self.state, "A", "You are an idiot", resources(.8))
        self.assertTrue(state["turns"][0]["personal_attack"])

    def test_invalid_inputs_do_not_mutate_state(self):
        snapshot = deepcopy(self.state)
        for speaker, text in (("C", "hello"), ("A", ""), ("B", "   "), ("A", "https://example.org"), ("A", "<p></p>")):
            with self.subTest(speaker=speaker, text=text), self.assertRaises(ValueError):
                self.add(self.state, text, speaker)
            self.assertEqual(self.state, snapshot)

    def test_cannot_analyze_without_session(self):
        with self.assertRaises(ValueError):
            self.add(None, "Uniforms cost money")

    def test_model_failure_does_not_mutate_state(self):
        snapshot = deepcopy(self.state)
        with patch.object(self.resources[2], "encode", side_effect=RuntimeError("Encoder failed")):
            with self.assertRaises(RuntimeError):
                self.add(self.state, "Uniform prices vary")
        self.assertEqual(self.state, snapshot)

    def test_review_targets_only_selected_pending_alert(self):
        state = self.add(self.state, "My cat sleeps")
        state = self.add(state, "You are an idiot")
        updated = review_alert(state, "R2", "Dismissed")
        self.assertEqual([a["status"] for a in updated["alerts"]], ["Pending", "Dismissed"])
        self.assertEqual([a["status"] for a in state["alerts"]], ["Pending", "Pending"])
        updated = review_alert(updated, "R1", "Reviewed")
        self.assertEqual([a["status"] for a in updated["alerts"]], ["Reviewed", "Dismissed"])
        with self.assertRaises(ValueError):
            review_alert(updated, "R1", "Dismissed")

    def test_review_rejects_invalid_ids_decisions_and_missing_session(self):
        for state, ident, decision in ((None, "R1", "Reviewed"), (self.state, "R404", "Reviewed"), (self.state, "R1", "Approve")):
            with self.subTest(ident=ident, decision=decision), self.assertRaises(ValueError):
                review_alert(state, ident, decision)

    def test_session_state_is_json_serializable(self):
        state = self.add(self.state, "You are an idiot")
        self.assertEqual(json.loads(json.dumps(state)), state)


class RenderingAndPreprocessingContracts(unittest.TestCase):
    def test_html_is_escaped_in_topic_transcript_and_alert(self):
        res = resources()
        state = new_session(TOPIC + ' <img src=x onerror=alert(1)>', res)
        state = analyze_turn(state, "B", '<script>alert("x")</script> You are an idiot', res)
        status, transcript, queue, _ = app.render_session(state)
        self.assertNotIn("<img", status)
        self.assertNotIn("<script>", transcript + queue)
        self.assertIn("&lt;script&gt;", transcript)
        self.assertIn("&lt;script&gt;", queue)

    def test_probability_display_sums_to_one(self):
        with patch("moderation_session.load_resources", return_value=resources()):
            state = new_session(TOPIC)
            output = app.submit_turn(state, "A", "You are an idiot")
        probabilities = output[6]
        self.assertAlmostEqual(sum(probabilities.values()), 1)
        self.assertAlmostEqual(probabilities["Personal attack"], .8)

    def test_empty_render_and_error_are_explicit(self):
        self.assertIn("start a session", app.render_session(None)[0])
        with self.assertRaises(app.gr.Error):
            app.submit_turn(None, "A", "Some text")

    def test_negation_survives_preprocessing(self):
        for text in ("You are not stupid", "You aren't stupid", "I don't agree", "I cannot accept that"):
            with self.subTest(text=text):
                self.assertIn("not", preprocess_text(text).split())

    def test_formatting_preserves_model_input(self):
        original = "You are not an idiot"
        expected = preprocess_text(original)
        for variant in (original.upper(), "<p>" + original + "</p>", "You  are\nnot an idiot"):
            self.assertEqual(preprocess_text(variant), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
