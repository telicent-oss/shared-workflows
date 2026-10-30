# Standalone main-branch SonarQube analysis

`main-sonarqube-scan.yml` implements TC-615. It analyses a caller repository independently of its build/publication workflow, using the existing Maven or CLI Sonar action. It has no schedule of its own: add a small caller to each repository's default branch. No existing build checks are disabled by this change (SCAN-04 and repository adoption are separate work).

The workflow checks out the configured branch with full history, records its SHA once and uses that checkout for preparation, coverage and analysis. It sets the Sonar branch and SCM revision explicitly, including for manual runs launched from another branch. Scheduled runs, manual runs and target-branch pushes are supported; PR and feature-branch push invocations are rejected. A failed vulnerability workflow cannot suppress this analysis unless a caller explicitly adds a dependency.

## Maven caller (including private dependencies)

Save this in the application repository, for example `.github/workflows/sonarqube-main.yml`:

```yaml
name: Main SonarQube analysis
on:
  schedule:
    - cron: '23 3 * * *'
  workflow_dispatch:
permissions:
  contents: read
  id-token: write
concurrency:
  group: standalone-sonar-main
  cancel-in-progress: false
jobs:
  sonar:
    uses: telicent-oss/shared-workflows/.github/workflows/main-sonarqube-scan.yml@main
    with:
      scanner: maven
      main-branch: main
      java-version: '21'
      maven-profiles: docker
      maven-args: -Dtest.maxForks=1
      # Optional; omit for public dependencies or supply MAVEN_USERNAME/PASSWORD.
      codeartifact-role: arn:aws:iam::098669589541:role/AWSDeployCodeArtifact
      maven-repository-id: aws-codeartifact-telicent
      coverage-paths: |
        module-one/target/site/jacoco/jacoco.xml
        module-two/target/site/jacoco/jacoco.xml
    secrets:
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
      SONAR_HOST_URL: ${{ secrets.SONAR_HOST_URL }}
      TEAMS_WEBHOOK_URL: ${{ secrets.TEAMS_WEBHOOK_URL }}
```

Replace the module paths with actual expected coverage-producing modules (or use the default `**/target/site/jacoco/jacoco.xml`). Every supplied glob must match at least one nonempty file. Explicit paths catch omitted modules more reliably than one broad glob. The project must configure JaCoCo report generation and pin `sonar-maven-plugin` and its project identity in its POM. Modules without applicable analysis should use the project's existing `sonar.skip` configuration.

Maven runs `clean install` locally, then the existing Maven scan action with `compile: false`, the same profiles/arguments, and the freshly generated reports. `install` supports dependencies across reactor modules for the separate scanner invocation; it does not deploy to a remote Maven repository. The build adds `-Dgpg.skip -Dcyclonedx.skip`. Never supply publishing goals, test/coverage skip flags or shell quoting in `maven-args`: flags are split on whitespace, without shell evaluation. A configured preparation script runs before the Maven build if extra setup is needed.

Private dependencies use the optional CodeArtifact OIDC role; no telicent-test workflow modification is required. Configure AWS trust for each caller repository and its target branch, not just telicent-test. The token is masked and exposed as `MAVEN_USERNAME`/`MAVEN_PASSWORD` and legacy `AWS_CODEARTIFACT_USER`/`AWS_CODEARTIFACT_TOKEN`. Java setup writes the Maven server entry for `maven-repository-id`. With no role, optional `MAVEN_USERNAME` and `MAVEN_PASSWORD` secrets supply ordinary repository credentials.

## CLI caller (frontend or Python)

```yaml
name: Main SonarQube analysis
on:
  schedule:
    - cron: '37 3 * * *'
  workflow_dispatch:
permissions:
  contents: read
  id-token: write
concurrency:
  group: standalone-sonar-main
  cancel-in-progress: false
jobs:
  sonar:
    uses: telicent-oss/shared-workflows/.github/workflows/main-sonarqube-scan.yml@main
    with:
      scanner: cli
      preparation-script: .github/scripts/sonar-coverage.sh
      node-version: '22'
      coverage-paths: coverage/lcov.info
      sonar-args: -Dsonar.javascript.lcov.reportPaths=coverage/lcov.info
      # Optional if already in sonar-project.properties:
      sonar-project-key: my-existing-project
      sonar-organization: telicent-oss
    secrets:
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
      SONAR_HOST_URL: ${{ secrets.SONAR_HOST_URL }}
      TEAMS_WEBHOOK_URL: ${{ secrets.TEAMS_WEBHOOK_URL }}
      PACKAGE_PAT: ${{ secrets.PACKAGE_PAT }}
      FONT_AWESOME_KEY: ${{ secrets.FONT_AWESOME_KEY }}
```

The caller owns a bash preparation script committed on the target branch. For an npm project using a committed package-lock.json, it might contain:

```bash
#!/usr/bin/env bash
set -euo pipefail
npm ci
npm run test:coverage
```

Use the repository's actual Yarn/pnpm/Python install and test commands. Corepack/pnpm/Yarn activation and private package registry configuration belong in this script; runtime installation alone does not configure package managers. Optional `PACKAGE_PAT`, `FONT_AWESOME_KEY`, `NPM_REGISTRY_TOKEN` and `NODE_AUTH_TOKEN` (from `NPM_REGISTRY_TOKEN`) are available only during preparation. Do not print credentials or enable shell tracing. Scripts should install dependencies and generate coverage only; they are trusted repository code and must not deploy/publish. CLI setup installs both Node and Python; use `python-version` for Python projects and set `coverage-paths` plus `sonar.python.coverage.reportPaths` appropriately.

For a monorepo set `working-directory` to the project directory; script paths, coverage patterns and CLI scanner properties are relative to it. Maven action working-directory defaults to `.` for backward compatibility.

## Configuration and outputs

- `main-branch`: caller default branch when omitted; must identify a branch, not a tag or SHA.
- `scanner`: `maven` (default) or `cli`. CLI requires `preparation-script`.
- `coverage-paths`: newline-separated expected globs, defaulting to JaCoCo. Pre-existing matching reports are removed before preparation. Coverage cannot be omitted silently. For Maven, validated patterns are passed comma-separated to the scanner. For CLI, also configure the language-specific Sonar coverage property.
- `java-version` / `java-distribution`: `21` / `temurin`. CLI runtimes default to Node `22`, Python `3.12`.
- `sonar-host-url`: optional input, then optional `SONAR_HOST_URL` secret, then `https://sonarcloud.io`.
- `sonar-project-key`, `sonar-organization`, `sonar-args`: CLI identity/properties; Maven reads project identity from its POM.
- `fail-on-quality-gate`: defaults to `true`; disabling this still performs analysis. `quality-gate-timeout-seconds` defaults to `300` and must be a positive integer.
- CodeArtifact settings: optional `codeartifact-role`, `aws-region` (`eu-west-2`), `codeartifact-domain` (`telicent`), `codeartifact-owner` (`098669589541`) and `maven-repository-id` (`aws-codeartifact-telicent`).
- `notify-teams`: defaults to `true`; requires `TEAMS_WEBHOOK_URL`. Set false only when deliberately disabling notification delivery, e.g. a local/manual smoke-test caller.
- Required secret: `SONAR_TOKEN`. Additional optional secrets are declared in the workflow for explicit mapping or `secrets: inherit`.
- Outputs: `source-sha` and `dashboard-url` when available. Job summaries and a 14-day analysis metadata artifact retain dashboard/task links even after a failed quality gate. Coverage is checked and submitted, but not retained as an artifact by this workflow.

The workflow requests contents read and OIDC token write for its analysis job, so callers must grant both even when not using CodeArtifact. It does not request package/release write permissions. Teams runs in a separate job after an analysis failure and includes repository, target branch/SHA, scanner, failure stage, workflow/report link and dashboard link when available. It follows the base-image Adaptive Card pattern, uses JSON-safe payload construction, and never prints the webhook. Missing webhook configuration and delivery errors are visible failures; notification success cannot turn failed analysis green. Clean scans stay quiet. A run that never starts needs separate freshness monitoring.

## Deployment and verification

This reusable workflow references existing shared composite actions at `@main`, matching current repository practice. The Maven composite gains `working-directory`, so publish that change with the workflow. To test from an implementation branch before merge, temporarily point the caller workflow AND both composite action references at that branch or commit. Do not assume a new workflow ref also changes action refs inside it.

Before adoption, run against a representative public Maven repo, private CodeArtifact Maven repo and CLI repo, then exercise failed tests, a failed quality gate and Teams delivery to a test channel. These require real repository credentials and are not replaced by local fixtures. Compare three scheduled cycles before disabling any current build scans.

Local verification:

```bash
ruby tests/test_main_sonarqube_scan.rb
actionlint -shellcheck= .github/workflows/main-sonarqube-scan.yml
```

The fixture tests use temporary files and a stubbed Maven/curl; they exercise failure validation, coverage regeneration, safe argument handling, analysis metadata, monorepo compatibility and Teams JSON/delivery failures without contacting Sonar or Teams.

## Teams channel setup and Auth Server example

Create a Teams **Workflows** webhook, using the channel's Workflows menu and a template such as **Send webhook alerts to a channel**. Select the destination channel and the **When a Teams webhook request is received** trigger. This implementation sends an Adaptive Card envelope (`type: message`, `attachments`, `contentType`, `contentUrl: null`); the flow must post each attachment's `content` as an Adaptive Card to the selected channel. Use the trigger's **Anyone** authentication option because the GitHub sender posts using the secret URL without a Microsoft bearer token. Tenant-user authentication would require additional sender authentication code. Add a co-owner to the flow for continuity.

Copy the saved flow's webhook URL into the caller repository's **Settings → Secrets and variables → Actions → New repository secret**, named `TEAMS_WEBHOOK_URL`. Alternatively, use an organization Actions secret with access granted to each participating repository. The secret belongs to the caller's accessible secrets, not solely shared-workflows. Existing compatible base-image webhook URLs can be reused if the destination channel is appropriate.

Auth Server already declares Sonar project `telicent-io_auth-server`, pins the scanner and generates `target/site/jacoco/jacoco.xml` in Maven verify. Its promotion flow references `SONAR_TOKEN` and `SONAR_HOST_URL`; verify those secrets are accessible and that the token can submit analysis (report-read permissions alone are insufficient). Copy [the Auth Server caller](examples/auth-server-sonarqube.yml) to `auth-server/.github/workflows/sonarqube-main.yml` after publishing the shared workflow and Maven action changes. No Auth Server POM changes are expected from the current local configuration.

The example uses the existing CodeArtifact role. Verify OIDC trust permits the Auth Server repository's main-branch subject and the role can obtain/read its dependency packages. The schedule is daily at 03:23 UTC; it runs from the caller's default branch. Start through **Actions → Auth Server main SonarQube analysis → Run workflow**, inspect coverage/SHA/dashboard, and validate a failure notification in a test channel before production routing. A successful HTTP POST only confirms webhook acceptance; also inspect the Power Automate flow run/channel to confirm the card was posted.

These examples do not disable Auth Server's current build analysis, its container vulnerability scans, or release reporting. SCAN-04 and per-repository adoption handle the later opt-out after parallel validation.

References:
- [Teams Workflows webhooks](https://learn.microsoft.com/en-us/microsoftteams/platform/webhooks-and-connectors/how-to/add-incoming-webhook)
- [Teams trigger authentication and Adaptive Card request schema](https://learn.microsoft.com/en-us/connectors/teams/#when-a-teams-webhook-request-is-received)
- [GitHub Actions secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)
