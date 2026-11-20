"""Timing, report grounding, context guardrails and durable feedback contracts."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

from conversation_insights import (apply_feedback, argument_for, participation, quotation_context,
                                   session_insights, voice_timing)
from moderation_session import analyze_turn, correct_voice_speaker, new_session
from session_store import SessionStore, feedback_records
from test_moderation_contract import resources, TOPIC


class TimingContracts(unittest.TestCase):
    def turn(self, recording, speaker, start, end):
        return {'voice_timing': voice_timing({'speaker_label': speaker, 'words': [
            {'start': start, 'end': end, 'word_is_final': True}]},recording)}

    def test_overlapping_word_intervals_are_not_counted_twice(self):
        report = participation([self.turn('one','A',0,1000), self.turn('one','A',500,1500)])
        self.assertEqual(report['seconds']['A'],1.5)

    def test_recording_reconnect_does_not_erase_previous_time(self):
        report = participation([self.turn('one','A',0,1000),self.turn('two','A',0,1000)])
        self.assertEqual(report['seconds']['A'],2)

    def test_missing_timing_is_not_estimated_from_words(self):
        report = participation([{'text': 'word '*1000}])
        self.assertEqual(report['timed_turns'],0)
        self.assertEqual(report['untimed_turns'],1)
        self.assertIsNone(report['shares']['A'])
        self.assertIsNone(report['dominant_speaker'])

    def test_unknown_word_does_not_inherit_confirmed_turn_label(self):
        timing=voice_timing({'speaker_label':'A','words':[
            {'start':0,'end':1000,'speaker':'UNKNOWN','word_is_final':True},
            {'start':1000,'end':2000,'word_is_final':True}]},'r')
        self.assertEqual([w['speaker'] for w in timing['intervals']],['Unknown','A'])

    def test_invalid_or_partial_timestamps_never_enter_totals(self):
        event={'words':[{'start':s,'end':e,'word_is_final':final} for s,e,final in
                        [(0,1,False),(4,2,True),(-1,4,True),(0,float('nan'),True),(True,2,True),(0,100,True)]]}
        self.assertEqual(len(voice_timing(event,'r')['intervals']),1)

    def test_balance_requires_enough_measured_speech_and_two_voices(self):
        self.assertIsNone(participation([self.turn('r','A',0,40000)])['dominant_speaker'])
        turns=[self.turn('r','A',0,30000),self.turn('r','B',30000,35000)]
        self.assertEqual(participation(turns)['dominant_speaker'],'A')
        turns.append(self.turn('r','Unknown',35000,70000))
        self.assertIsNone(participation(turns)['dominant_speaker'])

    def test_manual_speaker_correction_reassigns_measured_time(self):
        state={'turns':[dict(number=1,source='voice',speaker='A',**self.turn('r','A',0,3000))], 'alerts':[]}
        updated=correct_voice_speaker(state,1,'B')
        self.assertEqual(participation(updated['turns'])['seconds']['B'],3)
        self.assertEqual(participation(state['turns'])['seconds']['A'],3)

    def test_speaker_correction_removes_invalid_opponent_links(self):
        state={'turns':[
            {'number':1,'source':'voice','speaker':'A','argument':{'role':'claim','link':None}},
            {'number':2,'source':'voice','speaker':'B','argument':{'role':'rebuttal','link':{'turn':1}}}], 'alerts':[]}
        changed=correct_voice_speaker(state,1,'B')
        self.assertIsNone(changed['turns'][1]['argument']['link'])
        self.assertIsNotNone(state['turns'][1]['argument']['link'])


class ContextAndReportContracts(unittest.TestCase):
    def setUp(self):
        self.resources=resources()
        self.state=new_session(TOPIC,self.resources)

    def add(self,speaker,text):
        self.state=analyze_turn(self.state,speaker,text,self.resources)

    def test_reported_latency_includes_argument_extraction(self):
        import moderation_session
        original=moderation_session.argument_for
        clock=[1.0]
        def timed_argument(*args):
            result=original(*args)
            clock[0]+=.05
            return result
        with patch.object(moderation_session,'perf_counter',side_effect=lambda:clock[0]), patch.object(moderation_session,'argument_for',side_effect=timed_argument):
            self.add('A','Uniforms should be affordable for families.')
        self.assertAlmostEqual(self.state['turns'][-1]['latency_ms'],50,places=4)

    def test_quoted_metalinguistic_insult_retains_score_without_alert(self):
        self.add('A','The phrase "you are an idiot" is a personal attack and is unacceptable.')
        turn=self.state['turns'][-1]
        self.assertEqual(turn['attack_probability'],.8)
        self.assertFalse(turn['personal_attack'])
        self.assertTrue(turn['attack_context']['suppressed'])

    def test_quote_cannot_hide_a_direct_insult_outside_it(self):
        self.add('A','The phrase "hello" is unacceptable. You are an idiot.')
        self.assertTrue(self.state['turns'][-1]['personal_attack'])

    def test_argument_links_and_report_sources_are_real_earlier_turns(self):
        self.add('A','Uniform policies should protect families from high costs.')
        self.add('B','I disagree because uniform policies increase costs for families.')
        report=session_insights(self.state)
        self.assertEqual(report['arguments'][-1]['role'],'rebuttal')
        self.assertEqual(report['arguments'][-1]['link']['turn'],1)
        self.assertEqual(report['report']['disagreements'],[2])
        self.assertEqual(report['report']['claims'],[1])
        self.assertEqual(report['report']['reasons'],[2])

    def test_unrelated_rebuttal_does_not_get_fabricated_link(self):
        self.add('A','Uniform policies should protect families from high costs.')
        self.add('B','I disagree because my pet likes a different cushion.')
        self.assertIsNone(self.state['turns'][-1]['argument']['link'])

    def test_question_does_not_claim_evidence_was_supplied(self):
        self.add('A','What evidence supports the uniform policy?')
        self.add('B','My dog sleeps on the sofa.')
        question=session_insights(self.state)['report']['questions'][0]
        self.assertTrue(question['evidence_requested'])
        self.assertEqual(question['answer_turns'],[])

    def test_recent_context_can_survive_an_ack_without_becoming_a_new_anchor(self):
        from test_bounded_topic import Encoder
        bundle,policy,_=self.resources
        r=(bundle,policy,Encoder())
        state=new_session(TOPIC,r)
        for speaker,text in [('A','A uniform needs funding'),('B','Okay'),('A','Who pays?')]:
            state=analyze_turn(state,speaker,text,r)
        self.assertEqual(state['turns'][-1]['topic']['state'],'on_topic')
        self.assertTrue(state['turns'][-1]['topic']['used_context'])
        self.assertEqual(state['turns'][-1]['topic']['context_turn'],1)
        self.assertEqual(state['turns'][-1]['attack_context']['context_turns'],[1,2])
        self.assertFalse(state['monitor']['previous_relevant'])

    def test_context_cannot_keep_renewing_itself_after_anchor_expires(self):
        from test_bounded_topic import Encoder
        bundle,policy,_=self.resources
        r=(bundle,policy,Encoder())
        state=new_session(TOPIC,r)
        for text in ['A uniform needs funding','Okay','Who pays?','How much?','Who decides?','Who pays?']:
            state=analyze_turn(state,'A',text,r)
        self.assertFalse(state['turns'][-1]['topic']['used_context'])
        self.assertEqual(state['turns'][-1]['topic']['state'],'off_topic')

    def test_full_denial_requires_a_recent_accusation_and_cannot_hide_added_attack(self):
        self.add('A','You called me an idiot.')
        self.add('B','I did not call you an idiot.')
        self.assertFalse(self.state['turns'][-1]['personal_attack'])
        self.add('B','I did not call you an idiot. You are a moron.')
        self.assertFalse(self.state['turns'][-1]['attack_context']['suppressed'])

    def test_possible_answer_is_linked_without_claiming_the_evidence_is_verified(self):
        self.add('A','What evidence supports the uniform policy?')
        self.add('B','For example, a uniform policy helps families reduce clothing costs.')
        question=session_insights(self.state)['report']['questions'][0]
        self.assertEqual(question['answer_turns'],[2])
        self.assertTrue(self.state['turns'][-1]['argument']['link']['tentative'])

    def test_feedback_is_separate_from_review_status_and_survives_restart(self):
        self.add('B','You are an idiot.')
        alert=self.state['alerts'][0]
        updated=apply_feedback(self.state,alert['id'],'incorrect','Quoted by the speaker')
        self.assertEqual(updated['alerts'][0]['status'],'Pending')
        self.assertNotIn('feedback',self.state['alerts'][0])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'sessions.sqlite3'
            SessionStore(path).save(updated)
            restored=SessionStore(path).load(updated['id'])
            self.assertEqual(restored,updated)
            record=feedback_records(restored)[0]
            self.assertEqual(record['feedback']['verdict'],'incorrect')
            self.assertEqual(record['attack_probability'],.8)
            self.assertEqual(len(SessionStore(path).list()),1)
            revised=apply_feedback(restored,alert['id'],'correct','Checked the context')
            SessionStore(path).save(revised)
            self.assertEqual(len(feedback_records(SessionStore(path).load(updated['id']))),1)

    def test_invalid_feedback_and_unknown_alert_fail(self):
        self.add('B','You are an idiot.')
        for identifier,verdict in [('missing','correct'),('R1','maybe')]:
            with self.assertRaises(ValueError):
                apply_feedback(self.state,identifier,verdict,'')


if __name__=='__main__':
    unittest.main()
