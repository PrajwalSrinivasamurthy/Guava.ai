#!/usr/bin/env bash
# Runs the full test suite (offline + live) for every Texas Tech inbound implementation.
#
# Live tests (tests/test_scripted.py) need a real GUAVA_API_KEY in each project's .env —
# without one they skip cleanly rather than failing. See each project's README.
#
# Usage:
#   ./run_all_tests.sh              # offline + live, all 4 projects
#   ./run_all_tests.sh --offline    # skip the live tier (no RUN_LIVE, no --env-file)
#   ./run_all_tests.sh inbound-k12  # only the named project(s)
#
# Full output (everything below) is also written to test-results.log
# (overwritten each run) so a run can be reviewed without re-pasting terminal
# scrollback.

set -u
cd "$(dirname "$0")"

LOG_FILE="test-results.log"

run() {
    LIVE=1
    PROJECTS=()
    for arg in "$@"; do
        case "$arg" in
            --offline) LIVE=0 ;;
            *) PROJECTS+=("$arg") ;;
        esac
    done
    [ ${#PROJECTS[@]} -eq 0 ] && PROJECTS=(inbound-10k inbound-cla inbound-grad inbound-k12 inbound-online)

    RESULT_NAMES=()
    RESULT_VALUES=()
    FAILED=0

    for project in "${PROJECTS[@]}"; do
        echo "=================================================================="
        echo "== $project"
        echo "=================================================================="

        if [ ! -d "$project" ]; then
            echo "skip: no such project directory"
            RESULT_NAMES+=("$project")
            RESULT_VALUES+=("MISSING")
            FAILED=1
            continue
        fi

        (
            cd "$project" || exit 1
            if [ "$LIVE" -eq 1 ]; then
                if [ ! -f .env ]; then
                    echo "warning: no .env — live tests will skip, not fail"
                fi
                RUN_LIVE=1 uv run --env-file .env pytest tests/ -v
            else
                uv run pytest tests/ -v
            fi
        )
        status=$?

        RESULT_NAMES+=("$project")
        if [ $status -eq 0 ]; then
            RESULT_VALUES+=("PASS")
        else
            RESULT_VALUES+=("FAIL")
            FAILED=1
        fi
        echo
    done

    echo "=================================================================="
    echo "== Summary"
    echo "=================================================================="
    for i in "${!RESULT_NAMES[@]}"; do
        printf "  %-16s %s\n" "${RESULT_NAMES[$i]}" "${RESULT_VALUES[$i]}"
    done

    exit $FAILED
}

run "$@" | tee "$LOG_FILE"
status=${PIPESTATUS[0]}
echo
echo "Full output: $LOG_FILE"
exit "$status"
