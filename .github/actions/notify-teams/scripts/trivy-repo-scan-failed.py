#!/usr/bin/env python3
"""Parse a Trivy JSON report and inject CVE rows into an Adaptive Card template.

This script extracts the following fields from Results[0].Vulnerabilities[*]:
- VulnerabilityID -> Vulnerability ID
- Severity -> Severity
- Status -> Status
- Title -> Title

It filters vulnerabilities to include only those where `Severity` is `HIGH` or `CRITICAL`.

The extracted rows are formatted as Adaptive Card table rows and injected into the
JSON template by locating the object with `id == 'cve-table'` and setting its
`rows` property.

Usage:
    python cve-table.py [-h] -t TEMPLATE [ -o OUTPUT-FILE ] [input-file]
    cat report.json | python cve-table.py -t .github/workflows/templates/trivy-scan-teams-notification.json

The -t/--template argument is required and must point to a JSON file containing an
object with id `cve-table`. Output is printed to stdout by default or written to
the file given output positional argument.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


class MyParser(argparse.ArgumentParser):

    def error(self, message):
        sys.stderr.write('error: %s\n' % message)
        self.print_help()
        sys.exit(2)

    def format_help(self, groups=None):
        formatter = self._get_formatter()

        # Usage
        formatter.add_usage(self.usage, self._actions,
                            self._mutually_exclusive_groups)

        # Description
        formatter.add_text(self.description)

        if groups is None:
            groups = self._action_groups

        # Positionals, optionals and user-defined groups
        for action_group in groups:
            formatter.start_section(action_group.title)
            formatter.add_text(action_group.description)
            formatter.add_arguments(action_group._group_actions)
            formatter.end_section()

        # Epilog
        formatter.add_text(self.epilog)

        # Determine help from format above
        return formatter.format_help()


def parse_args() -> argparse.Namespace:
    epilog = """
Example usages:\n

  1. Input from stdin, output to stdout:
  python cve-table.py -t templates/trivy-scan-teams-notification -n app -w <GitHub Workflow URL>

  2. Input from file, output to stdout:
  python cve-table.py repo-scan-trivy-report.json -t templates/trivy-scan-teams-notification -n app -w <GitHub Workflow URL>

  3. Input from stdin, output to file:
  python cve-table.py - teams-notification-payload.json -t templates/trivy-scan-teams-notification -n app -w <GitHub Workflow URL>

  4. Input from file, output to file:
  python cve-table.py repo-scan-trivy-report.json teams-notification-payload.json -t templates/trivy-scan-teams-notification -n app -w <GitHub Workflow URL>
"""

    p = MyParser(
        description=(
            "Parse Trivy JSON and serialize selected vulnerabilities into table"
            " rows JSON for injection into payload for MS Teams notification."),
        formatter_class=lambda prog: argparse.RawDescriptionHelpFormatter(prog, max_help_position=40),
        add_help=False,
        epilog=epilog)
    
    positional_group = p.add_argument_group("Positional Arguments")
    positional_group.add_argument(
        "input", nargs="?", default="-",
        help="Path to Trivy JSON report file, or '-' for stdin (defaults to stdin)")
    positional_group.add_argument(
        "output", nargs="?", default="-",
        help="Path to output JSON to file, or '-' for stdout (defaults to stdout)")

    required_group = p.add_argument_group("Required Arguments")
    required_group.add_argument(
        "-t", "--template", required=True,
        help="Path to JSON template into which rows will be injected")
    required_group.add_argument(
        "-n", "--app-name", required=True,
        help="Name of the application that the Trivy report was generated for")
    required_group.add_argument(
        "-w", "--workflow-url", required=True,
        help="URL to the GitHub workflow run that produced the Trivy report")

    other_group = p.add_argument_group("Other Arguments")
    other_group.add_argument(
        "-h", "--help", action="help",
        help="Show this help message and exit")
    
    return p.parse_args()


def make_cell(text: str) -> Dict[str, Any]:
    return {
        "type": "TableCell",
        "items": [
            {
                "type": "TextBlock",
                "text": text,
                "color": "attention" if text in {"HIGH", "CRITICAL"} else "default",
                "weight": "bolder" if text in {"HIGH", "CRITICAL"} else "default",
                "wrap": True,
            }
        ],
    }


def make_row(cell_texts: List[str]) -> Dict[str, Any]:
    return {"type": "TableRow", "cells": [make_cell(t) for t in cell_texts]}


def header_row() -> Dict[str, Any]:
    return make_row(["Package", "ID", "Severity", "Installed Version", "Fixed Version"])


def extract_rows(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = [header_row()]

    results = data.get("Results") or []
    if not isinstance(results, list) or not results:
        return rows

    vulns = results[0].get("Vulnerabilities") or []
    if not isinstance(vulns, list):
        return rows

    for v in vulns:
        package = str(v.get("PkgName", ""))
        vuln_id = str(v.get("VulnerabilityID", ""))
        primary_url = str(v.get("PrimaryURL", ""))
        severity = str(v.get("Severity", ""))
        installed_ver = str(v.get("InstalledVersion", ""))
        fixed_ver = str(v.get("FixedVersion", "not-fixed"))

        # Filter where Status is not HIGH or CRITICAL
        if severity not in {"HIGH", "CRITICAL"}:
            continue

        # Add a link to the vulnerability ID, if there is a URL
        vuln_id_link = f"[{vuln_id}]({primary_url})" if primary_url else vuln_id

        rows.append(make_row([("`%s`" % package), vuln_id_link, severity, installed_ver, fixed_ver]))

    return rows


def find_object_by_id(obj: Any, target_id: str) -> Any:
    """Recursively search for an object with the given ID."""
    if isinstance(obj, dict):
        if obj.get("id") == target_id:
            return obj
        for value in obj.values():
            result = find_object_by_id(value, target_id)
            if result is not None:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = find_object_by_id(item, target_id)
            if result is not None:
                return result
    return None


def main() -> None:
    args = parse_args()

    # Load the Trivy report JSON from file or stdin
    if args.input == "-":
        raw = json.load(__import__("sys").stdin)
    else:
        path = Path(args.input)
        if not path.exists():
            raise SystemExit(f"Input file not found: {path}")
        with path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)

    # Extract CVE's from the Trivy report and format as JSON for MS Teams
    # AdaptiveCard table rows
    rows = extract_rows(raw)

    # Load the template and inject rows into the object with ID 'cve-table'
    template_path = Path(args.template)
    if not template_path.exists():
        raise SystemExit(f"Template file not found: {template_path}")
    with template_path.open("r", encoding="utf-8") as fh:
        template = json.load(fh)

    # Add the app name to the sub heading
    app_name = find_object_by_id(template, "app-name")
    if app_name is None:
        raise SystemExit("Template does not contain an object with id='app-name'")
    app_name["text"] = 'Application: %s\n' % args.app_name

    # Add the table of CVE rows to the template
    cve_table = find_object_by_id(template, "cve-table")
    if cve_table is None:
        raise SystemExit("Template does not contain an object with id='cve-table'")
    cve_table["rows"] = rows

    # Add the workflow URL to the open URL action
    open_workflow_action = find_object_by_id(template, "open-workflow-action")
    if open_workflow_action is None:
        raise SystemExit("Template does not contain an object with id='open-workflow-action'")
    open_workflow_action["url"] = args.workflow_url

    serialised = json.dumps(template, ensure_ascii=False, separators=(',', ':'))

    # If args.output is '-' write to stdout; if it's a path write to that file.
    if args.output == "-":
        print(serialised)
    elif args.output:
        out_path = Path(args.output)
        out_path.write_text(serialised, encoding="utf-8")
    else:
        # Fallback to stdout if somehow args.output is empty/null
        print(serialised)


if __name__ == "__main__":
    main()
