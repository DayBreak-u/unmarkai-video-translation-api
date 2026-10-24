# Source and translation review

Start a translation job with `--manual-review`. When it reaches `waiting_review`, it needs explicit approval. The source and translation stages each have a 72-hour deadline; saving does not extend it.

```bash
python examples/translate_video.py --file source.mp4 --target es --manual-review
# Replace job_REPLACE with the printed job ID.
python examples/review.py job_REPLACE --fetch --file output/review.json
# Edit ONLY segment text in output/review.json using your editor.
python examples/review.py job_REPLACE --save --file output/review.json
# Inspect the refreshed file, then explicitly approve its current version:
python examples/review.py job_REPLACE --confirm --file output/review.json
python examples/translate_video.py --job-id job_REPLACE
```

Repeat fetch/edit/save/confirm when the next stage reaches `waiting_review`. If no text needs changing, omit `--save`; confirmation approves the version you fetched. After the second approval, resume polling until the result is ready.

The fetch command follows all review pages. Save checks the server review ID and version, preserves IDs and timings, and sends only changed text in batches of at most 100 segments / under 64 KiB. Each successful batch updates the base version. A 409 or partial failure requires fetching the current review and merging your remaining edits; no automatic overwrite is attempted. Keep your edited file as a private backup before saving a large review.

The endpoint is `GET/PATCH /v1/jobs/{job_id}/review`; confirmation is `POST /v1/jobs/{job_id}/continue` with `review_id` and `base_version`. The example never automatically approves content, even if it is unchanged. On expiry, inspect the job error and billing state before creating another task.
