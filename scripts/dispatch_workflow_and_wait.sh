#!/usr/bin/env bash
set -euo pipefail

workflow="${1:?workflow file/name is required}"
ref="${2:-main}"
target_sha="${3:-}"
poll_attempts="${DISPATCH_POLL_ATTEMPTS:-24}"
poll_seconds="${DISPATCH_POLL_SECONDS:-5}"

if [ -z "${target_sha}" ]; then
  git fetch origin "${ref}"
  target_sha="$(git rev-parse "origin/${ref}")"
fi

dispatch_started="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
echo "Dispatching ${workflow} on ${ref} for target SHA ${target_sha} at ${dispatch_started}."
gh workflow run "${workflow}" --ref "${ref}"

run_id=""
for attempt in $(seq 1 "${poll_attempts}"); do
  run_id="$(
    gh run list \
      --workflow "${workflow}" \
      --branch "${ref}" \
      --event workflow_dispatch \
      --limit 30 \
      --json databaseId,headSha,createdAt,status,conclusion \
      --jq ".[] | select(.headSha == \"${target_sha}\" and .createdAt >= \"${dispatch_started}\") | .databaseId" \
      | head -n 1
  )"

  if [ -n "${run_id}" ]; then
    echo "Found ${workflow} run ${run_id} for ${target_sha}; waiting for completion."
    gh run watch "${run_id}" --exit-status
    exit 0
  fi

  sleep "${poll_seconds}"
done

echo "::error::No ${workflow} workflow_dispatch run appeared for target SHA ${target_sha}."
exit 1
