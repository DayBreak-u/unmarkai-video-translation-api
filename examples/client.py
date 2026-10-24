"""Small synchronous example client for the public UnmarkAI API (Python 3.10+)."""
import json
import mimetypes
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlparse
import uuid

import requests

API_BASE = 'https://api.unmarkai.net/v1'


class ApiError(RuntimeError):
    pass


def resource_id(value):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value):
        raise ValueError('Invalid resource ID')
    return value


def https_url(value):
    parsed = urlparse(value)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError('Expected an HTTPS URL without embedded credentials')
    return value


class Client:
    def __init__(self, key=None, session=None):
        self.key = key or os.environ.get('UNMARKAI_API_KEY')
        if not self.key:
            raise ValueError('Export UNMARKAI_API_KEY first (see .env.example)')
        self.session = session or requests.Session()

    def request(self, method, path, *, body=None, idempotency_key=None, params=None):
        headers = {'Authorization': f'Bearer {self.key}'}
        if idempotency_key:
            headers['Idempotency-Key'] = idempotency_key
        # Never put Authorization in session defaults: signed media URLs use separate requests.
        for attempt in range(3):
            try:
                response = self.session.request(method, API_BASE + path, headers=headers,
                                                json=body, params=params, timeout=(10, 60),
                                                allow_redirects=False)
            except requests.RequestException:
                if attempt < 2 and (method == 'GET' or idempotency_key):
                    time.sleep(2 ** attempt)
                    continue
                raise ApiError('API network error; reuse the printed idempotency key and identical body for job retries') from None
            if response.status_code in (429, 502, 503, 504) and attempt < 2 and (method == 'GET' or idempotency_key):
                try:
                    delay = min(60, max(1, float(response.headers.get('Retry-After', 2 ** attempt))))
                except ValueError:
                    delay = 2 ** attempt
                time.sleep(delay)
                continue
            if not 200 <= response.status_code < 300:
                try:
                    error = response.json().get('error', {})
                except ValueError:
                    error = {}
                raise ApiError(f"HTTP {response.status_code}: {error.get('code', 'request_failed')}; "
                               f"request_id={error.get('request_id', response.headers.get('X-Request-Id', 'unknown'))}")
            return response.json()
        raise ApiError('Retry limit reached')

    def upload(self, *, file=None, url=None, upload_id=None, timeout=3600, interval=5):
        if upload_id:
            return resource_id(upload_id)
        if url:
            ticket = self.request('POST', '/url-uploads', body={'source_url': https_url(url)})
            return self.wait_upload(ticket['upload_id'], timeout, interval)
        path = Path(file)
        mime = {'.mov': 'video/quicktime', '.avi': 'video/x-msvideo', '.mkv': 'video/x-matroska',
                '.webm': 'video/webm', '.mp4': 'video/mp4', '.mpeg': 'video/mpeg', '.mpg': 'video/mpeg'}.get(path.suffix.lower())
        size = path.stat().st_size
        if not mime or not 0 < size <= 2147483648:
            raise ValueError('Use MP4, MOV, AVI, MKV, WebM or MPEG, between 1 byte and 2 GiB')
        ticket = self.request('POST', '/uploads', body={'filename': path.name, 'content_type': mime, 'file_size_bytes': size})
        https_url(ticket['url'])
        with path.open('rb') as source:
            # A signed PUT is one-shot. Do not silently retry a consumed ticket.
            response = requests.put(ticket['url'], data=source, headers=ticket['headers'],
                                    timeout=(10, 300), allow_redirects=False)
        if not 200 <= response.status_code < 300:
            raise ApiError(f"Signed upload failed: HTTP {response.status_code}; inspect the upload before retrying")
        print(f"Upload ID: {ticket['upload_id']}", file=sys.stderr)
        return ticket['upload_id']

    def wait_upload(self, upload_id, timeout=3600, interval=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            upload = self.request('GET', f'/uploads/{resource_id(upload_id)}')
            if upload['status'] == 'uploaded':
                print(f'Upload ID: {upload_id}', file=sys.stderr)
                return upload_id
            if upload['status'] in ('failed', 'expired'):
                raise ApiError(f"URL import {upload['status']}: {(upload.get('error') or {}).get('code', 'unknown')}")
            time.sleep(interval)
        raise TimeoutError(f'Import timed out; inspect upload {upload_id}. The server import was not canceled.')

    def create_job(self, body, key=None):
        key = key or str(uuid.uuid4())
        print(f'Idempotency-Key: {key}', file=sys.stderr)
        return self.request('POST', '/jobs', body=body, idempotency_key=key)

    def wait_job(self, job_id, timeout=3600, interval=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            job = self.request('GET', f'/jobs/{resource_id(job_id)}')
            print(f"{job_id}: {job['status']} ({job.get('progress', 0)}%)", file=sys.stderr)
            if job['status'] in ('succeeded', 'waiting_review'):
                return job
            if job['status'] in ('failed', 'canceled'):
                raise ApiError(f"Job {job['status']}: {(job.get('error') or {}).get('code', 'unknown')}")
            time.sleep(interval)
        raise TimeoutError(f'Job {job_id} still running; resume with --job-id. This timeout does not cancel the job.')


def download_results(job, output):
    directory = Path(output)
    directory.mkdir(parents=True, exist_ok=True)
    # This JSON contains temporary signed result URLs: keep it out of version control.
    (directory / 'job.json').write_text(json.dumps(job, indent=2) + '\n')
    if job['status'] == 'waiting_review':
        print('Human review required. See docs/review.md; resume this job after each confirmation.', file=sys.stderr)
        return
    result = job.get('result') or {}
    if job['type'] == 'remove_text':
        assets = {'cleaned.mp4': result}
    else:
        assets = {name: result.get(key) for name, key in [
            ('translated.mp4', 'video'), ('source.srt', 'source_subtitles'),
            ('translated.srt', 'translated_subtitles'), ('original-asr.srt', 'asr_original_subtitles'),
            ('audio.mp3', 'audio')]}
    for name, asset in assets.items():
        if not asset or not asset.get('url'):
            continue
        destination = directory / name
        temp = destination.with_suffix(destination.suffix + '.part')
        try:
            # No API Authorization header is ever sent to the media origin.
            with requests.get(https_url(asset['url']), stream=True, timeout=(10, 120)) as response:
                if not 200 <= response.status_code < 300:
                    raise ApiError(f'Download failed: HTTP {response.status_code}; re-fetch job status for a fresh URL')
                with temp.open('wb') as target:
                    for chunk in response.iter_content(1024 * 1024):
                        target.write(chunk)
            temp.replace(destination)
        except Exception:
            temp.unlink(missing_ok=True)
            raise
        print(f'Saved {destination}', file=sys.stderr)


def add_arguments(parser):
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--file', help='Local authorized source video')
    inputs.add_argument('--url', help='Direct HTTPS video URL, not a platform watch page')
    inputs.add_argument('--upload-id', help='Reuse an already uploaded source')
    inputs.add_argument('--job-id', help='Resume an existing job without creating another')
    parser.add_argument('--output', default='output')
    parser.add_argument('--idempotency-key', help='Reuse the SAME key, upload ID and options when retrying creation')
    parser.add_argument('--timeout', type=int, default=3600, help='Maximum polling seconds per phase')
    parser.add_argument('--interval', type=int, default=5, help='Polling interval in seconds')


def run(parser, make_body):
    args = parser.parse_args()
    try:
        if args.timeout <= 0 or args.interval <= 0:
            raise ValueError('--timeout and --interval must be positive')
        # Validate job options before starting any upload.
        body = make_body(args) if not args.job_id else None
        client = Client()
        if args.job_id:
            job_id = resource_id(args.job_id)
        else:
            upload_id = client.upload(file=args.file, url=args.url, upload_id=args.upload_id,
                                      timeout=args.timeout, interval=args.interval)
            body['input'] = {'upload_id': upload_id}
            job = client.create_job(body, args.idempotency_key)
            job_id = job['id']
            print(f'Job ID: {job_id}', file=sys.stderr)
        download_results(client.wait_job(job_id, args.timeout, args.interval), args.output)
    except (ApiError, ValueError, OSError, requests.RequestException, TimeoutError) as error:
        # requests exceptions may include signed URLs; suppress those details.
        message = 'Media transfer failed; inspect the upload/job before retrying' if isinstance(error, requests.RequestException) else str(error)
        parser.exit(1, f'{message}\n')
