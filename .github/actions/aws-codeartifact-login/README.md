# AWS CodeArtifact Login Action

This GitHub action performs a login to AWS CodeArtifact to obtain an
[authorization token][1] that can then be used in later steps and/or jobs.

The obtained CodeArtifact authorization token is returned as an output called
`token` meaning that it is available to any subsequent steps and or jobs. The
token is registered for masking by GitHub Actions so that even if it is logged
(whether accidentally or otherwise) during the rest of your workflow it will
automatically be masked as a secret.

## Requirements

### AWS Credentials

This action assumes that your workflow has already obtained AWS credentials via
the [configure-aws-credentials][2] action or similar. We recommend using the official AWS action for this.

The pre-existing credentials available within your workflow job are then used
to run the `aws codeartifact get-authorization-token` command to perform the
actual login to CodeArtifact.

## Inputs and Outputs

### Inputs

<!-- markdownlint-disable MD060 -->
| Input          | Required | Default | Description |
| -------------- | -------- | ------- | ----------- |
| domain         | true     | N/A     | The AWS CodeArtifact domain. |
| owner          | true     | N/A     | The AWS CodeArtifact owner. |
| token-lifetime | false    | 900     | The lifetime of the token in seconds. Defaults to 900 seconds (15 minutes). CodeArtifact allows tokens to be issued with a lifetime of between 900 and 43200 (12 hours). |
<!-- markdownlint-enable MD060 -->

### Outputs

| Output |  Description                             |
| -------| ---------------------------------------- |
| user   | The AWS CodeArtifact user. Always `aws`. |
| token  | The value of the AWS CodeArtifact token. |

## Usage

### Basic Usage

At its most basic the action requires only `domain` and `owner` input.

```yaml
name: Simple Login Example
on: 
  push:

jobs:
  example:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v1-node16
        with:
          role-to-assume: arn:aws:iam::<AccountID>:role/<RoleName>
          aws-region: <Region>
      - name: CodeArtifact Login
        id: code-artifact-login
        uses: telicent-oss/shared-workflows/.github/actions/aws-codeartifact-login@main
        with:
          domain: telicent 
          owner: <AccountID> 
```

After our action has been called the CodeArtifact user and token are available
as outputs in subsequent jobs and/or steps.

For example a Maven user might then use a subsequent step to configure Maven with these credentials.

```yaml
      - name: Install Java and Maven
        uses: actions/setup-java@v3
        with:
          java-version: 17
          distribution: temurin
          cache: maven
          server-id: codeartifact
          server-username: ${{ steps.code-artifact-login.outputs.user }}
          server-password: ${{ steps.code-artifact-login.outputs.token }}
```

Or a Python user might do the following:

```yaml
      - name: Install pip requirements
        run: |
          pip install -r requirements.txt
        env:
          PIP_EXTRA_INDEX_URL: "https://${{ steps.code-artifact-login.outputs.user }}:${{ steps.code-artifact-login.outputs.token }}@telicent-098669589541.d.codeartifact.eu-west-2.amazonaws.com/pypi/telicent-code-artifacts/simple/"
```

Please refer to the relevant CodeArtifact and/or GitHub Actions documentation
for best practice with regards to how to supply the obtained credentials to the
appropriate package manager for your builds.

### Advanced Usage

It is possible to further customise the CodeArtifact login process with
additional inputs.

```yaml
name: Simple Login Example
on: 
  push:

jobs:
  example:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v1-node16
        with:
          role-to-assume: arn:aws:iam::<AccountID>:role/<RoleName>
          aws-region: <Region>
      - name: CodeArtifact Login
        id: code-artifact-login
        uses: telicent-oss/shared-workflows/.github/actions/aws-codeartifact-login@main
        with:
          domain: telicent 
          owner: <AccountID> 
          token-lifetime: 1800
```

After our action has been called the CodeArtifact user and token are available
as outputs in subsequent jobs and/or steps. Please refer to examples in [Basic Usage][3] for more information on how to use the outputs in subsequent steps.

#### Token Lifetime

Generally the `token-lifetime` should be set to a length that corresponds to
the approximate length of your build, allowing some slack for the performance
vagaries of running a build in GitHub Actions. If you don't explicitly specify
this then the default lifetime is 900 seconds (15 minutes), which is the minimum
permitted duration for a token.

AWS enforces a maximum token duration of 43200 (12 hours), if your build takes
longer than that you might need more help than this action can provide!

[1]: https://docs.aws.amazon.com/codeartifact/latest/ug/tokens-authentication.html
[2]: https://github.com/aws-actions/configure-aws-credentials
[3]: #basic-usage
