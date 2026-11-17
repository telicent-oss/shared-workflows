#!/usr/bin/env bash
# Example caller-owned preparation script; save as .github/scripts/security-sbom.sh.
set -euo pipefail
# Local install only. Use the repository's required profiles/arguments; do not deploy.
mvn --batch-mode clean install -DskipTests -Dgpg.skip
# Pin the generator. For per-module coverage, use makeBom and list every expected
# module SBOM in sbom-patterns rather than assuming an aggregate covers all modules.
mvn --batch-mode org.cyclonedx:cyclonedx-maven-plugin:2.9.1:makeAggregateBom \
  -DoutputName=bom -DoutputFormat=json -DincludeTestScope=false
