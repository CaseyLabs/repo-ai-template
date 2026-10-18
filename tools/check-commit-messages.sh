#!/bin/sh
# Runs .githooks/commit-msg on each commit message in a revision range, so CI
# catches commits made with the hook disabled or bypassed (for example `git commit -an`).
# Usage: tools/check-commit-messages.sh <revision-range>   e.g. origin/main..HEAD
set -eu
[ $# -eq 1 ] || { echo "usage: $0 <revision-range>" >&2; exit 2; }
root=$(git rev-parse --show-toplevel)
commits=$(git rev-list "$1")
msg=$(mktemp)
trap 'rm -f "$msg"' EXIT
status=0
for commit in $commits; do
	# A stored message is already cleaned up, so a surviving `#` line (`--cleanup=verbatim`) is
	# content, not a comment or scissors line: indent it so the hook still scans it.
	git log -1 --format=%B "$commit" | sed 's/^#/ #/' > "$msg"
	if ! out=$(sh "$root/.githooks/commit-msg" "$msg" 2>&1); then
		echo "$(git log -1 --format='%h %s' "$commit")" >&2
		echo "$out" >&2
		status=1
	fi
done
[ $status -eq 0 ] && echo "commit messages: $(echo "$commits" | grep -c .) checked, no AI attribution"
exit $status
