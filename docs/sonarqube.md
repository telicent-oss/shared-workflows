# SonarQube in the shared workflows

## Policy in one paragraph

The Quality Gate is **enforced on branch builds** and **reported but not enforced on the
main branch and on tags**. A code quality verdict should stop work from *landing*; it
should never stop a merge from completing or a release from being cut, because by that
point the code is already in and blocking it only breaks the pipeline for everyone. When
the gate fails on main or on a tag the build stays green and the failure is surfaced as a
GitHub warning annotation and a job summary entry.

## Components

| Component | Scanner | Used by |
|---|---|---|
| `.github/actions/mvn-sast-scanning` | `mvn sonar:sonar` | `maven.yml`, `parallel-maven.yml` |
| `.github/actions/sast-scanning` | Sonar Scanner CLI | JS/TS repos directly |
| `.github/actions/sonar-report-generation` | Web API → PDF → S3 | release evidence, via `push-container-image` / `promote-to-quay` |

## The `quality-gate` input

Both scan actions take `quality-gate`, which is what decides whether a verdict is
*observed* and whether it is *enforced*. These are separate decisions:

| Mode | Waits for the verdict | Fails the build | Reports the result |
|---|---|---|---|
| `enforce` | yes | yes | yes |
| `warn` | yes | no | yes — warning + job summary |
| `off` | no | no | no — nothing is observed |

`off` is genuinely silent: the scanner submits the analysis and returns without asking
for the result, so there is nothing to report. **If you want a project's build unblocked
while it is brought up to standard, use `warn`, not `off`.**

A scan that fails *before reaching the server* — bad credentials, a compilation failure,
a network problem — is a tooling failure rather than a verdict, and fails the build in
every mode. `warn` must not be able to hide a scanner that has stopped working.

### Deprecated input

`fail-on-quality-gate` / `sonar-fail-on-quality-gate` still work: `true` maps to
`enforce`, `false` maps to `off`. Both emit a deprecation warning. Note that the old
`false` is the silent mode, which is usually not what the caller wanted.

## Workflow-level control

`maven.yml` and `parallel-maven.yml` resolve the mode in the `prepare-sonarqube` job, in
this order:

1. `SONAR_QUALITY_GATE: false` → `off`
2. `SONAR_MODE` set explicitly → that value
3. tag build → `off`
4. `release/*` branch build → `warn`
5. `MAIN_BRANCH` build → `warn`
6. otherwise → `enforce`

The chosen mode and the reason for it are printed in the `prepare-sonarqube` job log.

```yaml
# Default: enforce on branches, warn on main and release/*, skip tags
uses: telicent-oss/shared-workflows/.github/workflows/maven.yml@main

# A project being brought up to standard: never block, always report
with:
  SONAR_MODE: warn

# A project that wants the old strict behaviour everywhere
with:
  SONAR_MODE: enforce
```

## Where the scan runs

In both workflows SonarQube runs as **its own job** (`sonarqube-code-scan`), never as a
step inside `build`. Nothing depends on that job. This matters because a failing step
fails its job, and a failing job causes every dependent job to be skipped — so a gate in
the `build` job would take the version output, the container images and the GitHub
release down with it, regardless of any `warn` setting.

Note that `continue-on-error` **cannot** be used on a job that calls a reusable workflow
(it requires `runs-on`), so a consumer cannot wrap its `uses:` call to tolerate a Sonar
failure. That is why the handling lives here rather than in the consuming repositories.

## What is skipped

- **Dependabot commits** (`github.actor == 'dependabot[bot]'`) — a dependency bump cannot
  change a Quality Gate outcome.
- **release-please release commits** (`chore(main): release …`) — version and changelog
  bumps only, and a release commit should not be the thing that reports a pre-existing
  quality problem.
- **Tag builds** — release evidence comes from `sonar-report-generation`, so the reusable
  Maven workflows skip a fresh SonarQube run on tags by default.
- **Commits with no change under `src/` or `pom.xml`**, via `detect-changes-action`. Note
  that the Sonar job runs this check *without* `output-on-base`, unlike the build job:
  the build forces tests to always run on the base branch, but there is no equivalent
  reason to re-analyse main when no source changed.

## Release evidence

`sonar-report-generation`, invoked from `push-container-image` / `promote-to-quay`, is
the non-blocking record of a release's code health: it reads the gate status from the Web
API, renders a PDF and uploads it to S3. This — not a fresh build-time scan on the tag —
is where a release's SAST evidence comes from. It defaults to `fail-on-quality-gate:
false` and should stay that way.

## Open questions

- **Where the warning should go.** Currently a warning annotation plus a job summary
  entry, which nobody owns. Both scan actions expose a `quality-gate-status` output so a
  caller can route a non-blocking failure somewhere with an owner — a Teams post via
  `.github/actions/notify-teams`, a non-blocking check run, or a tracking issue. Not yet
  wired up.
- **PR analysis.** No repository that runs Sonar uses a `pull_request` trigger, so
  SonarQube performs branch analysis and there is no PR decoration. Moving to
  `pull_request` would let the gate be evaluated where a developer can act on it, and
  would make `warn` on main a fallback rather than the main line of defence.
