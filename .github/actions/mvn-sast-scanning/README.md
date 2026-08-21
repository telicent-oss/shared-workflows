# Maven Static Application Security Testing Action

This GitHub action runs a SonarQube analysis over a Maven project using the
[SonarScanner for Maven][1] (`mvn sonar:sonar`) and reports, and optionally
enforces, the project's quality gate.

It is the Maven counterpart to the [sast-scanning][2] action, which uses the
standalone Sonar Scanner CLI. Prefer this action for Maven projects: the Maven
scanner understands the reactor, so multi-module projects, per-module coverage
reports and `sonar.skip` on individual modules all work without extra
configuration.

## Description

When invoked, the action will carry out the following steps.

* Validate the inputs, failing early with a clear message rather than leaving
  the scanner to fail opaquely.
* Compile the project if required (see [Compilation](#compilation)), since the
  Sonar Java analyser needs bytecode in `target/classes` to work from.
* Run `mvn sonar:sonar` and, unless `quality-gate` is `off`, wait for the
  quality gate result. Whether a failing gate fails the job depends on
  `quality-gate` — see [The quality gate](#the-quality-gate).
* Distinguish a quality gate verdict from a scan that never reached the server:
  the latter fails the job in every mode, so `warn` cannot hide a broken scan.
* Emit the analysis dashboard URL as an output, even when the quality gate
  fails — which is exactly when a developer needs the link.

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

### Java and Maven

The caller is responsible for installing Java and Maven before invoking the
action, typically:

```yaml
      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: '21'
          cache: maven
```

### SonarQube Token

The `sonar-token` needs permission to submit an analysis for the project, so
either a *Global Analysis Token* (`sqa_` prefix), a *Project Analysis Token*
(`sqp_` prefix) or a *User Token* (`squ_` prefix) with *Execute Analysis* will
do. Supply it from a secret rather than inline.

### Project Configuration

Per-project configuration lives in the consuming repository's `pom.xml` rather
than in workflow inputs. The parent POM should pin the scanner plugin in
`pluginManagement` and declare the project identity as properties:

```xml
<properties>
  <sonar.projectKey>telicent-oss_my-project</sonar.projectKey>
</properties>

<build>
  <pluginManagement>
    <plugins>
      <plugin>
        <groupId>org.sonarsource.scanner.maven</groupId>
        <artifactId>sonar-maven-plugin</artifactId>
        <version>5.1.0.4751</version>
      </plugin>
    </plugins>
  </pluginManagement>
</build>
```

Modules that should not be analysed (e.g. benchmarks) opt out in their own
`pom.xml`:

```xml
<properties>
  <sonar.skip>true</sonar.skip>
</properties>
```

## Compilation

The Sonar Java analyser works from bytecode, so compiled classes must exist in
each module's `target/classes` before the scan. The `compile` input controls
whether the action produces them itself (via `mvn test-compile`):

* `false` — a build step already ran earlier in the same job. Nothing to do.
* `true` — the scan runs in a fresh job, e.g. fanning in after a matrix
  build. The action compiles first. Tests are **not** rerun, so coverage must
  be supplied via `coverage-report-paths` in this scenario.
* `auto` (default) — the action compiles if any module containing
  `src/main/java` has no `target/classes` directory, and logs its decision as
  a workflow notice. This errs towards compiling when in doubt; prefer an
  explicit `true`/`false` in fan-in workflows that download build output for
  only a subset of modules.

## Inputs

| Name | Default | Required | Description |
| :--- | :--- | :--- | :--- |
| `sonar-host-url` | `https://sonarcloud.io` | No | Base URL of the SonarQube server used for the scan. |
| `sonar-token` | | Yes | A SonarQube token with permission to analyse the project. |
| `compile` | `auto` | No | Whether to compile before scanning: `true`, `false` or `auto`. See [Compilation](#compilation). |
| `coverage-report-paths` | | No | Value for `sonar.coverage.jacoco.xmlReportPaths`. Leave empty when tests ran in this job, as the scanner's per-module default of `target/site/jacoco/jacoco.xml` applies. When coverage was produced in other jobs and downloaded as artifacts, pass an absolute glob. |
| `quality-gate` | `warn` | No | `enforce`, `warn` or `off`. See [The quality gate](#the-quality-gate). |
| `fail-on-quality-gate` | | No | **Deprecated** — use `quality-gate`. `true` maps to `enforce`, `false` maps to `off`. |
| `quality-gate-timeout-seconds` | `'300'` | No | Maximum time to wait for the quality gate result. |
| `maven-args` | | No | Additional arguments for the Maven invocations, for example `-pl` or extra `-D` properties. |

## Outputs

| Output | Description |
| :--- | :--- |
| `dashboard-url` | URL of the analysis dashboard on the SonarQube server. Emitted even when the quality gate fails, so callers can surface it in job summaries or PR comments. |
| `quality-gate-status` | The observed gate result, `PASSED`, `FAILED` or empty when not observed. Populated in `warn` mode too, so a caller can route a non-blocking failure to a notification or check run. |

## The Quality Gate

`quality-gate` controls two separate decisions — whether the verdict is
*observed*, and whether it is *enforced*.

| Mode | Waits for the verdict | Fails the build | Reports the result |
| :--- | :--- | :--- | :--- |
| `enforce` | yes | yes | yes |
| `warn` | yes | no | yes — warning annotation and job summary |
| `off` | no | no | no — nothing is observed |

`off` is genuinely silent: the scanner submits the analysis and returns
without asking for the result, so there is nothing left to report. To unblock
a project's build while it is brought up to standard, use `warn`, not `off`.

A scan that fails before reaching the server — bad credentials, a compilation
failure, a network problem — is a tooling failure rather than a verdict, and
fails the build in every mode.

Note that a gate which does not resolve within
`quality-gate-timeout-seconds` is indistinguishable from one that failed, so a
slow analysis queue reports as a failure. That is a reason to prefer `warn` on
refs which must not be blocked.


## Usage

### Single-Job Workflow

Build and test first, then scan in the same job. Compilation is skipped
because the build already produced classes, and coverage is picked up from
each module's default JaCoCo report path.

```yaml
name: Maven SAST
on:
  pull_request:
  push:
    branches: [main]

jobs:
  build-and-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
        with:
          fetch-depth: 0

      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: '21'
          cache: maven

      - name: Build and test
        run: mvn verify --batch-mode

      - name: SonarQube scan
        uses: telicent-oss/shared-workflows/.github/actions/mvn-sast-scanning@main
        with:
          sonar-token: ${{ secrets.SONAR_TOKEN }}
          compile: 'false'
```

### Fan-In After a Matrix Build

Tests run across a matrix, each leg uploads its JaCoCo XML reports as
artifacts, and a single scan job fans in afterwards. The scan job has a fresh
workspace, so the action compiles the project itself and coverage is supplied
explicitly.

```yaml
  scan:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v5
        with:
          fetch-depth: 0

      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: '21'
          cache: maven

      - name: Download coverage reports
        uses: actions/download-artifact@v5
        with:
          pattern: coverage-*
          path: sonar-coverage

      - name: SonarQube scan
        uses: telicent-oss/shared-workflows/.github/actions/mvn-sast-scanning@main
        with:
          sonar-token: ${{ secrets.SONAR_TOKEN }}
          compile: 'true'
          coverage-report-paths: ${{ github.workspace }}/sonar-coverage/**/jacoco.xml
```

### Scanning Without Enforcing the Gate

Useful while a project is being brought up to the standard, so the analysis is
still published but a failing gate does not block the build.

```yaml
      - name: SonarQube scan
        uses: telicent-oss/shared-workflows/.github/actions/mvn-sast-scanning@main
        with:
          sonar-token: ${{ secrets.SONAR_TOKEN }}
          quality-gate: warn
```

### Surfacing the Dashboard URL

The `dashboard-url` output is written even when the gate fails, so pair it
with `if: always()` to keep the link visible on failing builds.

```yaml
      - name: SonarQube scan
        id: sonar
        uses: telicent-oss/shared-workflows/.github/actions/mvn-sast-scanning@main
        with:
          sonar-token: ${{ secrets.SONAR_TOKEN }}

      - name: Link to the analysis
        if: always()
        run: echo "### [SonarQube dashboard](${{ steps.sonar.outputs.dashboard-url }})" >> "$GITHUB_STEP_SUMMARY"
```

## Related Actions

| Action | Description |
| :--- | :--- |
| [`sast-scanning`](../sast-scanning) | Runs the Sonar Scanner CLI over a repo. Use for non-Maven projects. |
| [`sonar-report-generation`](../sonar-report-generation) | Renders a PDF code health report from an existing SonarQube analysis and uploads it to S3. |

[1]: https://docs.sonarsource.com/sonarqube-server/latest/analyzing-source-code/scanners/sonarscanner-for-maven/
[2]: ../sast-scanning
