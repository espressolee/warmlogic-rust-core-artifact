#!/usr/bin/env bash
set -euo pipefail

# scripts/ci/post_eval_report.sh
# Summarize latest evaluation reports, update meta/EVAL_INDEX.md, and post a PR comment when running in CI for PR events.

REPORT_DIR="meta/eval_reports"
INDEX_FILE="meta/EVAL_INDEX.md"
mkdir -p "$REPORT_DIR"

# Find latest reports
LATEST=$(ls -t "$REPORT_DIR"/EVALUATION_REPORT_*.md 2>/dev/null | head -n10 || true)
if [ -z "$LATEST" ]; then
  echo "No evaluation reports found in $REPORT_DIR"
  exit 0
fi

# Build summary
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
SUMMARY_FILE=$(mktemp)
echo "# Evaluation Summary - $TS" > "$SUMMARY_FILE"
for f in $LATEST; do
  echo "- Report: $f" >> "$SUMMARY_FILE"
  echo "
">> "$SUMMARY_FILE"
  head -n 60 "$f" | sed -n '1,200p' >> "$SUMMARY_FILE"
  echo "\n---\n" >> "$SUMMARY_FILE"
done

# Append to index
mkdir -p "$(dirname "$INDEX_FILE")"
if [ ! -f "$INDEX_FILE" ]; then
  echo "# Evaluation Index" > "$INDEX_FILE"
fi
{
  echo "\n## $TS"
  sed -n '1,80p' "$SUMMARY_FILE"
} >> "$INDEX_FILE"

# Attempt to post PR comment if running in GitHub Actions pull_request
if [ -n "${GITHUB_REF:-}" ] && echo "$GITHUB_REF" | grep -q "refs/pull/" && [ -n "${GITHUB_REPOSITORY:-}" ] && [ -n "${GITHUB_TOKEN:-}" ]; then
  PR_NUM=$(echo "$GITHUB_REF" | cut -d'/' -f3)
  OWNER_REPO="$GITHUB_REPOSITORY"
  COMMENTS_API="https://api.github.com/repos/$OWNER_REPO/issues/$PR_NUM/comments"
  BODY=$(sed 's/"/\\"/g' "$SUMMARY_FILE" | awk '{printf "%s\\n", $0}')
  PAYLOAD=$(printf '{"body": "%s"}' "$BODY")
  curl -s -H "Authorization: token $GITHUB_TOKEN" -X POST -d "$PAYLOAD" "$COMMENTS_API" || true
  echo "Posted summary comment to PR #$PR_NUM"
else
  echo "Not a pull_request event or missing GITHUB_TOKEN; skipping PR comment."
fi

# Print location of index file
echo "Index updated: $INDEX_FILE"

exit 0
