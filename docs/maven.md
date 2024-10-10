# Maven Shared Workflow

The Maven Shared Workflow definition may be found [here (serial buld)](../.github/workflows/maven.yml) and 
[here (parallel build)](../.github/workflows/parallel-maven.yml)

These workflows are designed to build Maven based projects and includes automation of `SNAPSHOT` deployment, Maven
Central releases and GitHub Releases.  See [What this Does](#what-this-workflow-does) for more details on exactly what's
contained within this workflow.

## Requirements

This workflow has the following requirements:

- The repository it is called from **MUST** contain a `pom.xml` file in the root of the repository
- The Maven project **MUST** be configured such that it meets the Maven Central requirements, the helper script
  [`isMavenCentralReady.sh`](../isMavenCentralReady.sh) in this repository can be used to check whether a repository
  meets these requirements:
  ```bash
  $ ./isMavenCentralReady.sh /path/to/repository/
  ```
  Which will do a bunch of sanity checks to see if various Maven Central requirements are being met.  This script is not
  perfect so the first release you attempt to make with this workflow **MAY** still fail in some circumstances.
  Telicent developers should refer to our internal documentation on preparing a repository for open source for more
  specific details.

## Private vs Public Workflow

This is the public version of this workflow for use in open source (public) repositories.  For internal private Telicent
repositories there is a private workflow whose documentation may be found in the private workflows repository.

The key differences with this workflow versus the private workflow are as follows:

- This workflow automates the deployment of release artifacts to Maven Central
- This workflow is designed to build **only** for public artifact repositories
- This workflow imports a GPG Key for code signing when supplied as a secret
- This workflow only releases GPG signed artifacts

## What this Workflow Does

The serial Maven workflow does the following:

1. A `cache-dependencies` job that:
    - Configures Java and Maven
    - Does a `mvn dependency:go-offline` to populate a GitHub Actions Cache used in the subsequent job
2. A `build` job that:
    - Configures Java and Maven
    - Optionally logs into DockerHub if configured to do so (see `USES_DOCKERHUB_IMAGES` in [workflow
      inputs](#workflow-inputs))
    - Builds the project with `mvn install`
    - Scans the project for high/critical severity vulnerabilities attaching reports to the build
   vulnerabilities with `trivy`
    - Adds the detected Maven project version (value of `project.version`) to the job outputs
    - Optionally deploys `SNAPSHOT`s if the build is a `SNAPSHOT` and it's on the `MAIN_BRANCH`, and `PUBLISH_SNAPSHOTS`
      is configured appropriately, i.e. `mvn deploy -DskipTests`, tests are skipped as this step only runs if the
      earlier full build was successful
3. A `github-release` job that runs only when the built version is not a `SNAPSHOT` and the workflow was triggered from
   a Git tag:
    - Configures Java and Maven
    - Does a quick Maven build (`mvn install -DskipTests`) since this job is dependent on the `build` job being
      successful which does a full build
    - Deploys the release to Maven Central
    - Extracts release notes from the configured `CHANGELOG_FILE` (if possible) and detects whether GitHub Release Note
      auto-generation is configured on the repository
    - Generates a GitHub

For the parallel build version of the workflow the steps are slightly different:

1. A `cache-dependencies` job, this is the same as for the serial workflow
2. A `detect-modules` job that:
    - Configures Java and Maven
    - Generates a JSON Output that is an array of the modules found in the repository
3. A `build` job for each detected module that:
    - Configures Java and Maven
    - Optionally logs into DockerHub if configured to do so (see `USES_DOCKERHUB_IMAGES` in [workflow
      inputs](#workflow-inputs))
    - Builds the module and its dependencies with `mvn install -DskipTests -am -pl :module`
    - Tests the module with `mvn install -pl :module`
4. A `scan-and-publish` job that: 
    - Configures Java and Maven
    - Does a quick Maven build (`mvn install -DskipTests`) since this job is dependent on the `build` jobs being
      successful which has built and verified each individual module
    - Scans the project for high/critical severity vulnerabilities attaching reports to the build vulnerabilities with
   `trivy`
    - Adds the detected Maven project version (value of `project.version`) to the job outputs
    - Optionally deploys `SNAPSHOT`s if the build is a `SNAPSHOT` and it's on the `MAIN_BRANCH`, and `PUBLISH_SNAPSHOTS`
      is configured appropriately, i.e. `mvn deploy -DskipTests`, tests are skipped as this step only runs if the
      earlier full build was successful
5. A `github-release` job that is the same as the serial build

Note that many aspects of the above may be configured via [workflow inputs](#workflow-inputs).

### Choosing the Serial vs Parallel Builds

They key motivator for whether to use the serial or parallel build is how long your build takes.  For shorter builds
(10-15 minutes) the serial build should be used as it is simpler.  However, for longer builds the parallel build should
be used as this can significantly improve CI/CD runtime as the observed runtime will be dictated by the slowest building
module (typically the module with the most complex/largest number of tests).

Additionally if your build has some tests that can experience transient failures, e.g. due to timing or container setup
issues, then you may benefit from using the parallel build as in the event of a failure you can restart just the failing
module build and not the entire build.

## Simple Usage Example

Here's an example usage of the workflow:

```yaml
name: Maven Build

on:
  # Run workflow for any push to a branch or a tag
  push:
    branches:
      - '**'
    tags:
      - '**'
  # Allow manual triggering of the workflow
  workflow_dispatch:

jobs:
  maven-build:
    uses: telicent-oss/shared-workflows/.github/workflows/maven.yml@main
    with:
      # Want SNAPSHOTs to be published from main
      PUBLISH_SNAPSHOTS: true
      # Included more detailed logging when debugging (i.e. re-running failed tasks)
      MAVEN_DEBUG_ARGS: -Dlogback.configurationFile=logback-debug.xml
    secrets: inherit
```

Key notes:

- You **MUST** include `secrets: inherit` when calling the reusable workflow otherwise releases won't succeed
- Your workflow trigger criteria **MUST** include a `tags` trigger otherwise the `github-release` job will
never be run.

### Using the Parallel Build

Workflow inputs are identical across both the serial and parallel build so you merely need to change the referenced
workflow in the `uses` clause to be `parallel-maven.yml` instead e.g.

```yaml
name: Maven Parallel Build

on:
  # Run workflow for any push to a branch or a tag
  push:
    branches:
      - '**'
    tags:
      - '**'
  # Allow manual triggering of the workflow
  workflow_dispatch:

jobs:
  maven-build:
    uses: telicent-oss/shared-workflows/.github/workflows/parallel-maven.yml@main
    with:
      # Want SNAPSHOTs to be published from main
      PUBLISH_SNAPSHOTS: true
      # Included more detailed logging when debugging (i.e. re-running failed tasks)
      MAVEN_DEBUG_ARGS: -Dlogback.configurationFile=logback-debug.xml
    secrets: inherit
```

### Combining with other workflows

In the following example we do a Maven build first and then trigger some Docker builds if that succeeds:

```yaml
name: Complex Build

on:
  # Run workflow for any push to a branch or a tag
  push:
    branches:
      - '**'
    tags:
      - '**'
  # Allow manual triggering of the workflow
  workflow_dispatch:

# Only permit one build per branch/tag, except on release branches where we want all
# builds to proceed
concurrency:
  group: ${{ github.workflow }}-${{ github.ref_name }}
  cancel-in-progress: ${{ !contains(github.ref_name, 'release/') }}
    
jobs:
  maven-build:
    uses: telicent-oss/shared-workflows/.github/workflows/maven.yml@main
    with:
      # Some Docker based tests in this repository use public images
      USES_DOCKERHUB_IMAGES: true
      # Want SNAPSHOTs to be published from main
      PUBLISH_SNAPSHOTS: true
      MAIN_BRANCH: main
      MAVEN_ARGS: -Dtest.maxForks=1
      # If running in debug mode, use appropriate logging
      MAVEN_DEBUG_ARGS: -Dlogback.configurationFile=logback-debug.xml
      JAVA_VERSION: 21
      CHANGELOG_FILE: CHANGELOG.md
    secrets: inherit

  docker-build:
    strategy:
      matrix:
        image: [ example-image, another-example-image ]
      fail-fast: false
    needs: maven-build
    uses: telicent-oss/shared-workflows/.github/workflows/docker-push-to-registries.yml@main
    with:
      APP_NAME: ${{ matrix.image }}
      APP_NAME_PREFIX: ""
      PATH: .
      DOCKERFILE: docker/Dockerfile
      VERSION: ${{ needs.maven-build.outputs.version }}
      TARGET: ${{ matrix.image }}
      BUILD_ARGS: |
        PROJECT_VERSION=${{ needs.maven-build.outputs.version }}
      USES_MAVEN: true
      JAVA_VERSION: 21
    secrets: inherit
```

Key Notes:

- Notice that we've added a `concurrency` section to the workflow file to limit the concurrency of our builds. This is
  optional but is often useful to speed up 
- The `docker-build` job uses the `needs` parameter to ensure it only runs after a successful run of the `maven-build`
  job.
- We can refer to the Maven version of the built project via the `needs.maven-build.outputs.version` variable in
  subsequent jobs.

## FAQs

### Do I need a release branch?

Yes, our open source repositories protect the `main` branch from direct pushes, this means you **MUST** always create a
release from a branch and then merge that release back to `main` once it is completed.  If you try to release directly
from `main` then the Maven Release plugin will fail as the push will be rejected by GitHub.

### What triggers the actual GitHub and Maven Central releaes?

The workflow will produce an automatic GitHub release, and publish artifacts to Maven Central whenever you tag the
repository, provided that the tag does not point to a `SNAPSHOT` version.

### How do I make a release?

Use the Maven release plugin from your development machine:

```bash
$ mvn release:clean release:prepare -DreleaseVersion=1.2.3 -DdevelopmentVersion=1.2.4-SNAPSHOT -Dtag=1.2.3
```

Replacing the versions and tag with the appropriate values for your repository.

Go to the GitHub Actions tab for your repository and wait for the build triggered by your tag to complete successfully.
Once this has completed then your release has been pushed to Maven Central and will be visible there in 30 minutes to 4
hours.

### Why does the GitHub Release not contain any release notes?

Firstly, have you ensured that you have a `CHANGELOG.md` or equivalent file in your repository?  If this is named
something other than `CHANGELOG.md` then please set the [`CHANGELOG_FILE`](#workflow-inputs) input accordingly.

Secondly, the release note extraction is based on reading through the Change Log and finding a line that starts `#
<version>` where `<version>` is the declared version of your release.  It then grabs all lines from that point onwards
until the next line starting with an equivalent number of `#`.  If your Change Log is formatted differently, or there is
no section for the current release, then this will not be successfully detected.  Please see our [Extract Release Notes
Action documentation](https://github.com/telicent-oss/extract-release-notes-action/blob/main/README.md#changelog-format)
for more detail about the supported Change Log formats.

### Can I generate release notes automatically instead?

Yes, if you provide a `.github/release.yml` file in your repository then you can take advantage of GitHub's [Automatic
Release
Notes](https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes#configuring-automatically-generated-release-notes)

If this file is present then these will automatically be combined with any manually provided Change Log entries.

# Workflow Inputs

The following table provides a complete reference to the available inputs.

| Name                    | Required? | Type       | Default         | Description                                                                                                                                                                                                                                                                |
|-------------------------|-----------|------------|-----------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `CHANGELOG_FILE`        | `false `  | `string `  | `CHANGELOG.md ` | Specifies the Change Log file in the repository from which release notes can be extracted.                                                                                                                                                                                 |
| `DOCKER_PROFILE`        | `false `  | `string `  | `docker `       | Specifies the name of the profile that enables/disables Docker based tests.                                                                                                                                                                                                |
| `JAVA_VERSION`          | `false `  | `number `  | `21 `           | Specifies the JDK version to install and build with.  Defaults to 21.                                                                                                                                                                                                      |
| `JDK`                   | `false `  | `string `  | `temurin `      | Specifies the JDK to use, defaults to `temurin`.                                                                                                                                                                                                                           |
| `MAIN_BRANCH`           | `false `  | `string `  | `main `         | Specifies the main branch for the repository.  Used in determining whether to publish `SNAPSHOT`s in  conjunction with the `PUBLISH_SNAPSHOTS` parameter.                                                                                                                  |
| `MAVEN_ARGS`            | `false `  | `string `  |                 | Specifies any additional arguments to pass to the Maven invocations.                                                                                                                                                                                                       |
| `MAVEN_BUILD_GOALS`     | `false `  | `string `  | `install `      | Specifies the Maven goal(s) to use when building the project.  Defaults to `install`.                                                                                                                                                                                      |
| `MAVEN_DEBUG_ARGS`      | `false `  | `string `  |                 | Specifies any additional arguments to pass to the Maven invocations when the workflow is run in  debug mode.                                                                                                                                                               |
| `MAVEN_DEPLOY_GOALS`    | `false `  | `string `  | `deploy `       | Specifies the Maven goal(s) to use when deploying the project, assuming `PUBLISH_SNAPSHOTS` was set to `true` and we're on the configured `MAIN_BRANCH`.  Defaults to `deploy`.                                                                                            |
| `MAVEN_REPOSITORY_ID`   | `false `  | `string `  | `sonatype-oss ` | Specifies the ID of the repository to which `SNAPSHOT`s and Releases are published, this **MUST** match  the ID of a repository defined in the `pom.xml` for the project in order for credentials to be correctly  configured.                                             |
| `PUBLISH_SNAPSHOTS`     | `false `  | `boolean ` | `true `         | Specifies whether Maven `SNAPSHOT`s are published from this build.  Note that even when enabled (as is the default) `SNAPSHOT`s are only published when a build occurs on the main branch.  The main branch  can be separately configured via the `MAIN_BRANCH` parameter. |
| `RELEASE_FILES`         | `false `  | `string `  | `null `         | Specifies the release files that should be attached to the GitHub release.  For example a  downloadable package that is generated from the repository.  Regardless of this value we  will always attach the SBOMs to the release.                                          |
| `USES_DOCKERHUB_IMAGES` | `false `  | `boolean ` | `false `        | Specifies whether this build needs to pull images from DockerHub.                                                                                                                                                                                                          |

