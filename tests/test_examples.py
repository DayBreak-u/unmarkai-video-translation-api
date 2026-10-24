import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'examples'))
from client import ApiError, Client, download_results


def response(data=None, status=200):
    value = MagicMock()
    value.status_code = status
    value.headers = {}
    value.json.return_value = data
    return value


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.session = MagicMock()
        self.client = Client('uma_live_test_only', session=self.session)

    @patch('client.requests.put')
    def test_local_upload_preserves_signed_headers_and_never_sends_api_key(self, put):
        headers = {'content-type': 'video/mp4', 'content-length': '3', 'if-none-match': '*'}
        self.session.request.return_value = response({'upload_id': 'upl_test', 'url': 'https://storage.example/file', 'headers': headers})
        put.return_value = response(status=200)
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / 'video.mp4'
            file.write_bytes(b'abc')
            self.assertEqual(self.client.upload(file=file), 'upl_test')
        self.assertEqual(put.call_args.kwargs['headers'], headers)
        self.assertNotIn('Authorization', put.call_args.kwargs['headers'])
        self.assertEqual(put.call_args.kwargs['allow_redirects'], False)

    @patch('client.time.sleep')
    def test_url_import_waits_until_uploaded(self, sleep):
        self.session.request.side_effect = [response({'upload_id':'upl_import'}), response({'status':'importing'}), response({'status':'uploaded'})]
        self.assertEqual(self.client.upload(url='https://cdn.example/video.mp4'), 'upl_import')
        self.assertEqual(self.session.request.call_args_list[0].kwargs['json'], {'source_url':'https://cdn.example/video.mp4'})

    def test_failed_import_is_terminal(self):
        self.session.request.return_value = response({'status':'failed', 'error':{'code':'invalid_source'}})
        with self.assertRaisesRegex(ApiError, 'invalid_source'):
            self.client.wait_upload('upl_test')

    @patch('client.time.sleep')
    def test_job_creation_retry_preserves_key_and_body(self, sleep):
        self.session.request.side_effect = [response({}, 503), response({'id':'job_test'})]
        body = {'type':'remove_text', 'input':{'upload_id':'upl_test'}, 'mode':'all_area'}
        self.assertEqual(self.client.create_job(body, 'stable-key')['id'], 'job_test')
        calls = self.session.request.call_args_list
        self.assertEqual(calls[0].kwargs['json'], calls[1].kwargs['json'])
        self.assertEqual(calls[1].kwargs['headers']['Idempotency-Key'], 'stable-key')

    def test_unkeyed_post_is_not_retried(self):
        self.session.request.return_value = response({'error':{'code':'busy'}}, 503)
        with self.assertRaises(ApiError):
            self.client.request('POST', '/uploads', body={})
        self.assertEqual(self.session.request.call_count, 1)

    @patch('client.time.sleep')
    def test_polling_transitions_and_review_pause(self, sleep):
        self.session.request.side_effect = [response({'status':'queued'}), response({'status':'waiting_review'})]
        self.assertEqual(self.client.wait_job('job_test')['status'], 'waiting_review')

    def test_failed_and_canceled_jobs_stop(self):
        for status in ['failed', 'canceled']:
            self.session.request.return_value = response({'status':status, 'error':{'code':'test_error'}})
            with self.assertRaisesRegex(ApiError, status):
                self.client.wait_job('job_test')

    @patch('client.time.monotonic', side_effect=[0, 2])
    def test_poll_timeout_does_not_cancel(self, clock):
        with self.assertRaises(TimeoutError):
            self.client.wait_job('job_test', timeout=1)
        self.session.request.assert_not_called()

    @patch('client.requests.get')
    def test_result_download_does_not_send_api_auth(self, get):
        media = response(status=200)
        media.iter_content.return_value = [b'video']
        get.return_value.__enter__.return_value = media
        with tempfile.TemporaryDirectory() as tmp:
            download_results({'type':'remove_text','status':'succeeded','result':{'url':'https://cdn.example/out'}}, tmp)
            self.assertEqual((Path(tmp)/'cleaned.mp4').read_bytes(), b'video')
        self.assertNotIn('headers', get.call_args.kwargs)

    @patch('client.requests.get')
    def test_translation_downloads_video_and_both_subtitles(self, get):
        media = response(status=200)
        media.iter_content.side_effect = [[b'video'], [b'source'], [b'translated']]
        get.return_value.__enter__.return_value = media
        result = {k:{'url':'https://cdn.example/'+k} for k in ['video','source_subtitles','translated_subtitles']}
        with tempfile.TemporaryDirectory() as tmp:
            download_results({'type':'video_translation','status':'succeeded','result':result}, tmp)
            self.assertEqual((Path(tmp)/'translated.srt').read_bytes(), b'translated')
            self.assertEqual((Path(tmp)/'source.srt').read_bytes(), b'source')

    def test_api_error_exposes_code_and_request_id_only(self):
        self.session.request.return_value = response({'error':{'code':'invalid_input','message':'https://signed.example/private', 'request_id':'req_test'}}, 400)
        with self.assertRaisesRegex(ApiError, 'req_test') as error:
            self.client.request('GET', '/jobs/job_test')
        self.assertNotIn('signed.example', str(error.exception))


if __name__ == '__main__':
    unittest.main()
