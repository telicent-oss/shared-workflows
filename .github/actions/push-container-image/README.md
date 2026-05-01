# Push Container Image GitHub Action

A GitHub Action for building generating metadata for a container image, then
building the container image and pushing it to a container registry.

## Description

When invoked, the action will carry out the following steps. Some are invoked
based on the value of inputs.

* Download a build artifact if a path to a `build-artifact` is specified.
* Build a Maven package when `uses-maven` is `true`.
* Create an SBOM based on the repository contents.
* Log into the required `registry`.
* Create metadata to apply to the container image.
* Build the container image and pushes it to the registry.
* Sign the container image if the `registry` is `quay`. Signing is not required
where the `registry` is `ecr`, as ECR uses an AWS Signer profile to
automatically sign container images that are pushed to it.
* Execute a Trivy dockerfile scan when `trivy-scan-dockerfile` is `true`.
* Execute a Trivy image scan when `trivy-scan-image` is `true`.
* Execute a Grype image scan when `grype-scan-image` is `true`.
* Send an MS Teams notification to a Teams Workflow when the step to build and
push the container image fails, and when a `teams-workflow-url` has been
specified.

## Inputs

### General Options

| Name | Default | Required | Description |
| :--- | :--- | :--- | :--- |
| `github-token` | | Yes | GitHub token to allow the action to interact with the repository. |
| `app-name` | | Yes | The name for the application, used as the main portion of the image name. |
| `app-name-prefix` | `'telicent-'` | No | The prefix for the image name. Defaults to `telicent-`. |
| `dry-run` | `'false'` | No | Whether to test the build and scan without pushing to the registry. |

### Build Options

| Name | Default | Required | Description |
| :--- | :--- | :--- | :--- |
| `enable-buildkit-cache` | `'false'` | No | Whether the docker buildkit cache is required. |
| `build-artifact` | | No | A build artifact to download and use as part of the Docker build. |
| `uses-maven` | `'false'` | No | Whether the build requires the JDK and Maven to be present. |
| `java-version` | `'21'` | No | Specifies the JDK version to install and build with. |
| `jdk` | `'temurin'` | No | Specifies the JDK to use. |

### Container Registry Options

| Name | Default | Required | Description |
| :--- | :--- | :--- | :--- |
| `registry` | | Yes | The container registry to push the image to. Supported values are `aws` (Amazon ECR) or `quay` (Quay.io). |
| `quay-username` | | Yes (if registry is set to `quay`) | Quay username. |
| `quay-token` | | Yes (if registry is set to `quay`) | Quay token. |

### Container Metadata Options

| Name | Default | Required | Description |
| :--- | :--- | :--- | :--- |
| `allow-latest-tag` | `'false'` | No | Set to `true` to explicitly add the `latest` tag. Note that the tag may still be added implicitly if `allow-mutable-tags` is set to `true` and the reference branch is the branch specified as `main-branch`. |
| `allow-development-tag`| `'false'` | No | Set to `true` to explicitly add the `development` tag. Note that the tag may still be added implicitly if `allow-mutable-tags` is set to `true` and the reference branch is the branch specified as `main-branch`. |
| `allow-mutable-tags` | `'true'` | No | Set to `false` to avoid adding mutable tags like `latest` and `development` based on the branch specified as `main-branch`. |
| `main-branch` | `'main'` | No | Specifies the main branch for the repository. When `allow-mutable-tags` is `true`, if this build is on the `main-branch` then the `latest` tag will be applied to the image, otherwise the `development` tag will be applied. |
| `allow-sha-tag` | `'true'` | No | Set to `false` to avoid adding the image SHA as a tag. |
| `sha-tag-format` | `'long'` | No | The format to use when tagging the image with the git SHA. Must be one of `long` (default, 40 character SHA) or `short` (7 character SHA). The environment variable `DOCKER_METADATA_SHORT_SHA_LENGTH` can be used to change the short SHA length. |
| `allow-version-tag` | `'true'` | No | Set to `false` to avoid adding a version tag. |
| `version` | | Yes (if `allow-version-tag` is `true`) | The version for the image. |
| `version-suffix` | | No | A suffix to use a part of the version tag. |

### Container Build Options

| Name | Default | Required | Description |
| :--- | :--- | :--- | :--- |
| `build-args` | | No | Additional build arguments to pass to the Docker `--build-args` flag. |
| `path` | `'.'` | No | The path in which the Dockerfile is located. |
| `dockerfile` | | Yes | The name of the Dockerfile to build the image from. |
| `target` | | No | The target stage within the Dockerfile to build the image from. |
| `image-suffix` | | No | A suffix to use as part of the image name. |

### MS Teams Notification Options

| Name | Default | Required | Description |
| :--- | :--- | :--- | :--- |
| `teams-workflow-url` | | No | MS Teams webhook or workflow URL to send notifications to. |

### Trivy/Grype Scanning Options

| Name | Default | Required | Description |
| :--- | :--- | :--- | :--- |
| `package-directory` | | No | If release has multiple package that are SBOM targets, then set this to disambiguate SBOMs. |
| `grype-scan-image` | `'true'` | No | Whether to run a Grype scan on the built image. |
| `trivy-ignores` | | No | Name of trivy ignore file. Only allowed for BUILD image, MUST NOT be used with DEPLOY images. |
| `trivy-scan-dockerfile`| `'true'` | No | Whether to run a Trivy scan on the Dockerfile used to build the image. |
| `trivy-scan-image` | `'true'` | No | Whether to run a Trivy scan on the built image. |
| `fail-on-unfixed` | `'false'` | No | Whether to fail the scan if unfixed vulnerabilities are found. |
| `remote-vex` | | No | Supplies references to one/more repositories from which additional VEX statements should be obtained and used to filter out vulnerabilities that have been assessed as to not apply to our software products. Note that telicent-oss/telicent-base-images is always included by default so this is only needed if the image being built relies on other images libraries for which VEX statements are required. |

### Build Secrets

| Name | Default | Required | Description |
| :--- | :--- | :--- | :--- |
| `font-awesome-key` | | No | NPM Font Awesome token. |
| `package-pat` | | No | NPM |

## Outputs

| Name | Description |
| :--- | :---------- |
| `image` | The versioned container image tag that was created and published. |
| `sha-image-tag` | The git revision (SAH) applied as a tag to the container image, if applicable. |

## SHA Tag Prefix

Due to an edge case where SemVer rejects a version where the SHA has a leading 0, a prefix of `sha` is applied to the SHA tag in this action.

### Details

When parsing a version number, SemVer does not allow numeric version segments to start with `0`. A version segment is classed as anything that comes after a
`.`, `-` or `+` character.

Although unlikely, it is possible that a SHA can be all numbers (approximately
1 in 268 for a short SHA of 7 characters), meaning that SemVer classifies it as
a numeric identifier as opposed to an alphanumeric identifier.

When the SHA starts with a 0 and is classed as a numeric identifier, this will
cause a failure in the steps that utilise a tool that parses the version, and
it is for that reason a prefix is applied.
