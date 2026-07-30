# Static Application Security Testing Action

This GitHub action runs a SonarQube analysis over a repo and, by default,
enforces the project's quality gate as a hard failure.

As of ODY go live to prod, passing this action is a requirement for release.

## Description

When invoked, the action will carry out the following steps.

* Validate that a SonarQube host URL and token have been supplied, failing
  early with a clear message rather than leaving the scanner to fail opaquely.
* Run the [SonarQube scanner][1] over `project-base-dir`, passing through
  `sonar-project-key`, `sonar-organization` and any additional `args`.
* Wait for the analysis to be processed and fail the job when the quality gate
  is not passing, unless `sonar-fail-on-quality-gate` is `false`.

Both upstream actions are pinned by commit SHA.

## Requirements

### Checkout Depth

The calling workflow **must** check the repo out with `fetch-depth: 0`.

```yaml
      - uses: actions/checkout@v5
        with:
          fetch-depth: 0
```

SonarQube uses git history to attribute issues to authors and to work out
which code is new. A shallow clone, which is the `actions/checkout` default,
leaves it unable to do either, so new code metrics and the quality gate
conditions that depend on them will be wrong.

### SonarQube Token

The `sonar-token` needs permission to submit an analysis for the project, so
either a *Global Analysis Token* (`sqa_` prefix), a *Project Analysis Token*
(`sqp_` prefix) or a *User Token* (`squ_` prefix) with *Execute Analysis* will
do. Supply it from a secret rather than inline.

Note that this differs from the [sonar-report-generation][2] action, which
reads the Web API and therefore requires a *User Token* specifically.

### Project Configuration

The scanner needs to know which project it is analysing. Supply it either
through the `sonar-project-key` and `sonar-organization` inputs, or by
committing a `sonar-project.properties` to the repo.

`sonar-organization` is required by SonarQube Cloud, the default host. It is
not needed for a self-hosted SonarQube Server.

## Inputs

| Name | Default | Required | Description |
| :--- | :--- | :--- | :--- |
| `sonar-host-url` | `https://sonarcloud.io` | No | Base URL of the SonarQube server used for the scan. |
| `sonar-token` | | Yes | A SonarQube token with permission to analyse the project. |
| `sonar-project-key` | | No | The key of the project to analyse. Only required when the repo has no `sonar-project.properties` declaring `sonar.projectKey`. |
| `sonar-organization` | | No | The organization the project belongs to. Required by SonarQube Cloud unless declared in `sonar-project.properties`. |
| `sonar-fail-on-quality-gate` | `'true'` | No | Whether to perform just the scan or to enforce it with a hard failure gate. |
| `sonar-polling-timeout-seconds` | `'300'` | No | Maximum time to wait for the quality gate result. |
| `project-base-dir` | `.` | No | Base directory of the code to scan. Usually `.`, except in a monorepo where it could be `apps/<application-name>`. |
| `args` | | No | Additional arguments for the Sonar Scanner CLI, for example `-Dsonar.sources=src`. |

## Outputs

| Output | Description |
| :--- | :--- |
| `quality-gate-status` | The quality gate result, one of `PASSED`, `WARN` or `FAILED`. Only populated when `sonar-fail-on-quality-gate` is `true`. |

## Usage

### Basic Usage

```yaml
name: SAST
on:
  pull_request:
  push:
    branches: [main]

jobs:
  sast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
        with:
          fetch-depth: 0

      - name: Run SAST scanning
        uses: telicent-oss/shared-workflows/.github/actions/sast-scanning@main
        with:
          sonar-token: ${{ secrets.SONAR_TOKEN }}
          sonar-project-key: telicent-access-platform
          sonar-organization: telicent-oss
```

### Scanning One Application in a Monorepo

```yaml
      - name: Run SAST scanning
        uses: telicent-oss/shared-workflows/.github/actions/sast-scanning@main
        with:
          sonar-token: ${{ secrets.SONAR_TOKEN }}
          sonar-project-key: telicent-access-platform-api
          sonar-organization: telicent-oss
          project-base-dir: apps/api
```

### Scanning Without Enforcing the Gate

Useful while a project is being brought up to the standard, so the analysis is
still published but a failing gate does not block the build.

```yaml
      - name: Run SAST scanning
        uses: telicent-oss/shared-workflows/.github/actions/sast-scanning@main
        with:
          sonar-token: ${{ secrets.SONAR_TOKEN }}
          sonar-project-key: telicent-access-platform
          sonar-organization: telicent-oss
          sonar-fail-on-quality-gate: 'false'
```

### Self-Hosted SonarQube With Extra Scanner Properties

```yaml
      - name: Run SAST scanning
        id: sast
        uses: telicent-oss/shared-workflows/.github/actions/sast-scanning@main
        with:
          sonar-host-url: https://sonar.example.com
          sonar-token: ${{ secrets.SONAR_TOKEN }}
          sonar-project-key: telicent-access-platform
          sonar-polling-timeout-seconds: '600'
          args: >-
            -Dsonar.sources=src
            -Dsonar.tests=test
            -Dsonar.javascript.lcov.reportPaths=coverage/lcov.info
```

### Using the Output

```yaml
      - name: Report the outcome
        if: always()
        run: echo "Quality gate: ${{ steps.sast.outputs.quality-gate-status }}"
```

## Related Actions

| Action | Description |
| :--- | :--- |
| [`sonar-report-generation`](../sonar-report-generation) | Renders a PDF code health report from an existing SonarQube analysis and uploads it to S3. |
| [`trivy-repo-scan`](../trivy-repo-scan) | Scans the repo for vulnerabilities and secrets with Trivy. |

[1]: https://github.com/SonarSource/sonarqube-scan-action
[2]: ../sonar-report-generation
