# Release Candidate Version Action

This GitHub action works out the version for a development build of a
repository that is released with [release-please][1]:

```text
<next version>-RC.<commits since the last release>
```

For example, `1.8.0-RC.12` is the twelfth commit since the last release, built
while `1.8.0` is the next version to be released.

[Semantic versioning][2] orders `RC.9` below `RC.10`, and every release
candidate below the release itself, so the newest build of a version is always
its highest. A suffix made from the commit SHA has no such order, which
matters to anything that follows the builds by version, such as a chart
subscription.

## How the version is worked out

1. The last released version is the package's entry in the release-please
   manifest at the commit being built.
2. The next version is the one an open release-please pull request into the
   branch being built proposes for the package, read from the manifest on that
   pull request's branch. When there is no such pull request, it is the next
   patch of the last released version.
3. The build number is the number of commits between the last release's tag
   and the commit being built.

### Before the first release

When no release can be found, the version is `0.0.0-RC.<commits>`, numbered by
every commit behind the one being built. It ranks below any release, so the
builds are outranked as soon as the repository has one. No release can be
found when:

- there is no manifest file;
- the manifest has no version for the package; or
- the manifest's version has no tag.

The step then adds a warning to the job summary, and a warning annotation to
the run, naming the manifest, version and tag prefix it looked for. A wrong
`manifest-file`, `package-path` or `tag-prefix` in a repository that has
released looks the same, and the warning is how to tell.

Only a "not found" answer from GitHub is treated this way. Any other API
error fails the step, and no version is written.

Everything is read through the GitHub API, so the action needs no checkout
and no language tooling. It is the same for a Node.js, Python or any other
repository that release-please manages with a manifest.

## Requirements

- The repository is released with release-please, using a manifest file.
- Each released version has a tag, named `<tag-prefix><version>`.
- The job has these permissions:

  ```yaml
  permissions:
    contents: read
    pull-requests: read
  ```

## Inputs and Outputs

### Inputs

<!-- markdownlint-disable MD060 -->
| Input         | Required | Default                                | Description |
| ------------- | -------- | -------------------------------------- | ----------- |
| manifest-file | false    | `.github/release-please-manifest.json` | Path to the release-please manifest file, relative to the repository root. |
| package-path  | false    | `.`                                    | The package's key in the release-please manifest. |
| tag-prefix    | false    | `v`                                    | What precedes the version in the package's release tags. A package released with its component in the tag needs it here, for example `my-component-v`. |
| github-token  | false    | `github.token`                         | Token used to read the repository's contents and pull requests. |
<!-- markdownlint-enable MD060 -->

### Outputs

| Output       | Description                                                       |
| ------------ | ----------------------------------------------------------------- |
| version      | The release candidate version, for example `1.8.0-RC.12`.         |
| next-version | The version the build is a candidate of, for example `1.8.0`. `0.0.0` before the first release. |

## Usage

```yaml
jobs:
  prepare:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: read
    outputs:
      version: ${{ steps.release-candidate.outputs.version }}
    steps:
      - name: Work out the release candidate version
        id: release-candidate
        uses: telicent-oss/shared-workflows/.github/actions/release-candidate-version@main
```

A later job can then give the version to the chart it publishes:

```yaml
      - name: Package and push Helm chart
        uses: telicent-oss/shared-workflows/.github/actions/push-helm-chart@main
        with:
          version: ${{ needs.prepare.outputs.version }}
```

[1]: https://github.com/googleapis/release-please
[2]: https://semver.org/#spec-item-11
