# shared-workflows

Shared workflows for Telicent OSS projects

## Maven Workflows

See the [Maven Workflow](docs/maven.md) documentation for usage.

## Standalone vulnerability scanning

See [standalone Trivy/Grype scanning](docs/standalone-vulnerability-scanning.md) for main-branch source/SBOM and immutable-image scans with Teams failure notifications.

## Dependabot auto-merge

[`dependabot-automerge.yml`](.github/workflows/dependabot-automerge.yml) labels Dependabot minor/patch PRs `automerge` and merges them through telicent-mergebot once every CI run on the head has passed. A failed vulnerability scan is tolerated if the PR adds no HIGH/CRITICAL findings beyond the default branch's latest scan. The caller owns the triggers:

```yaml
on:
  pull_request:
    branches: [main]
  workflow_run:
    workflows: ["Test feature branch", "Vulnerability Scanning"] # every CI workflow on Dependabot PRs
    types: [completed]

jobs:
  automerge:
    uses: telicent-oss/shared-workflows/.github/workflows/dependabot-automerge.yml@main
    permissions:
      actions: read
      contents: read
      pull-requests: write
    secrets:
      MERGEBOT_CLIENT_ID: ${{ secrets.MERGEBOT_CLIENT_ID }}
      MERGEBOT_PRIVATE_KEY: ${{ secrets.MERGEBOT_PRIVATE_KEY }}
```

The `MERGEBOT_*` secrets must be in both the Actions and Dependabot secret stores. Inputs `vulnerability-workflow`, `vulnerability-job-prefix` and `trivy-report-artifact` default to the names used in telicent-apps' `vulnerability-scanning.yml`.

## Standalone SonarQube analysis

See [standalone main-branch SonarQube analysis](docs/standalone-sonarqube.md) for scheduled/manual Maven and CLI scans with Teams failure notifications.
