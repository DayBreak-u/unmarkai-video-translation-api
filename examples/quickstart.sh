#!/usr/bin/env bash
# Run from repository root. Writes private temporary responses under output/curl/.
set -euo pipefail
: "${UNMARKAI_API_KEY:?Export UNMARKAI_API_KEY first}"
command -v jq >/dev/null
VIDEO=${1:?Usage: bash examples/quickstart.sh ./source.mp4}
API_BASE=${UNMARKAI_API_BASE:-https://api.unmarkai.net/v1}
API_BASE=${API_BASE%/}
mkdir -p output/curl
SIZE=$(wc -c < "$VIDEO" | tr -d ' ')
CONTENT_TYPE=${CONTENT_TYPE:-video/mp4}
jq -n --arg name "$(basename "$VIDEO")" --arg mime "$CONTENT_TYPE" --argjson size "$SIZE" \
  '{filename:$name,content_type:$mime,file_size_bytes:$size}' > output/curl/upload.json
curl --fail-with-body -sS "$API_BASE/uploads" \
  -H "Authorization: Bearer $UNMARKAI_API_KEY" -H 'Content-Type: application/json' \
  --data-binary @output/curl/upload.json -o output/curl/ticket.json
jq -r '.headers | to_entries[] | "\(.key): \(.value)"' output/curl/ticket.json > output/curl/headers.txt
curl --fail-with-body -sS -X PUT "$(jq -r .url output/curl/ticket.json)" \
  --header @output/curl/headers.txt --upload-file "$VIDEO"
UPLOAD_ID=$(jq -r .upload_id output/curl/ticket.json)
printf 'Upload ID: %s\n' "$UPLOAD_ID"
TARGET_LANGUAGE=${TARGET_LANGUAGE:-es}
jq -n --arg upload "$UPLOAD_ID" --arg target "$TARGET_LANGUAGE" \
  '{type:"video_translation",input:{upload_id:$upload},source_language:"auto",target_language:$target,advanced_quality:false,subtitle_enabled:true}' > output/curl/request.json
IDEMPOTENCY_KEY=${IDEMPOTENCY_KEY:-$(python3 -c 'import uuid; print(uuid.uuid4())')}
printf 'Idempotency-Key: %s\n' "$IDEMPOTENCY_KEY"
curl --fail-with-body -sS "$API_BASE/jobs" \
  -H "Authorization: Bearer $UNMARKAI_API_KEY" -H 'Content-Type: application/json' \
  -H "Idempotency-Key: $IDEMPOTENCY_KEY" --data-binary @output/curl/request.json -o output/curl/job.json
JOB_ID=$(jq -r .id output/curl/job.json)
printf 'Job ID: %s\n' "$JOB_ID"
# Check once; use the Python example's --job-id to poll and download.
curl --fail-with-body -sS "$API_BASE/jobs/$JOB_ID" -H "Authorization: Bearer $UNMARKAI_API_KEY" | jq .
