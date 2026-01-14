#!/usr/bin/env python3
"""
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


class MyParser(argparse.ArgumentParser):

    def error(self, message):
        sys.stderr.write('error: %s\n' % message)
        self.print_help()
        sys.exit(2)


def parse_args() -> argparse.Namespace:
    epilog = """
Example usages:\n

  1. Output to stdout:
  python image-push.py -r Quay.io -s success -t templates/trivy-scan-teams-notification -n app -i <Image URL> -w <GitHub Workflow URL>

  2. Output to file:
  python image-push.py teams-notification-payload.json -r Quay.io -s success -t templates/trivy-scan-teams-notification -n app -i <Image URL> -w <GitHub Workflow URL>
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
        "output", nargs="?", default="-",
        help="Path to output JSON to file, or '-' for stdout (defaults to stdout)")

    required_group = p.add_argument_group("Required Arguments")
    required_group.add_argument(
        "-r", "--registry", required=True, choices=["Quay.io", "ECR"],
        help="Name of the container registry to which the image was pushed, either 'Quay.io' or 'ECR'")
    required_group.add_argument(
        "-t", "--template", required=True,
        help="Path to JSON template into which rows will be injected")
    required_group.add_argument(
        "-n", "--app-name", required=True,
        help="Name of the application that the Trivy report was generated for")
    required_group.add_argument(
        "-i", "--image-url", required=True,
        help="URL of the container image that was pushed to a remote registry")
    required_group.add_argument(
        "-w", "--workflow-url", required=True,
        help="URL to the GitHub workflow run that produced the Trivy report")
    
    optional_group = p.add_argument_group("Optional Arguments")
    optional_group.add_argument(
        "-s", "--status", required=True, choices=["success", "failure"], default="success",
        help="Status of the image push operation to report, either 'success' or 'failure' (defaults to 'success')")

    other_group = p.add_argument_group("Other Arguments")
    other_group.add_argument(
        "-h", "--help", action="help",
        help="Show this help message and exit")
    
    return p.parse_args()


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

    # Load the template.
    template_path = Path(args.template)
    if not template_path.exists():
        raise SystemExit(f"Template file not found: {template_path}")
    with template_path.open("r", encoding="utf-8") as fh:
        template = json.load(fh)

    # Add the app name to the Application fact
    header_text = find_object_by_id(template, "header-text")
    if header_text is None:
        raise SystemExit("Template does not contain an object with id='header-text'")
    status_message = "Succeeded" if args.status == "success" else "Failed"
    header_text["text"] = "Image Push to %s %s" % (args.registry, status_message)
    header_text["color"] = "Good" if args.status == "success" else "Attention"

    # Add the app name to the Application fact
    app_name = find_object_by_id(template, "app-name")
    if app_name is None:
        raise SystemExit("Template does not contain an object with id='app-name'")
    app_name["value"] = args.app_name

    # Add the image URL to the Image URL fact
    image_url = find_object_by_id(template, "image-url")
    if image_url is None:
        raise SystemExit("Template does not contain an object with id='image-url'")
    image_url["value"] = args.image_url

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
