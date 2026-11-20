"""Behavioral repair contracts; semantic quality is evaluated separately with real embeddings."""
import unittest
from conversation_insights import argument_for, session_insights
from test_moderation_contract import resources


class RepairContracts(unittest.TestCase):
    def turn(self, text, role=None, speaker='A', number=1, topic='on_topic'):
        turn={'number':number,'text':text,'speaker':speaker,'topic':{'state':topic},'personal_attack':False}
        turn['argument']={'role':role,'link':None,'evidence_requested':False} if role else argument_for(turn,[],resources()[2])
        return turn

    def test_question_inside_a_reported_quote_does_not_become_an_open_question(self):
        t=self.turn('The poster asks "Why recycle?" and recommends separate paper bins.')
        self.assertNotEqual(t['argument']['role'],'question')

    def test_indirect_question_and_imperative_request_are_questions(self):
        for text in ('I wonder how the school would pay for uniforms.','Please explain how the uniform subsidy would be funded.','Please show a source for the uniform cost estimate.'):
            self.assertEqual(self.turn(text)['argument']['role'],'question',text)

    def test_negative_agreement_is_a_rebuttal(self):
        self.assertEqual(self.turn('I do not agree that uniform subsidies help families.')['argument']['role'],'rebuttal')

    def test_off_topic_reason_cue_is_not_an_argument(self):
        self.assertEqual(self.turn('Because my guitar strings snapped, I bought a new guitar.',topic='off_topic')['argument']['role'],'unclassified')

    def test_report_uses_explicit_answer_links_instead_of_argument_links(self):
        q=self.turn('What is the uniform cost?','question')
        answer=self.turn('A uniform would cost forty pounds.','claim',speaker='B',number=9)
        answer['argument']['answers']=[{'turn':1,'status':'possible_answer','confidence':.8}]
        state={'turns':[q,answer],'alerts':[]}
        report=session_insights(state)['report']['questions'][0]
        self.assertEqual(report['answer_turns'],[9])

    def test_refusal_does_not_count_as_supplied_answer(self):
        q=self.turn('What evidence supports the uniform policy?','question')
        answer=self.turn('I refuse to answer the question.','unclassified',speaker='B',number=2)
        answer['argument']['answers']=[{'turn':1,'status':'declined','confidence':.9}]
        report=session_insights({'turns':[q,answer],'alerts':[]})['report']['questions'][0]
        self.assertEqual(report['answer_turns'],[])
        self.assertEqual(report['responses'][0]['status'],'declined')
        self.assertEqual(report['status'],'needs_followup')

    def test_delayed_response_is_tracked_beyond_six_turns(self):
        from question_tracker import find_responses, question_info
        q=self.turn('What is the annual uniform cost?','question')
        q['argument']['question']=question_info(q['text'],'Should schools require uniforms?')
        previous=[q]+[self.turn('The policy needs a public vote.','claim',number=n) for n in range(2,9)]
        answer=self.turn('The annual uniform cost is forty pounds.','claim',number=9,speaker='B')
        responses=find_responses(answer,previous,resources()[2])
        self.assertEqual(responses[0]['turn'],1)

    def test_partial_and_missing_evidence_responses_remain_open_for_followup(self):
        q=self.turn('What evidence supports the policy?','question')
        a=self.turn('I do not have the evidence.','claim',number=2)
        a['argument']['answers']=[{'turn':1,'status':'insufficient_evidence','confidence':.9}]
        question=session_insights({'turns':[q,a]})['report']['questions'][0]
        self.assertEqual(question['status'],'needs_followup')

    def test_quantity_question_with_modifiers_requires_a_quantity(self):
        from question_tracker import question_info,response_status
        self.assertEqual(question_info('What is the annual library membership cost?')['kind'],'quantity')
        self.assertEqual(response_status('The library membership scheme needs a public calendar.','quantity'),'partial_answer')

    def test_verb_form_asks_for_a_quantity_and_relative_clause_does_not_change_question_type(self):
        from question_tracker import question_info
        self.assertEqual(question_info('What would the maintenance contract cost?')['kind'], 'quantity')
        self.assertEqual(question_info('How can residents who work late join?')['kind'], 'explanation')

    def test_adjacent_topical_statement_without_quantity_does_not_preempt_an_answer(self):
        from question_tracker import find_responses
        q=self.turn('How many uniforms should each student receive?','question')
        aside=self.turn('Uniforms should be distributed before school opens.','claim',number=2)
        self.assertEqual(find_responses(aside,[q],resources()[2]),[])

    def test_short_spoken_number_can_answer_the_immediately_preceding_quantity_question(self):
        from question_tracker import find_responses
        q=self.turn('How many uniforms should each student receive?','question')
        answer=self.turn('Two per student.','claim',speaker='B',number=2)
        responses=find_responses(answer,[q],resources()[2])
        self.assertEqual([(r['turn'],r['status']) for r in responses],[(1,'possible_answer')])

    def test_deictic_evidence_followup_can_reference_a_recent_topical_argument(self):
        prev=self.turn('Uniforms reduce annual clothing costs.','claim')
        q=self.turn('Where is the evidence for that conclusion?',number=2,speaker='B',topic='off_topic')
        result=argument_for(q,[prev],resources()[2])
        self.assertEqual(result['role'],'question')
        self.assertTrue(result['evidence_requested'])

    def test_feature_request_does_not_answer_which_software_will_be_used(self):
        q=self.turn('What platform would the uniform ordering service use?','question')
        statement=self.turn('Uniform orders should support a printable receipt.','claim',number=2)
        from question_tracker import find_responses
        self.assertEqual(find_responses(statement,[q],resources()[2]),[])

    def test_off_topic_agreement_with_a_specific_recent_claim_stays_an_agreement(self):
        prev=self.turn('Uniforms are expensive for families.','claim')
        reply=self.turn('I agree that uniforms are expensive for families.',number=2,speaker='B',topic='off_topic')
        result=argument_for(reply,[prev],resources()[2])
        self.assertEqual(result['role'],'agreement')
        self.assertEqual(result['link']['turn'],1)

    def test_delayed_topically_similar_statement_without_requested_quantity_is_not_an_answer(self):
        from question_tracker import find_responses,question_info
        q=self.turn('How many library memberships can the scheme offer?','question')
        q['argument']['question']=question_info(q['text'])
        previous=[q,self.turn('The council needs to discuss the scheme.','claim',number=2)]
        later=self.turn('We should publish the library membership scheme calendar.','claim',number=3)
        self.assertEqual(find_responses(later,previous,resources()[2]),[])

    def test_refusal_is_a_response_but_not_an_argumentative_reason(self):
        q=self.turn('What source supports the new library scheme?','question')
        later=self.turn('I will not answer that question about the library scheme.',number=2,speaker='B')
        # Force a misleading role suggestion: explicit response acts take priority over it.
        from unittest.mock import patch
        with patch('argument_models.available',return_value={'dimension':2}), patch('argument_models.load_models',return_value={}), patch('argument_models.role_scores',return_value={'reason':.99,'claim':.005,'rebuttal':.005}):
            argument=argument_for(later,[q],resources()[2])
        self.assertEqual(argument['role'],'unclassified')
        self.assertEqual(argument['answers'][0]['status'],'declined')

    def test_direct_answer_remains_a_claim_when_role_model_suggests_reason(self):
        q=self.turn('Who would supervise the library volunteers?','question')
        later=self.turn('Qualified library staff would supervise the volunteers.',number=2,speaker='B')
        from unittest.mock import patch
        with patch('argument_models.available',return_value={'dimension':2}), patch('argument_models.load_models',return_value={}), patch('argument_models.role_scores',return_value={'reason':.99,'claim':.005,'rebuttal':.005}):
            argument=argument_for(later,[q],resources()[2])
        self.assertEqual(argument['role'],'claim')
        self.assertEqual(argument['link']['relation'],'answers')

    def test_manual_correction_preserves_original_and_rejects_future_targets(self):
        from conversation_insights import correct_argument
        first=self.turn('Uniforms increase clothing costs.','claim')
        second=self.turn('A school survey estimated higher costs.','claim',number=2,speaker='B')
        state={'turns':[first,second],'alerts':[]}
        fixed=correct_argument(state,2,'reason',1,'support','A supporting estimate')
        self.assertEqual(fixed['turns'][1]['argument_original'],second['argument'])
        self.assertEqual(fixed['turns'][1]['argument']['link']['relation'],'support')
        self.assertFalse(fixed['turns'][1]['argument']['link']['tentative'])
        self.assertEqual(second['argument']['role'],'claim')
        again=correct_argument(fixed,2,'rebuttal',1,'attack','')
        self.assertEqual(again['turns'][1]['argument_original'],second['argument'])
        with self.assertRaises(ValueError): correct_argument(state,1,'rebuttal',2,'attack','')

    def test_correcting_a_question_removes_stale_answer_associations(self):
        from conversation_insights import correct_argument
        q=self.turn('What is the cost?','question')
        a=self.turn('A uniform would cost forty pounds.','claim',number=2)
        a['argument']['answers']=[{'turn':1,'status':'possible_answer'}]
        a['argument']['link']={'turn':1,'relation':'answers','tentative':True}
        fixed=correct_argument({'turns':[q,a]},1,'claim',None,None,'Rhetorical question')
        self.assertEqual(fixed['turns'][1]['argument']['answers'],[])
        self.assertIsNone(fixed['turns'][1]['argument']['link'])

    def test_same_speaker_self_rebuttal_survives_speaker_correction(self):
        from moderation_session import correct_voice_speaker
        first=self.turn('Uniforms increase clothing costs.','claim')
        second=self.turn('I disagree with my earlier estimate.','rebuttal',number=2,speaker='B')
        first['source']='voice';second['source']='voice'
        second['argument'].update(method='learned-roles-relations-v2',link={'turn':1,'relation':'attack'})
        fixed=correct_voice_speaker({'turns':[first,second],'alerts':[]},2,'A')
        self.assertEqual(fixed['turns'][1]['argument']['link']['turn'],1)


if __name__=='__main__': unittest.main()
