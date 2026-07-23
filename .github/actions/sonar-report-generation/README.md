# SonarQube Code Health Report Action

This GitHub action queries the SonarQube Web API for a project, renders a PDF
report describing the overall health of the code, and uploads that report to a
path in S3.

## Description

When invoked, the action will carry out the following steps.

* Read the project's measures, quality gate result, issue breakdown and
  historic trends from the SonarQube Web API.
* Render a PDF report covering the quality gate, the four SonarQube ratings,
  headline metrics, new code metrics, an issue breakdown by severity and type,
  trend charts over the last `history-days` days, the most frequently violated
  rules and the files carrying the most issues.
* Write a summary of the report to the GitHub job summary, when `job-summary`
  is `true`.
* Upload the report to `s3-uri`.
* Store the report as a GitHub artifact, when `upload-artifact` is `true`.
* Fail the job when the quality gate is not passing and
  `fail-on-quality-gate` is `true`. The report is generated and uploaded before
  this check runs.

The report is produced with [ReportLab][1] and has no system level
dependencies, so it runs on a stock GitHub hosted runner.

## Requirements

### AWS Credentials

The upload uses the AWS CLI, which is pre-installed on GitHub hosted runners.
Credentials can be supplied either by configuring them earlier in the job with
the [configure-aws-credentials][2] action, or by passing an `aws-role-to-assume`
to this action so that it assumes the role itself. In both cases the role needs
`s3:PutObject` on the destination path.

### SonarQube Token

The `sonar-token` must be a **User Token**, generated from *My Account →
Security → Generate Tokens* with the type set to *User Token*. It needs only
the *Browse* permission on the project. Supply it from a secret rather than
inline.

Analysis tokens do not work, even though they authenticate successfully. A
*Global Analysis Token* (`sqa_` prefix) or *Project Analysis Token* (`sqp_`
prefix) is authorised only for submitting analyses, so most Web API reads come
back as `403 Insufficient privileges` regardless of the permissions held by the
account that created the token. The symptom is a report missing its trends and
last analysis date, with warnings naming the endpoints that were refused. Check
the prefix on the token: a User Token starts `squ_`.

## Inputs

### SonarQube Options

| Name | Default | Required | Description |
| :--- | :--- | :--- | :--- |
| `sonar-host-url` | `https://sonarcloud.io` | No | Base URL of the SonarQube server. |
| `sonar-token` | | Yes | A SonarQube token with permission to browse the project. |
| `sonar-project-key` | | Yes | The key of the project to report on. |
| `sonar-branch` | | No | The branch to report on. Defaults to the project's main branch. |
| `project-version` | | No | The version of the code that was analysed, shown on the report as the analysed version. Takes precedence over the version SonarQube recorded, and is the only way to populate the field where the token cannot read the analysis history. |

### Destination Options

| Name | Default | Required | Description |
| :--- | :--- | :--- | :--- |
| `s3-uri` | | Yes | Destination for the report. A URI ending in `/`, or one naming only a bucket, is treated as a prefix and the generated file name is appended. Anything else is used as the full object key. |
| `aws-region` | | No | AWS region to use for the upload. Only needed when the region is not already set in the job environment. |
| `aws-role-to-assume` | | No | ARN of an IAM role to assume before uploading. When unset, the credentials already available to the job are used. |
| `s3-extra-args` | | No | Extra arguments for `aws s3 cp`, for example `--sse aws:kms --sse-kms-key-id <key-arn>`. |

### Report Options

| Name | Default | Required | Description |
| :--- | :--- | :--- | :--- |
| `report-name` | | No | File name to give the report. Defaults to `sonar-code-health-<project-key>-<branch>-<timestamp>.pdf`. |
| `history-days` | `'90'` | No | Days of history to include in the trend charts. |
| `fail-on-quality-gate` | `'false'` | No | Whether to fail the action when the quality gate is not passing. |
| `job-summary` | `'true'` | No | Whether to write a summary of the report to the GitHub job summary. |
| `upload-artifact` | `'true'` | No | Whether to also store the report as a GitHub artifact. |
| `artifact-name` | `sonar-code-health-report` | No | Name of the GitHub artifact. |
| `artifact-retention-days` | `'30'` | No | Days to retain the GitHub artifact for. |
| `python-version` | `'3.12'` | No | Python version used to generate the report. |

## Outputs

| Output | Description |
| :--- | :--- |
| `report-path` | Path to the generated PDF on the runner. |
| `report-name` | File name of the generated PDF. |
| `report-s3-uri` | The S3 URI the report was uploaded to. |
| `quality-gate-status` | The project's quality gate status, one of `OK`, `ERROR`, `WARN` or `NONE`. |
| `summary-json` | Path to a JSON summary of the metrics included in the report. |

## Usage

### Basic Usage

```yaml
name: Sonar Code Health Report
on:
  schedule:
    - cron: '0 6 * * 1'
  workflow_dispatch:

jobs:
  report:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - name: Generate and upload the code health report
        uses: telicent-oss/shared-workflows/.github/actions/sonar-report-generation@main
        with:
          sonar-host-url: https://sonar.example.com
          sonar-token: ${{ secrets.SONAR_TOKEN }}
          sonar-project-key: telicent-access-platform
          s3-uri: s3://telicent-reports/sonar/
          aws-role-to-assume: ${{ secrets.AWS_ROLE_PUBLISH_REPORTS }}
          aws-region: eu-west-2
```

The report is uploaded to
`s3://telicent-reports/sonar/sonar-code-health-telicent-access-platform-20260722-060312.pdf`.

### Using Credentials Already Configured in the Job

Where the job has already obtained AWS credentials, omit `aws-role-to-assume`
and the existing credentials are used.

```yaml
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v6
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_PUBLISH_REPORTS }}
          aws-region: eu-west-2
      - name: Generate and upload the code health report
        uses: telicent-oss/shared-workflows/.github/actions/sonar-report-generation@main
        with:
          sonar-host-url: https://sonar.example.com
          sonar-token: ${{ secrets.SONAR_TOKEN }}
          sonar-project-key: telicent-access-platform
          s3-uri: s3://telicent-reports/sonar/
```

### Advanced Usage

Report on a specific branch, write to a fixed object key so the latest report
is always at a predictable location, encrypt it with KMS, extend the trend
charts to a year and fail the job when the quality gate is not passing.

```yaml
      - name: Generate and upload the code health report
        id: sonar-report
        uses: telicent-oss/shared-workflows/.github/actions/sonar-report-generation@main
        with:
          sonar-host-url: https://sonar.example.com
          sonar-token: ${{ secrets.SONAR_TOKEN }}
          sonar-project-key: telicent-access-platform
          sonar-branch: main
          project-version: ${{ github.ref_name }}
          s3-uri: s3://telicent-reports/sonar/latest/access-platform.pdf
          s3-extra-args: --sse aws:kms --sse-kms-key-id ${{ secrets.AWS_KMS_KEY_ARN }}
          aws-role-to-assume: ${{ secrets.AWS_ROLE_PUBLISH_REPORTS }}
          aws-region: eu-west-2
          history-days: '365'
          fail-on-quality-gate: 'true'
```

### Using the Outputs

The outputs can be used to chain further steps, such as an MS Teams
notification.

```yaml
      - name: Report the outcome
        run: |
          echo "Quality gate: ${{ steps.sonar-report.outputs.quality-gate-status }}"
          echo "Report: ${{ steps.sonar-report.outputs.report-s3-uri }}"
```

The `summary-json` output points at a file with the same figures in a machine
readable form.

```json
{
  "projectKey": "telicent-access-platform",
  "qualityGateStatus": "ERROR",
  "failingConditions": ["new_coverage", "new_reliability_rating"],
  "metrics": {
    "bugs": 14.0,
    "coverage": 63.4,
    "reliabilityRating": "C"
  }
}
```

## Compatibility

The action targets the current SonarQube Web API but degrades where a server
does not offer part of it, so it also works against older SonarQube versions
and SonarCloud.

* Authentication is attempted with a bearer token first, falling back to the
  token-as-basic-auth-username form used by SonarQube 9 and earlier.
* Metrics unknown to the server are dropped before they are requested, so the
  measures call never fails over a metric that has since been removed.
* The issue search falls back from the `components` parameter to the
  deprecated `componentKeys` for servers older than SonarQube 10.4.
* The project name is read from `api/components/show`, falling back to
  `api/measures/component` where the token cannot browse the component. Only a
  project that resolves through neither is treated as missing.
* File paths are derived from the component keys already present in the issue
  facets, so no per-file lookup is needed.
* Sections whose data is unavailable, such as trends on a project with a single
  analysis, are omitted rather than left blank.

Warnings are emitted for any endpoint that could not be read, and the report is
still produced from whatever data was available.

## Development

The report generator is a standalone script and can be run against a SonarQube
server directly.

```bash
pip install -r .github/actions/sonar-report-generation/scripts/requirements.txt
export SONAR_TOKEN=<token>
python .github/actions/sonar-report-generation/scripts/generate_report.py \
  --host-url https://sonar.example.com \
  --project-key telicent-access-platform \
  --branch main \
  --output report.pdf \
  --summary-json summary.json
```

The scripts are organised as follows.

| File | Description |
| :--- | :--- |
| `scripts/sonar_api.py` | The SonarQube Web API client and the `ProjectHealth` snapshot it produces. |
| `scripts/pdf_report.py` | Renders a `ProjectHealth` snapshot as a PDF. |
| `scripts/generate_report.py` | Command line entry point, plus the JSON and Markdown summaries. |

[1]: https://docs.reportlab.com/
[2]: https://github.com/aws-actions/configure-aws-credentials
