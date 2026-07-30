#!/usr/bin/env python3
"""
Minimal SonarQube / SonarCloud Web API client used to gather the data that
makes up a code health report.

Only the read-only endpoints needed by the report are implemented. Every call
degrades gracefully where an endpoint or metric is unavailable on the target
server, as the available metrics and facets vary between SonarQube versions.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urljoin

import requests

# Metrics we would like to report on. Anything the server does not know about
# is dropped before the measures call is made, see SonarClient.available_metrics.
WANTED_METRICS = [
    # Quality gate
    "alert_status",
    # Reliability
    "bugs", "reliability_rating", "reliability_remediation_effort",
    # Security
    "vulnerabilities", "security_rating", "security_remediation_effort",
    "security_hotspots", "security_hotspots_reviewed", "security_review_rating",
    # Maintainability
    "code_smells", "sqale_rating", "sqale_index", "sqale_debt_ratio",
    # Tests
    "coverage", "line_coverage", "branch_coverage", "tests", "test_failures",
    "test_errors", "skipped_tests", "test_success_density",
    # Duplication
    "duplicated_lines_density", "duplicated_blocks", "duplicated_lines",
    # Size and complexity
    "ncloc", "lines", "files", "functions", "classes", "statements",
    "comment_lines_density", "complexity", "cognitive_complexity",
    # New code
    "new_bugs", "new_vulnerabilities", "new_code_smells", "new_security_hotspots",
    "new_coverage", "new_duplicated_lines_density", "new_lines",
    "new_technical_debt", "new_maintainability_rating", "new_reliability_rating",
    "new_security_rating",
]

# Metrics plotted on the trend charts, in preference order.
TREND_METRICS = [
    "bugs", "vulnerabilities", "code_smells", "security_hotspots",
    "coverage", "duplicated_lines_density", "ncloc", "sqale_index",
]

NEW_CODE_METRICS = {m for m in WANTED_METRICS if m.startswith("new_")}


class SonarError(RuntimeError):
    """Raised when the SonarQube API cannot satisfy a request."""


@dataclass
class Measure:
    """A single metric value for a component."""

    metric: str
    value: str | None = None
    best_value: bool | None = None

    def as_float(self) -> float | None:
        try:
            return float(self.value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None


@dataclass
class Condition:
    """A single quality gate condition and whether the project meets it."""

    metric: str
    status: str
    comparator: str | None = None
    threshold: str | None = None
    actual: str | None = None


@dataclass
class ProjectHealth:
    """Everything the report needs about a single project."""

    key: str
    name: str
    branch: str | None = None
    server_version: str | None = None
    analysed_at: datetime | None = None
    last_version: str | None = None
    quality_gate_status: str = "NONE"
    conditions: list[Condition] = field(default_factory=list)
    measures: dict[str, Measure] = field(default_factory=dict)
    severities: dict[str, int] = field(default_factory=dict)
    issue_types: dict[str, int] = field(default_factory=dict)
    top_rules: list[tuple[str, int]] = field(default_factory=list)
    top_files: list[tuple[str, int]] = field(default_factory=list)
    total_issues: int = 0
    history: dict[str, list[tuple[datetime, float]]] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def value(self, metric: str) -> str | None:
        measure = self.measures.get(metric)
        return measure.value if measure else None

    def number(self, metric: str) -> float | None:
        measure = self.measures.get(metric)
        return measure.as_float() if measure else None


class SonarClient:
    """A thin wrapper over the subset of the SonarQube Web API that we need."""

    def __init__(
        self,
        host_url: str,
        token: str,
        timeout: int = 30,
        verify_tls: bool = True,
    ) -> None:
        self.host_url = host_url.rstrip("/")
        self.timeout = timeout
        self._token = token
        self._session = requests.Session()
        self._session.verify = verify_tls
        # SonarQube 10+ accepts bearer tokens, older servers only understand the
        # token-as-basic-auth-username form. Start with bearer, fall back once.
        self._auth_header = f"Bearer {token}"
        self._fallback_auth_available = True

    def _basic_auth_header(self) -> str:
        encoded = base64.b64encode(f"{self._token}:".encode()).decode()
        return f"Basic {encoded}"

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET a Web API path, returning the decoded JSON body."""
        url = urljoin(f"{self.host_url}/", path.lstrip("/"))
        clean = {k: v for k, v in (params or {}).items() if v not in (None, "")}

        response = self._session.get(
            url,
            params=clean,
            headers={"Authorization": self._auth_header, "Accept": "application/json"},
            timeout=self.timeout,
        )

        if response.status_code == 401 and self._fallback_auth_available:
            self._fallback_auth_available = False
            self._auth_header = self._basic_auth_header()
            return self.get(path, params)

        if not response.ok:
            raise SonarError(
                f"{response.status_code} from {path}: {_error_message(response)}")

        try:
            return response.json()
        except ValueError as exc:
            raise SonarError(f"Non JSON response from {path}") from exc

    def try_get(self, path: str, params: dict[str, Any] | None = None,
                quiet: bool = False) -> dict[str, Any]:
        """As get(), but returns an empty dict instead of raising."""
        try:
            return self.get(path, params)
        except (SonarError, requests.RequestException) as exc:
            if not quiet:
                print(f"::warning::Could not read {path} from SonarQube: {exc}")
            return {}

    def server_version(self) -> str | None:
        # /api/server/version returns text/plain, so it is fetched directly.
        try:
            response = self._session.get(
                f"{self.host_url}/api/server/version",
                headers={"Authorization": self._auth_header},
                timeout=self.timeout,
            )
            return response.text.strip() if response.ok else None
        except requests.RequestException:
            return None

    def available_metrics(self) -> set[str]:
        """All metric keys the server knows about."""
        keys: set[str] = set()
        page = 1
        while True:
            data = self.try_get("api/metrics/search", {"ps": 500, "p": page})
            metrics = data.get("metrics", [])
            keys.update(m["key"] for m in metrics if "key" in m)
            total = int(data.get("total", 0))
            if not metrics or len(keys) >= total or page > 20:
                break
            page += 1
        return keys

    def component(self, project_key: str, branch: str | None) -> dict[str, Any]:
        """Project metadata, used for the report's title.

        `api/components/show` needs Browse on the component, which some tokens
        are not granted even though they can read measures, so fall back to a
        metadata only measures call before treating the project as missing.
        """
        data = self.try_get(
            "api/components/show", {"component": project_key, "branch": branch},
            quiet=True)
        component = data.get("component") or {}
        if component:
            return component

        data = self.get(
            "api/measures/component",
            {"component": project_key, "branch": branch, "metricKeys": "ncloc"},
        )
        return data.get("component") or {}

    def measures(
        self, project_key: str, branch: str | None, metrics: list[str]
    ) -> dict[str, Measure]:
        """Fetch measures in batches, as servers cap the metric keys per call."""
        results: dict[str, Measure] = {}
        for batch in _chunks(metrics, 50):
            data = self.try_get(
                "api/measures/component",
                {
                    "component": project_key,
                    "branch": branch,
                    "metricKeys": ",".join(batch),
                    "additionalFields": "period",
                },
            )
            for raw in data.get("component", {}).get("measures", []):
                metric = raw.get("metric")
                if not metric:
                    continue
                # New code metrics carry their value on the period rather than
                # on the measure itself.
                value = raw.get("value")
                if value is None:
                    period = raw.get("period") or (raw.get("periods") or [{}])[0]
                    value = period.get("value")
                results[metric] = Measure(
                    metric=metric, value=value, best_value=raw.get("bestValue"))
        return results

    def quality_gate(
        self, project_key: str, branch: str | None
    ) -> tuple[str, list[Condition]]:
        data = self.try_get(
            "api/qualitygates/project_status",
            {"projectKey": project_key, "branch": branch},
        )
        status = data.get("projectStatus", {})
        conditions = [
            Condition(
                metric=c.get("metricKey", "unknown"),
                status=c.get("status", "UNKNOWN"),
                comparator=c.get("comparator"),
                threshold=c.get("errorThreshold"),
                actual=c.get("actualValue"),
            )
            for c in status.get("conditions", [])
        ]
        return status.get("status", "NONE"), conditions

    def issue_facets(
        self, project_key: str, branch: str | None
    ) -> tuple[int, dict[str, dict[str, int]]]:
        """Open issue counts broken down by severity, type, rule and file."""
        params = {
            "components": project_key,
            "branch": branch,
            "resolved": "false",
            "ps": 1,
            "facets": "severities,types,rules,files",
        }
        # `components` replaced `componentKeys` in SonarQube 10.4, so a failure
        # here is an expected compatibility probe rather than something to warn
        # about; only the retry against older servers is reported.
        data = self.try_get("api/issues/search", params, quiet=True)
        if not data:
            params.pop("components")
            params["componentKeys"] = project_key
            data = self.try_get("api/issues/search", params)

        facets: dict[str, dict[str, int]] = {}
        for facet in data.get("facets", []):
            name = facet.get("property")
            if not name:
                continue
            facets[name] = {
                v.get("val", ""): int(v.get("count", 0))
                for v in facet.get("values", [])
                if v.get("count")
            }
        return int(data.get("total", 0)), facets

    def rule_names(self, rule_keys: list[str]) -> dict[str, str]:
        """Map rule keys to their human readable names.

        Rules are looked up one at a time because the search endpoint filters
        on a single `rule_key` only, and silently ignores an unknown parameter
        rather than reporting an error.
        """
        names: dict[str, str] = {}
        for key in rule_keys:
            data = self.try_get("api/rules/show", {"key": key})
            name = (data.get("rule") or {}).get("name")
            if name:
                names[key] = name
        return names

    def last_analysis(
        self, project_key: str, branch: str | None
    ) -> tuple[datetime | None, str | None]:
        data = self.try_get(
            "api/project_analyses/search",
            {"project": project_key, "branch": branch, "ps": 1},
        )
        analyses = data.get("analyses", [])
        if not analyses:
            return None, None
        analysis = analyses[0]
        return _parse_date(analysis.get("date")), analysis.get("projectVersion")

    def history(
        self,
        project_key: str,
        branch: str | None,
        metrics: list[str],
        days: int,
    ) -> dict[str, list[tuple[datetime, float]]]:
        """Historic measure values, oldest first, for the last `days` days."""
        if not metrics or days <= 0:
            return {}

        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        series: dict[str, list[tuple[datetime, float]]] = {}
        for batch in _chunks(metrics, 10):
            data = self.try_get(
                "api/measures/search_history",
                {
                    "component": project_key,
                    "branch": branch,
                    "metrics": ",".join(batch),
                    "from": since,
                    "ps": 1000,
                },
            )
            for measure in data.get("measures", []):
                metric = measure.get("metric")
                if not metric:
                    continue
                points = []
                for entry in measure.get("history", []):
                    date = _parse_date(entry.get("date"))
                    try:
                        value = float(entry.get("value"))
                    except (TypeError, ValueError):
                        continue
                    if date:
                        points.append((date, value))
                if points:
                    series[metric] = sorted(points, key=lambda p: p[0])
        return series


def collect_health(
    client: SonarClient,
    project_key: str,
    branch: str | None,
    history_days: int,
    top_n: int = 10,
) -> ProjectHealth:
    """Gather everything the report needs in one pass over the API."""
    component = client.component(project_key, branch)
    health = ProjectHealth(
        key=project_key,
        name=component.get("name") or project_key,
        branch=branch,
        server_version=client.server_version(),
    )

    known = client.available_metrics()
    metrics = [m for m in WANTED_METRICS if not known or m in known]
    health.measures = client.measures(project_key, branch, metrics)

    health.quality_gate_status, health.conditions = client.quality_gate(project_key, branch)
    if health.quality_gate_status == "NONE":
        health.quality_gate_status = health.value("alert_status") or "NONE"

    health.analysed_at, health.last_version = client.last_analysis(project_key, branch)

    health.total_issues, facets = client.issue_facets(project_key, branch)
    health.severities = facets.get("severities", {})
    health.issue_types = facets.get("types", {})

    rules = sorted(facets.get("rules", {}).items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    rule_names = client.rule_names([key for key, _ in rules])
    health.top_rules = [(rule_names.get(key, key), count) for key, count in rules]

    files = sorted(facets.get("files", {}).items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    health.top_files = [(component_path(key, project_key), count) for key, count in files]

    trend_metrics = [m for m in TREND_METRICS if not known or m in known]
    health.history = client.history(project_key, branch, trend_metrics, history_days)

    return health


def component_path(component_key: str, project_key: str) -> str:
    """The repository relative path encoded in a SonarQube component key.

    File keys are of the form `<project key>:<path>`, so the path can be
    recovered without asking the server about each file in turn.
    """
    prefix = f"{project_key}:"
    if component_key.startswith(prefix):
        return component_key[len(prefix):] or component_key
    _, separator, tail = component_key.rpartition(":")
    return tail if separator and tail else component_key


def _chunks(items: list[str], size: int):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    # SonarQube returns e.g. 2024-05-01T12:34:56+0100 which fromisoformat only
    # accepts once the offset is colon separated.
    text = value.strip()
    if len(text) > 5 and (text[-5] in "+-") and text[-3] != ":":
        text = f"{text[:-2]}:{text[-2:]}"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip()[:200] or response.reason
    errors = payload.get("errors")
    if errors:
        return "; ".join(e.get("msg", "") for e in errors)
    return response.text.strip()[:200] or response.reason
