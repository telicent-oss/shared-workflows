# AWS CodeArtifact Login Action

This repository provides a GitHub Action that performs a login to AWS CodeArtifact to obtain an [authorization token][1]
that can then be used in later job steps.

The obtained CodeArtifact authorization token is exported as an environment variable via the `$GITHUB_ENV` file meaning
that it is available to any subsequent job steps.  The token is also registered for masking by GitHub Actions so that
even if it is logged (whether accidentally or otherwise) during the rest of your Actions workflow it will automatically
be masked as a secret.

# Requirements

**IMPORTANT:** This action assumes that your workflow has already obtained AWS credentials via the
[configure-aws-credentials][2] action or similar.  The pre-existing credentials available within your workflow job are
then used to run the `aws codeartifact get-authorization-token` command to perform the actual login to CodeArtifact.

# Usage

At its most basic the action is used as follows:

```yaml
name: Simple Login Example
on: 
  push:
  workflow_dispatch:

jobs:
  example:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read

    steps:
      # Per requirements you first need to obtain AWS Credentials somehow before using this action
      # We recommend using the official AWS action for this, please refer to their documentation
      # for necessary inputs 
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v1-node16
        with:
          role-to-assume: arn:aws:iam::098669589541:role/AWSDeployCodeArtifact
          aws-region: eu-west-2

      # Use this action to obtain the AWS CodeArtifact token
      - name: "CodeArtifact Login"
        uses: Telicent-io/aws-codeartifact-login-action@v1
        with:
          # The AWS CodeArtifact Domain
          domain: telicent 
          # The AWS CodeArtifact Domain Owner, note the need to quote if your Owner has a leading zero
          owner: "098669589541" 

      # Add steps that use the token as you see fit...
```

After our action has been called the CodeArtifact token is available in the environment of subsequent steps via the
`AWS_CODEARTIFACT_TOKEN` environment variable.  The default username `aws` used for communicating with CodeArtifact is
also exported to the `AWS_CODEARTIFACT_USER` variable.

For example a Maven user might then use a subsequent step to configure Maven with these credentials e.g.

```yaml
      - name: Install Java and Maven
        uses: actions/setup-java@v3
        with:
          java-version: 17
          distribution: temurin
          cache: maven
          server-id: codeartifact
          server-username: AWS_CODEARTIFACT_USER
          server-password: AWS_CODEARTIFACT_TOKEN
```

Or a Python user might do the following:

```yaml
      - name: Install pip requirements
        run: |
          pip install -r requirements.txt
        env:
          PIP_EXTRA_INDEX_URL: "https://aws:${{ env.AWS_CODEARTIFACT_TOKEN }}@telicent-098669589541.d.codeartifact.eu-west-2.amazonaws.com/pypi/telicent-code-artifacts/simple/"
```

Again please refer to the relevant CodeArtifact and/or GitHub Actions documentation for how best to supply the obtained
credentials to the appropriate package manager for your builds.

# Advanced Usage

We provide the ability to further customise the CodeArtifact login process as shown in this example:

```yaml
name: Advanced Login Example
on: 
  push:
  workflow_dispatch:

jobs:
  example:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read

    steps:
      # Per requirements you first need to obtain AWS Credentials somehow before using this action
      # We recommend using the official AWS action for this, please refer to their documentation
      # for necessary inputs 
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v1-node16
        with:
          role-to-assume: arn:aws:iam::098669589541:role/AWSDeployCodeArtifact
          aws-region: eu-west-2

      # Use this action to obtain the AWS CodeArtifact Token
      - name: "CodeArtifact Login"
        uses: Telicent-io/aws-codeartifact-login-action@v1
        with:
          domain: telicent
          owner: "098669589541"
          # Place the CodeArtifact username and token into custom environment variables
          user-variable: "CUSTOM_USER"
          token-variable: "CUSTOM_TOKEN"
          # Extend the lifetime of the token to 3600 seconds (1 hour)
          token-lifetime: "3600"
```

In this example the CodeArtifact credentials are placed into the `CUSTOM_USER` and `CUSTOM_TOKEN` variables,
additionally the retrieved token will have a lifetime i.e. validity of 1 hour.

## Token Lifetime

Generally you should set a `token-lifetime` that corresponds to the approximate length of your build, allowing some
slack for the performance vagaries of running a build in GitHub Actions.  If you don't explicitly specify this then the
default lifetime is 900 seconds (15 minutes) which is the minimum permitted duration for a token.

AWS enforces a maximum token duration of 43200 (12 hours), if your build takes longer than that you might need more help
than this action can provide!

[1]: https://docs.aws.amazon.com/codeartifact/latest/ug/tokens-authentication.html
[2]: https://github.com/aws-actions/configure-aws-credentials
