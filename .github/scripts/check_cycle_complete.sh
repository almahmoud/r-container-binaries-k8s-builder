#!/bin/bash
# check_cycle_complete.sh - Check if build cycle is ready to finalize
# Returns 0 if ready and creates notification message, 1 otherwise

set -euo pipefail

# Check if notification was already sent
if [[ -f "cycle_ready_notified" ]]; then
  echo "Notification already sent, skipping"
  exit 1
fi

# Load package data
if [[ ! -f "biocdeps.json" ]] || [[ ! -f "remaining-packages.json" ]]; then
  echo "Required files not found, skipping check"
  exit 1
fi

# Count packages in different states
TOTAL_PKGS=$(python3 -c "import json; print(len(json.load(open('biocdeps.json'))))")
REMAINING_PKGS=$(python3 -c "import json; data=json.load(open('remaining-packages.json')); print(len(data))")
SUCCESSFUL=$(wc -l < logs/successful-packages.txt 2>/dev/null || echo 0)
FAILED=$(wc -l < logs/failed-packages.txt 2>/dev/null || echo 0)
DISPATCHED=$(wc -l < logs/dispatched-packages.txt 2>/dev/null || echo 0)
IN_PROGRESS=$((DISPATCHED - SUCCESSFUL - FAILED))
READY=$(wc -l < ready_packages.txt 2>/dev/null || echo 0)

echo "Total packages: ${TOTAL_PKGS}"
echo "Successful: ${SUCCESSFUL}"
echo "Failed: ${FAILED}"
echo "In progress: ${IN_PROGRESS}"
echo "Ready to dispatch: ${READY}"
echo "Remaining (blocked): ${REMAINING_PKGS}"

# Check if cycle is stuck: no in-progress, no ready, but has remaining packages
if [[ "${IN_PROGRESS}" -eq 0 ]] && [[ "${READY}" -eq 0 ]] && [[ "${REMAINING_PKGS}" -gt 0 ]]; then
  echo "Cycle appears stuck - all remaining packages are blocked by failures"
  
  # Verify remaining packages depend on failed packages
  python3 << 'PYEOF'
import json
import sys

with open('biocdeps.json') as f:
    all_deps = json.load(f)

with open('remaining-packages.json') as f:
    remaining = json.load(f)

with open('logs/failed-packages.txt') as f:
    failed = set(line.strip() for line in f if line.strip())

blocked_by_failures = []
for pkg in remaining:
    if pkg in all_deps:
        deps = all_deps[pkg]
        # Check if any dependency is in failed packages
        failed_deps = [d for d in deps if d in failed]
        if failed_deps:
            blocked_by_failures.append(f"{pkg} (blocked by: {', '.join(failed_deps[:3])})")

if len(blocked_by_failures) == len(remaining):
    print(f"✅ Confirmed: All {len(remaining)} remaining packages are blocked by failed dependencies")
    print(f"\nSuccessful builds: {len(open('logs/successful-packages.txt').readlines())}")
    print(f"Failed builds: {len(failed)}")
    print(f"Blocked packages: {len(remaining)}")
    print(f"\nExamples of blocked packages:")
    for example in blocked_by_failures[:5]:
        print(f"  - {example}")
    sys.exit(0)
else:
    print("Some packages may not be blocked by failures")
    sys.exit(1)
PYEOF
  
  if [[ $? -eq 0 ]]; then
    # Mark as notified
    touch cycle_ready_notified
    git add cycle_ready_notified
    git commit -m "Mark cycle as ready for finalization" || true
    git push || true
    exit 0
  else
    exit 1
  fi
else
  echo "Cycle still in progress"
  exit 1
fi
