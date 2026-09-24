#!/usr/bin/env bash
set -euo pipefail

# Usage: run-helm-tests.sh <chart-path> <test-mode> <action-path>
# test-mode: local-only | shared-only | union

CHART="$1"
TEST_MODE="$2"
ACTION_PATH="$3"

SHARED_TESTS_DEST="${CHART}/tests/.shared"

copy_shared_tests() {
  mkdir -p "$SHARED_TESTS_DEST"
  cp "${ACTION_PATH}"/shared-tests/*_test.yaml "$SHARED_TESTS_DEST"/
}

case "$TEST_MODE" in
  local-only)
    TEST_ARGS=(-f "tests/*_test.yaml")
    ;;
  shared-only)
    copy_shared_tests
    TEST_ARGS=(-f "tests/.shared/*_test.yaml")
    ;;
  union)
    copy_shared_tests
    TEST_ARGS=(-f "tests/*_test.yaml" -f "tests/.shared/*_test.yaml")
    ;;
  *)
    echo "[ERROR] Unknown test-mode: ${TEST_MODE} (expected local-only, shared-only, or union)"
    exit 1
    ;;
esac

helm unittest "${TEST_ARGS[@]}" "$CHART"