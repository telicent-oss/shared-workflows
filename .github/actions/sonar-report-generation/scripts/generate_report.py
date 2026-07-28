#!/usr/bin/env python3
"""
Query the SonarQube Web API for a project and render a PDF code health report.

Optionally writes a JSON summary (consumed by the composite action to set step
outputs) and a Markdown summary suitable for a GitHub job summary.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from pdf_report import (
    build_report,
    fmt_effort,
    fmt_int,
    fmt_pct,
    fmt_rating,
)
from sonar_api import ProjectHealth, SonarClient, SonarError, collect_health


class ArgParser(argparse.ArgumentParser):

    def error(self, message):
        sys.stderr.write(f"error: {message}\n")
        self.print_help()
        sys.exit(2)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    epilog = """
Example usages:

  1. Report on the default branch:
  python generate_report.py -H https://sonar.example.com -k my-project -o report.pdf

  2. Report on a specific branch, with a 180 day trend and a job summary:
  python generate_report.py -H https://sonar.example.com -k my-project -b main \\
      -o report.pdf --history-days 180 --markdown-summary summary.md
"""

    parser = ArgParser(
        description="Generate a PDF code health report from the SonarQube API.",
        formatter_class=lambda prog: argparse.RawDescriptionHelpFormatter(
            prog, max_help_position=40),
        epilog=epilog,
    )
    parser.add_argument("-H", "--host-url", required=True,
                        help="Base URL of the SonarQube or SonarCloud server.")
    parser.add_argument("-k", "--project-key", required=True,
                        help="Key of the project to report on.")
    parser.add_argument("-t", "--token", default=None,
                        help="SonarQube token. Defaults to $SONAR_TOKEN.")
    parser.add_argument("-b", "--branch", default=None,
                        help="Branch to report on. Defaults to the project's main branch.")
    parser.add_argument("-V", "--project-version", default=None,
                        help="Version of the code that was analysed, shown on the report. "
                             "Takes precedence over the version SonarQube recorded, which "
                             "is useful where the token cannot read the analysis history.")
    parser.add_argument("-o", "--output", default=None,
                        help="Path to write the PDF to. Defaults to an auto generated name.")
    parser.add_argument("--output-dir", default=".",
                        help="Directory for the auto generated file name. Defaults to '.'.")
    parser.add_argument("--history-days", type=int, default=90,
                        help="Days of history to include in the trend charts. Defaults to 90.")
    parser.add_argument("--top", type=int, default=10,
                        help="Number of rules and files to list. Defaults to 10.")
    parser.add_argument("--timeout", type=int, default=30,
                        help="Per request timeout in seconds. Defaults to 30.")
    parser.add_argument("--insecure", action="store_true",
                        help="Skip TLS verification, for servers with private CAs.")
    parser.add_argument("--summary-json", default=None,
                        help="Path to write a machine readable summary to.")
    parser.add_argument("--markdown-summary", default=None,
                        help="Path to write a Markdown summary to.")
    return parser.parse_args(argv)


def default_output_path(directory: str, health_key: str, branch: str | None) -> Path:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", health_key).strip("-") or "project"
    if branch:
        branch_slug = re.sub(r"[^A-Za-z0-9._-]+", "-", branch).strip("-")
        slug = f"{slug}-{branch_slug}"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Path(directory) / f"sonar-code-health-{slug}-{stamp}.pdf"


def build_summary(health: ProjectHealth, report_path: Path) -> dict:
    failing = [c.metric for c in health.conditions if c.status.upper() == "ERROR"]
    return {
        "projectKey": health.key,
        "projectName": health.name,
        "branch": health.branch,
        "generatedAt": health.generated_at.isoformat(),
        "lastAnalysisAt": health.analysed_at.isoformat() if health.analysed_at else None,
        "analysedVersion": health.last_version,
        "qualityGateStatus": health.quality_gate_status,
        "failingConditions": failing,
        "reportPath": str(report_path),
        "metrics": {
            "bugs": health.number("bugs"),
            "vulnerabilities": health.number("vulnerabilities"),
            "codeSmells": health.number("code_smells"),
            "securityHotspots": health.number("security_hotspots"),
            "openIssues": health.total_issues,
            "coverage": health.number("coverage"),
            "duplicatedLinesDensity": health.number("duplicated_lines_density"),
            "linesOfCode": health.number("ncloc"),
            "technicalDebtMinutes": health.number("sqale_index"),
            "reliabilityRating": fmt_rating(health.number("reliability_rating")),
            "securityRating": fmt_rating(health.number("security_rating")),
            "securityReviewRating": fmt_rating(health.number("security_review_rating")),
            "maintainabilityRating": fmt_rating(health.number("sqale_rating")),
        },
    }


def build_markdown(health: ProjectHealth, report_path: Path) -> str:
    status = (health.quality_gate_status or "NONE").upper()
    badge = {"OK": "✅ Passed", "ERROR": "❌ Failed", "WARN": "⚠️ Warning"}.get(
        status, f"❔ {status}")

    lines = [
        f"## SonarQube code health — {health.name}",
        "",
        f"**Quality gate:** {badge}  ",
        f"**Branch:** `{health.branch or 'default'}`  ",
    ]
    if health.last_version:
        lines.append(f"**Version:** `{health.last_version}`  ")
    lines += [
        f"**Report:** `{report_path.name}`",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Reliability | {fmt_rating(health.number('reliability_rating'))} "
        f"({fmt_int(health.number('bugs'))} bugs) |",
        f"| Security | {fmt_rating(health.number('security_rating'))} "
        f"({fmt_int(health.number('vulnerabilities'))} vulnerabilities) |",
        f"| Maintainability | {fmt_rating(health.number('sqale_rating'))} "
        f"({fmt_int(health.number('code_smells'))} code smells) |",
        f"| Security hotspots | {fmt_int(health.number('security_hotspots'))} |",
        f"| Coverage | {fmt_pct(health.number('coverage'))} |",
        f"| Duplication | {fmt_pct(health.number('duplicated_lines_density'))} |",
        f"| Technical debt | {fmt_effort(health.number('sqale_index'))} |",
        f"| Lines of code | {fmt_int(health.number('ncloc'))} |",
    ]

    failing = [c for c in health.conditions if c.status.upper() == "ERROR"]
    if failing:
        lines += ["", "### Failing quality gate conditions", ""]
        lines += [
            f"- `{c.metric}`: actual `{c.actual}`, required "
            f"`{(c.comparator or '').lower()} {c.threshold}`"
            for c in failing
        ]

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    token = args.token or os.environ.get("SONAR_TOKEN", "")
    if not token:
        print("::error::A SonarQube token must be given via --token or $SONAR_TOKEN")
        return 2

    client = SonarClient(
        host_url=args.host_url,
        token=token,
        timeout=args.timeout,
        verify_tls=not args.insecure,
    )

    try:
        health = collect_health(
            client,
            project_key=args.project_key,
            branch=args.branch,
            history_days=args.history_days,
            top_n=args.top,
        )
    except SonarError as exc:
        print(f"::error::Could not read project '{args.project_key}' from SonarQube: {exc}")
        return 1
    except requests.RequestException as exc:
        print(f"::error::Could not reach SonarQube at {args.host_url}: {exc}")
        return 1

    if args.project_version:
        health.last_version = args.project_version

    report_path = Path(args.output) if args.output else default_output_path(
        args.output_dir, health.key, health.branch)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    build_report(health, str(report_path))
    print(f"Wrote code health report to {report_path}")

    if args.summary_json:
        summary_path = Path(args.summary_json)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(build_summary(health, report_path), indent=2), encoding="utf-8")

    if args.markdown_summary:
        markdown_path = Path(args.markdown_summary)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(build_markdown(health, report_path), encoding="utf-8")

    return 0


if __name__ == "__main__":
    sys.exit(main())
