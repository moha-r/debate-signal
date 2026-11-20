import unittest
import numpy as np

from contextual_topic import BoundedTopicMonitor


class Encoder:
    def encode(self,text,normalize_embeddings=True):
        if text == 'Schools should require uniforms':
            return np.array([1.,0.,0.])
        if 'uniform' in text.lower():
            return np.array([.8,.6,0.])
        if text.lower().startswith(('who','how','the supplier')):
            return np.array([0.,.9,np.sqrt(.19)])
        return np.array([0.,0.,1.])


class BoundedContextContracts(unittest.TestCase):
    def monitor(self,window=4):
        return BoundedTopicMonitor('Schools should require uniforms',.5,context_window=window,link_threshold=.3,encoder=Encoder())

    def test_acknowledgement_keeps_a_recent_topical_anchor(self):
        monitor=self.monitor()
        monitor.process('A uniform supplier needs a budget')
        monitor.process('Okay')
        result=monitor.process('Who pays?')
        self.assertTrue(result['used_context'])
        self.assertEqual(result['state'],'on_topic')

    def test_unrelated_statement_cannot_inherit_the_anchor(self):
        monitor=self.monitor()
        monitor.process('A uniform supplier needs a budget')
        result=monitor.process('My pet sleeps on a pink cushion')
        self.assertFalse(result['used_context'])
        self.assertEqual(result['state'],'off_topic')

    def test_anchor_expires_after_bounded_history(self):
        monitor=self.monitor(window=2)
        monitor.process('Uniform suppliers need funding')
        monitor.process('Okay')
        monitor.process('Understood')
        result=monitor.process('Who pays?')
        self.assertFalse(result['used_context'])

    def test_inherited_context_does_not_create_a_new_direct_anchor(self):
        monitor=self.monitor(window=2)
        monitor.process('Uniform suppliers need funding')
        self.assertEqual(monitor.process('Who pays?')['state'],'on_topic')
        self.assertEqual(monitor.process('How much?')['state'],'on_topic')
        self.assertEqual(monitor.process('Who decides?')['state'],'off_topic')

    def test_confirmed_drift_suspends_context_until_direct_return(self):
        monitor=self.monitor()
        monitor.process('Uniform suppliers need funding')
        monitor.process('My pet sleeps')
        self.assertTrue(monitor.process('It likes a pink cushion')['alert'])
        self.assertFalse(monitor.process('Who pays?')['used_context'])
        self.assertEqual(monitor.process('Uniform costs need support')['state'],'on_topic')
        self.assertEqual(monitor.process('Who pays?')['state'],'on_topic')


if __name__=='__main__':
    unittest.main()
