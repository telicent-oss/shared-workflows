# Helm Metadata Updater GitHub Action

A GitHub Action for checking that metadata in the `values.yaml` file of a Helm
chart is present and valid. This action uses the [readme-generator-for-helm][]
NPM package.

## Description

When invoked, the `metadata-updater.py` script will discover all Helm charts in
a repository (in `./charts` by defaults, though this can be configured). and
for each it will ensure that the required files exist and that the metadata for
each value in the `values.yaml` file is present and valid. For each valid chart,
a `values.schema.json` file will be produced.

If one or more charts fail validation, or if after a successful validation there
the Git detects differences to the files maintained by the metadata updater, the
Action will fail. See [Troubleshooting][] below for tips should you encounter
failures.

## Required Files

Each chart must have the following files, otherwise the metadata updater will
report failure for the chart.

* `readme.config`: A sample [`readme.config`][] file is available in this repository.
* `values.yaml`: Unique for each chart.
* `README.md`: Not technically required, and if absent a minimal README will be
created with the required headings. If you wish to use a pre-existing README,
the `## Parameters` heading must exist.

## Usage

### GitHub Actions Workflow

The action should be invoked through a workflow. A copy of the [metadata-updater.yaml][] workflow can be found in this repository.

While in most cases the workflow can be used without change, it is possible to
configure the path to Helm charts, and charts to specifically include or exclude
when running the metadata updater. See [Inputs][] for more information.

```bash
jobs:
  metadata-updater:
    name: Check Helm chart metadata is up to date
    runs-on: ubuntu-latest
    steps:
      - name: Run metadata updater
        uses: telicent-oss/shared-workflows/.github/actions/helm-metadata-updater@main
        with:
          charts-path: test-charts
          include-charts: test-charts/chart-2
```

### Local Usage

> **Note:** After copying [metadata-updater.sh][], it's best practice to commit
> it to the repository.

Before committing changes to the `values.yaml` file, the metadata updater should
be run locally. To run with the script included in this action, you can copy
the [metadata-updater.sh][] wrapper script from this repository and run it
locally.

```shell
# Copy the wrapper script. Run this command from the root of the repository.
SCRIPT_PATH=".dev/metadata-updater.sh"
SCRIPT_URL="https://raw.githubusercontent.com/telicent-oss/shared-workflows/refs/heads/main/.github/actions/helm-metadata-updater/files/metadata-updater.sh"
curl -L -o "$SCRIPT_PATH" "$SCRIPT_URL"

# Run the wrapper script locally.
./.dev/metadata-updater.sh
```

If required, arguments to configure the path to Helm charts, and charts to
specifically include or exclude when running the metadata updater can be added
to the command to run the wrapper script locally. See [Inputs][] for more information.

```bash
./.dev/metadata-updater.sh --path test-charts --include test-charts/chart-2
```

## Inputs

The following table provides the following -

* **Workflow Input:** The names of the workflow inputs that can be used when
running this action through a GitHub Action
* **Script Argument:** The names of the script arguments that can be used when
running the metadata updater locally.

<!-- markdownlint-disable MD060 -->
| Workflow Input   | Script Argument   | Default  | Description |
| ---------------- | ----------------- | -------- | ----------- |
| `charts-path`    | `--path`, `-p`    | `charts` | The path to the Helm charts to inspect. |
| `include-charts` | `--include`, `-i` |          | A space separated list of charts to include in the check. Paths should be relative to the root of the repository. |
| `exclude-charts` | `--exclude`, `-e` |          | A space separated list of charts to exclude from the check. Paths should be relative to the root of the repository. Ignored if `include-charts`/`--include` is provided. |
<!-- markdownlint-enable MD060 -->

## Troubleshooting

### Invalid Metadata

If the action fails due to invalid metadata, such as a missing metadata for key
or where metadata has been provided for non existing key, then this indicates
that the `values.yaml` file has not been updated.

The logs will always output the results of the metadata updater run, so please
check for specific errors and ensure that your `values.yaml` file is up to date.

* See the [example `values.yaml`][] file for an example of how to add metadata.
* See the [readme-generator-for-helm -- values.yaml Metadata][] for a
description of the supported metadata tags. Note that the
[`readme.config`][] file in this repository configures the package to use
`@key` as opposed to `@param`.

### Uncommitted Changes

If the action fails due to uncommitted changes, the following message will be
shown.

> README files and schemas are out of sync with values.yaml

This means that the metadata in `values.yaml` is valid, however the `README.md` and `values.schema.json` files have not been updated.

To resolve this error, run the metadata updater locally and commit the changes.

## Contributing

Following any contribution it is required that tests be updated.

### Doctest

Classes and methods within the `metadata-updater.py` script include `doctest`
examples. After any contribution these tests should updated as necessary and run
to ensure that they are successful.

Note that these tests are only expected to succeed using the command below, and
are likely to fail when executed using the [metadata-updater.sh][] wrapper script from any repository.

```shell
$ python .github/actions/helm-metadata-updater/metadata-updater.py --test
[SUCCESS] 28 doctest(s) run, all passed.
```

### Unit Tests

The metadata updater has a companion test script containing unit tests. After
any contribution these tests should be updated as necessary and rn to ensure
that they are successful.

```bash
$ cd cd .github/actions
$ python -m unittest helm-metadata-updater/test_metadata_updater.py
..........................
----------------------------------------------------------------------
Ran 26 tests in 0.021s

OK
```

<!-- Links to sections of this document -->
[Inputs]: #inputs
[Troubleshooting]: #troubleshooting

<!-- Links to files in this repository -->
[example `values.yaml`]: files/example-values.yaml
[metadata-updater.sh]: files/metadata-updater.sh
[metadata-updater.yaml]: files/metadata-updater.yaml
[`readme.config`]: files/readme.config

<!-- External links -->
[readme-generator-for-helm]: https://github.com/bitnami/readme-generator-for-helm
[readme-generator-for-helm -- values.yaml Metadata]: https://github.com/bitnami/readme-generator-for-helm#valuesyaml-metadata
