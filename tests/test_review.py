from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'examples'))
from review import fetch_review, save_review
from client import ApiError


def snapshot(version=1):
    return {'review_id':'rev_test','stage':'source','version':version,'next_cursor':None,
            'segments':[{'id':'seg_a','start_ms':0,'end_ms':1000,'text':'Hello'}]}


class ReviewTests(unittest.TestCase):
    def test_follows_review_pagination(self):
        client = MagicMock()
        first = snapshot()
        first['next_cursor'] = 'next'
        second = snapshot()
        second['segments'][0]['id'] = 'seg_b'
        client.request.side_effect = [first, second]
        self.assertEqual(len(fetch_review(client, 'job_test')['segments']), 2)
        self.assertEqual(client.request.call_args.kwargs['params']['cursor'], 'next')

    def test_changed_pagination_version_stops(self):
        client = MagicMock()
        first = snapshot()
        first['next_cursor'] = 'next'
        client.request.side_effect = [first, snapshot(2)]
        with self.assertRaises(ApiError):
            fetch_review(client, 'job_test')

    def test_stale_review_is_not_overwritten(self):
        client = MagicMock()
        client.request.return_value = snapshot(2)
        with self.assertRaisesRegex(ValueError, 'Stale'):
            save_review(client, 'job_test', snapshot(1))
        self.assertEqual(client.request.call_count, 1)

    def test_only_changed_text_is_saved_with_current_version(self):
        client = MagicMock()
        edited = snapshot()
        edited['segments'][0]['text'] = 'Corrected'
        client.request.side_effect = [snapshot(), {'review_id':'rev_test','version':2}, snapshot(2)]
        self.assertEqual(save_review(client, 'job_test', edited)['version'], 2)
        self.assertEqual(client.request.call_args_list[1].kwargs['body'],
                         {'review_id':'rev_test','base_version':1,'segments':[{'id':'seg_a','text':'Corrected'}]})
        self.assertFalse(any('/continue' in call.args[1] for call in client.request.call_args_list))

    def test_timing_edits_are_rejected(self):
        client = MagicMock()
        client.request.return_value = snapshot()
        edited = snapshot()
        edited['segments'][0]['end_ms'] = 5000
        with self.assertRaisesRegex(ValueError, 'timing'):
            save_review(client, 'job_test', edited)

    def test_large_unicode_edits_split_by_actual_json_bytes(self):
        client = MagicMock()
        original = snapshot()
        original['segments'] = [dict(original['segments'][0], id=f'seg_{i}') for i in range(3)]
        edited = deepcopy(original)
        for segment in edited['segments']:
            segment['text'] = '字' * 10000
        client.request.side_effect = [original, {'version':2}, {'version':3}, {'version':4}, dict(edited,version=4)]
        self.assertEqual(save_review(client, 'job_test', edited)['version'], 4)
        self.assertEqual(len([c for c in client.request.call_args_list if c.args[0]=='PATCH']), 3)
