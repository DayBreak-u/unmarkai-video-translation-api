"""Fetch, save or explicitly confirm one video translation review stage."""
import argparse
import json
from pathlib import Path
import requests
from client import ApiError, Client, resource_id


def fetch_review(client, job_id):
    path = f'/jobs/{resource_id(job_id)}/review'
    first = client.request('GET', path)
    segments = list(first['segments'])
    cursor = first['next_cursor']
    while cursor:
        page = client.request('GET', path, params={'cursor': cursor, 'limit': 100})
        if (page['review_id'], page['version']) != (first['review_id'], first['version']):
            raise ApiError('Review changed while paging; fetch again')
        segments.extend(page['segments'])
        cursor = page['next_cursor']
    return {**first, 'segments': segments, 'next_cursor': None}


def save_review(client, job_id, edited):
    current = fetch_review(client, job_id)
    if (current['review_id'], current['version']) != (edited['review_id'], edited['version']):
        raise ValueError('Stale review file. Fetch again before saving; do not overwrite newer edits.')
    original = {segment['id']: segment for segment in current['segments']}
    if len(edited['segments']) != len(original) or {s['id'] for s in edited['segments']} != set(original):
        raise ValueError('Cannot add or remove segments')
    changes = []
    for segment in edited['segments']:
        old = original[segment['id']]
        if (segment['start_ms'], segment['end_ms']) != (old['start_ms'], old['end_ms']):
            raise ValueError('Only text may be edited, not timing')
        if segment['text'] != old['text']:
            if not isinstance(segment['text'], str) or not 1 <= len(segment['text']) <= 10000:
                raise ValueError('Changed text must contain 1–10000 characters')
            changes.append({'id': segment['id'], 'text': segment['text']})
    version = current['version']
    while changes:
        batch = []
        while changes and len(batch) < 100:
            candidate = {'review_id': current['review_id'], 'base_version': version, 'segments': batch + [changes[0]]}
            if len(json.dumps(candidate).encode()) > 64000:
                if not batch:
                    raise ValueError('A segment exceeds the review request size limit')
                break
            batch.append(changes.pop(0))
        saved = client.request('PATCH', f'/jobs/{resource_id(job_id)}/review',
                               body={'review_id': current['review_id'], 'base_version': version, 'segments': batch})
        version = saved['version']
    return fetch_review(client, job_id)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job_id')
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--fetch', action='store_true')
    action.add_argument('--save', action='store_true')
    action.add_argument('--confirm', action='store_true', help='Explicitly approve the version in --file')
    parser.add_argument('--file', default='output/review.json')
    args = parser.parse_args()
    try:
        client = Client()
        path = Path(args.file)
        if args.fetch:
            result = fetch_review(client, args.job_id)
        elif args.save:
            result = save_review(client, args.job_id, json.loads(path.read_text()))
        else:
            review = json.loads(path.read_text())
            result = client.request('POST', f'/jobs/{resource_id(args.job_id)}/continue',
                                    body={'review_id': review['review_id'], 'base_version': review['version']})
            print(json.dumps(result))
            raise SystemExit(0)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print(f"Saved {result['stage']} review version {result['version']} to {path}")
    except (ApiError, ValueError, KeyError, OSError, requests.RequestException) as error:
        parser.exit(1, ('Network error; fetch current review before retrying' if isinstance(error, requests.RequestException) else str(error)) + '\n')
