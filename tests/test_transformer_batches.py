"""Verify padding/batch and candidate metrics without loading pretrained weights."""

import unittest
import numpy as np

from transformer_batches import batch_arrays, binary_scores


class TransformerBatchContracts(unittest.TestCase):
    def test_padded_batches_are_cropped_to_bounded_length_buckets(self):
        ids = np.arange(4*128).reshape(4,128)
        mask = np.zeros((4,128),dtype=np.int64)
        mask[0,:7] = 1
        mask[1,:39] = 1
        labels = np.array([0,1,0,1])
        batch = batch_arrays(ids,mask,labels,[0,1])
        self.assertEqual(batch['input_ids'].shape,(2,64))
        np.testing.assert_array_equal(batch['labels'],[0,1])
        np.testing.assert_array_equal(batch['input_ids'][:,:39],ids[[0,1],:39])

    def test_short_final_batch_has_no_synthetic_examples(self):
        ids = np.ones((3,128),dtype=np.int32)
        mask = np.zeros_like(ids);mask[:,:4] = 1
        batch = batch_arrays(ids,mask,np.array([0,1,1]),[2])
        self.assertEqual(batch['input_ids'].shape,(1,32))
        self.assertEqual(batch['labels'].tolist(),[1])

    def test_confusion_counts_and_rates_match_reference(self):
        metrics = binary_scores([0,0,1,1],[.1,.8,.9,.2],threshold=.5)
        self.assertEqual([metrics[k] for k in ['tn','fp','fn','tp']],[1,1,1,1])
        self.assertEqual(metrics['attack_precision'],.5)
        self.assertEqual(metrics['attack_recall'],.5)
        self.assertEqual(metrics['accuracy'],.5)

    def test_length_grouping_visits_each_row_once_and_reduces_padding(self):
        import transformer_batches
        self.assertTrue(hasattr(transformer_batches,'length_bucket_order'), 'Length-aware batch ordering is missing')
        lengths = np.random.default_rng(6).integers(4,129,1025)
        order = transformer_batches.length_bucket_order(lengths,batch_size=4,seed=1842)
        self.assertEqual(sorted(order.tolist()),list(range(len(lengths))))
        np.testing.assert_array_equal(order,transformer_batches.length_bucket_order(lengths,4,1842))
        random_order = np.random.default_rng(1842).permutation(len(lengths))
        def padded_cost(indices):
            return sum(int(np.ceil(lengths[indices[i:i+4]].max()/32)*32)*len(indices[i:i+4]) for i in range(0,len(indices),4))
        self.assertLess(padded_cost(order),padded_cost(random_order)*.8)


if __name__=='__main__':
    unittest.main()
