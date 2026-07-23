#!/usr/bin/env python3
"""
Renders a ProjectHealth snapshot as a PDF code health report.

Everything is drawn with ReportLab's built in fonts and primitives so that the
action has no system level dependencies beyond pip.
"""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing, Line
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from sonar_api import ProjectHealth

INK = colors.HexColor("#1b2733")
MUTED = colors.HexColor("#64748b")
RULE = colors.HexColor("#dbe2ea")
PANEL = colors.HexColor("#f4f7fa")
ACCENT = colors.HexColor("#2f6fb8")
WHITE = colors.white

RATING_COLOURS = {
    "A": colors.HexColor("#2e9e5b"),
    "B": colors.HexColor("#7fbf3f"),
    "C": colors.HexColor("#e8b21a"),
    "D": colors.HexColor("#ef7d2f"),
    "E": colors.HexColor("#d6304a"),
}

SEVERITY_COLOURS = {
    "BLOCKER": colors.HexColor("#8c1c2b"),
    "CRITICAL": colors.HexColor("#d6304a"),
    "MAJOR": colors.HexColor("#ef7d2f"),
    "MINOR": colors.HexColor("#e8b21a"),
    "INFO": colors.HexColor("#7b93ab"),
    "HIGH": colors.HexColor("#d6304a"),
    "MEDIUM": colors.HexColor("#ef7d2f"),
    "LOW": colors.HexColor("#e8b21a"),
}

SEVERITY_ORDER = ["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO",
                  "HIGH", "MEDIUM", "LOW"]

GATE_COLOURS = {
    "OK": colors.HexColor("#2e9e5b"),
    "PASSED": colors.HexColor("#2e9e5b"),
    "WARN": colors.HexColor("#e8b21a"),
    "ERROR": colors.HexColor("#d6304a"),
    "FAILED": colors.HexColor("#d6304a"),
    "NONE": MUTED,
}

MARGIN = 16 * mm

STYLES = {
    "title": ParagraphStyle(
        "title", fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=INK),
    "subtitle": ParagraphStyle(
        "subtitle", fontName="Helvetica", fontSize=11, leading=15, textColor=MUTED),
    "heading": ParagraphStyle(
        "heading", fontName="Helvetica-Bold", fontSize=12.5, leading=16,
        textColor=INK, spaceBefore=2, spaceAfter=4),
    "body": ParagraphStyle(
        "body", fontName="Helvetica", fontSize=9, leading=12.5, textColor=INK),
    "muted": ParagraphStyle(
        "muted", fontName="Helvetica", fontSize=8, leading=11, textColor=MUTED),
    "cell": ParagraphStyle(
        "cell", fontName="Helvetica", fontSize=8.5, leading=11, textColor=INK),
    "cell-bold": ParagraphStyle(
        "cell-bold", fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=INK),
    "tile-value": ParagraphStyle(
        "tile-value", fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=INK),
    "tile-label": ParagraphStyle(
        "tile-label", fontName="Helvetica", fontSize=7.5, leading=10, textColor=MUTED),
}


# --------------------------------------------------------------------------
# Value formatting
# --------------------------------------------------------------------------

def fmt_int(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{int(round(value)):,}"


def fmt_pct(value: float | None, places: int = 1) -> str:
    if value is None:
        return "-"
    return f"{value:.{places}f}%"


def fmt_rating(value: float | None) -> str:
    if value is None:
        return "-"
    return "ABCDE"[min(max(int(round(value)) - 1, 0), 4)]


def fmt_effort(minutes: float | None) -> str:
    """Format a remediation effort in minutes as SonarQube does (8 hour days)."""
    if minutes is None:
        return "-"
    total = int(round(minutes))
    if total <= 0:
        return "0min"
    days, remainder = divmod(total, 8 * 60)
    hours, mins = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins and not days:
        parts.append(f"{mins}min")
    return " ".join(parts) or "0min"


def fmt_datetime(value: datetime | None) -> str:
    if value is None:
        return "unknown"
    return value.strftime("%d %b %Y %H:%M %Z").strip()


def _hex(colour: colors.Color) -> str:
    """A ``#rrggbb`` string, as ReportLab's inline markup expects."""
    return f"#{colour.hexval()[2:]}"


def _escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else f"{text[:limit - 1]}…"


# --------------------------------------------------------------------------
# Custom flowables
# --------------------------------------------------------------------------

class DistributionBar(Flowable):
    """A single stacked bar showing the relative size of each segment."""

    def __init__(self, segments: Sequence[tuple[str, int, colors.Color]], height: float = 13):
        super().__init__()
        self.segments = [s for s in segments if s[1] > 0]
        self.height = height
        self.width = 0.0

    def wrap(self, available_width: float, available_height: float):
        self.width = available_width
        return self.width, self.height

    def draw(self) -> None:
        total = sum(count for _, count, _ in self.segments)
        if not total:
            self.canv.setFillColor(RULE)
            self.canv.rect(0, 0, self.width, self.height, stroke=0, fill=1)
            return

        x = 0.0
        for index, (_, count, colour) in enumerate(self.segments):
            width = self.width * count / total
            # Absorb rounding into the final segment so the bar is always full.
            if index == len(self.segments) - 1:
                width = self.width - x
            self.canv.setFillColor(colour)
            self.canv.rect(x, 0, width, self.height, stroke=0, fill=1)
            x += width


class HorizontalRule(Flowable):
    """A hairline separator spanning the frame."""

    def __init__(self, colour: colors.Color = RULE, thickness: float = 0.6):
        super().__init__()
        self.colour = colour
        self.thickness = thickness
        self.width = 0.0

    def wrap(self, available_width: float, available_height: float):
        self.width = available_width
        return self.width, self.thickness

    def draw(self) -> None:
        self.canv.setStrokeColor(self.colour)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 0, self.width, 0)


# --------------------------------------------------------------------------
# Layout helpers
# --------------------------------------------------------------------------

def _tile(width: float, label: str, value: str, note: str = "",
          accent: colors.Color | None = None) -> Table:
    """A small panel showing one headline figure."""
    value_style = STYLES["tile-value"]
    if accent is not None:
        value_style = ParagraphStyle("tile-value-accent", parent=value_style, textColor=accent)

    rows = [
        [Paragraph(_escape(value), value_style)],
        [Paragraph(_escape(label.upper()), STYLES["tile-label"])],
    ]
    if note:
        rows.append([Paragraph(_escape(note), STYLES["tile-label"])])

    table = Table(rows, colWidths=[width])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PANEL),
        ("LINEBELOW", (0, 0), (-1, -1), 0, PANEL),
        ("TOPPADDING", (0, 0), (-1, 0), 7),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
        ("TOPPADDING", (0, 1), (-1, -1), 0),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def _tile_row(tiles: Sequence[Table], total_width: float, columns: int,
              tile_width: float) -> Table:
    """Lay tiles out on a grid, padding the final row so widths stay even."""
    cells = list(tiles) + [""] * ((columns - len(tiles) % columns) % columns)
    rows = [cells[i:i + columns] for i in range(0, len(cells), columns)]
    table = Table(rows, colWidths=[total_width / columns] * columns)
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), (total_width / columns) - tile_width),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _data_table(header: Sequence[str], rows: Sequence[Sequence], widths: Sequence[float],
                aligns: Sequence[str] | None = None) -> Table:
    """A zebra striped table with a tinted header row."""
    body = [[Paragraph(_escape(h), STYLES["cell-bold"]) for h in header]]
    for row in rows:
        body.append([
            cell if isinstance(cell, Flowable) else Paragraph(_escape(str(cell)), STYLES["cell"])
            for cell in row
        ])

    table = Table(body, colWidths=list(widths), repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), PANEL),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, RULE),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, colors.HexColor("#eef2f6")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]
    for index, align in enumerate(aligns or []):
        style.append(("ALIGN", (index, 0), (index, -1), align.upper()))
    table.setStyle(TableStyle(style))
    return table


def _section(title: str, *content: Flowable) -> list[Flowable]:
    """A titled section, with the heading pinned to the start of its content."""
    heading = [
        Spacer(1, 9),
        Paragraph(_escape(title), STYLES["heading"]),
        HorizontalRule(),
        Spacer(1, 6),
    ]
    if not content:
        return heading
    return [KeepTogether(heading + [content[0]]), *content[1:]]


# --------------------------------------------------------------------------
# Report sections
# --------------------------------------------------------------------------

def _title_block(health: ProjectHealth, width: float) -> list[Flowable]:
    meta = [
        ("Project key", health.key),
        ("Branch", health.branch or "default"),
        ("Last analysis", fmt_datetime(health.analysed_at)),
        ("Analysed version", health.last_version or "-"),
        ("Report generated", fmt_datetime(health.generated_at)),
        ("SonarQube version", health.server_version or "unknown"),
    ]
    rows = [
        [Paragraph(_escape(label), STYLES["muted"]),
         Paragraph(_escape(_truncate(str(value), 90)), STYLES["cell"])]
        for label, value in meta
    ]
    meta_table = Table(rows, colWidths=[width * 0.22, width * 0.78])
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))

    return [
        Paragraph("Code Health Report", STYLES["title"]),
        Paragraph(_escape(health.name), STYLES["subtitle"]),
        Spacer(1, 10),
        meta_table,
        Spacer(1, 10),
    ]


def _quality_gate_banner(health: ProjectHealth, width: float) -> Table:
    status = (health.quality_gate_status or "NONE").upper()
    colour = GATE_COLOURS.get(status, MUTED)
    label = {"OK": "PASSED", "ERROR": "FAILED", "NONE": "NOT AVAILABLE"}.get(status, status)

    failing = [c for c in health.conditions if c.status.upper() in ("ERROR", "WARN")]
    if status in ("OK", "PASSED"):
        detail = "All quality gate conditions are met."
    elif failing:
        detail = f"{len(failing)} of {len(health.conditions)} conditions are not met."
    else:
        detail = "No quality gate result was reported for this project."

    rows = [[
        Paragraph(
            f'<font color="{_hex(colour)}" size="13"><b>QUALITY GATE {_escape(label)}</b></font>',
            STYLES["body"]),
        Paragraph(_escape(detail), STYLES["muted"]),
    ]]
    table = Table(rows, colWidths=[width * 0.42, width * 0.58])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PANEL),
        ("LINEBEFORE", (0, 0), (0, -1), 3, colour),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return table


def _ratings_row(health: ProjectHealth, width: float) -> Table:
    ratings = [
        ("Reliability", health.number("reliability_rating"), "bugs"),
        ("Security", health.number("security_rating"), "vulnerabilities"),
        ("Security review", health.number("security_review_rating"), "security_hotspots"),
        ("Maintainability", health.number("sqale_rating"), "code_smells"),
    ]

    letters, labels, counts = [], [], []
    style = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 2), (-1, 2), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]

    for index, (label, rating, count_metric) in enumerate(ratings):
        letter = fmt_rating(rating)
        colour = RATING_COLOURS.get(letter, MUTED)
        letters.append(Paragraph(
            f'<font color="{_hex(colour)}"><b>{letter}</b></font>',
            ParagraphStyle("rating", parent=STYLES["body"], fontSize=26, leading=29,
                           alignment=1)))
        labels.append(Paragraph(
            _escape(label.upper()),
            ParagraphStyle("rating-label", parent=STYLES["tile-label"], alignment=1)))
        count = health.number(count_metric)
        counts.append(Paragraph(
            _escape(f"{fmt_int(count)} open" if count is not None else "-"),
            ParagraphStyle("rating-count", parent=STYLES["tile-label"], alignment=1)))
        style.append(("BACKGROUND", (index, 0), (index, -1), PANEL))
        if index:
            style.append(("LINEBEFORE", (index, 0), (index, -1), 4, WHITE))

    table = Table([letters, labels, counts], colWidths=[width / 4] * 4)
    table.setStyle(TableStyle(style))
    return table


def _headline_tiles(health: ProjectHealth, width: float) -> Table:
    columns = 4
    gutter = 6
    tile_width = (width - gutter * (columns - 1)) / columns

    coverage = health.number("coverage")
    duplication = health.number("duplicated_lines_density")
    hotspots_reviewed = health.number("security_hotspots_reviewed")

    debt_ratio = health.number("sqale_debt_ratio")

    definitions = [
        ("Open issues", fmt_int(health.total_issues), "unresolved", None),
        ("Bugs", fmt_int(health.number("bugs")), "reliability", None),
        ("Vulnerabilities", fmt_int(health.number("vulnerabilities")), "security", None),
        ("Code smells", fmt_int(health.number("code_smells")), "maintainability", None),
        ("Coverage", fmt_pct(coverage), "line and branch",
         _threshold_colour(coverage, good=80, warn=50)),
        ("Duplication", fmt_pct(duplication), "duplicated lines",
         _threshold_colour(duplication, good=3, warn=10, lower_is_better=True)),
        ("Security hotspots", fmt_int(health.number("security_hotspots")),
         f"{fmt_pct(hotspots_reviewed, 0)} reviewed" if hotspots_reviewed is not None else "to review",
         None),
        ("Technical debt", fmt_effort(health.number("sqale_index")),
         f"{fmt_pct(debt_ratio)} debt ratio" if debt_ratio is not None else "to fix all smells",
         None),
        ("Lines of code", fmt_int(health.number("ncloc")), "excluding comments", None),
        ("Files", fmt_int(health.number("files")), "analysed", None),
        ("Comment density", fmt_pct(health.number("comment_lines_density")), "of all lines", None),
        ("Cognitive complexity", fmt_int(health.number("cognitive_complexity")),
         "whole project", None),
    ]

    tiles = [
        _tile(tile_width, label, value, note, accent)
        for label, value, note, accent in definitions
    ]
    return _tile_row(tiles, width, columns, tile_width)


def _threshold_colour(value: float | None, good: float, warn: float,
                      lower_is_better: bool = False) -> colors.Color | None:
    if value is None:
        return None
    if lower_is_better:
        if value <= good:
            return RATING_COLOURS["A"]
        return RATING_COLOURS["C"] if value <= warn else RATING_COLOURS["E"]
    if value >= good:
        return RATING_COLOURS["A"]
    return RATING_COLOURS["C"] if value >= warn else RATING_COLOURS["E"]


def _conditions_table(health: ProjectHealth, width: float) -> Flowable:
    if not health.conditions:
        return Paragraph("No quality gate conditions are configured for this project.",
                         STYLES["muted"])

    rows = []
    for condition in sorted(health.conditions, key=lambda c: c.status.upper() != "ERROR"):
        status = condition.status.upper()
        colour = GATE_COLOURS.get("ERROR" if status == "ERROR" else "OK", MUTED)
        label = {"OK": "Passed", "ERROR": "Failed", "WARN": "Warning"}.get(status, status.title())
        rows.append([
            Paragraph(_escape(_metric_label(condition.metric)), STYLES["cell"]),
            Paragraph(_escape(_format_condition_value(condition.metric, condition.actual)),
                      STYLES["cell"]),
            Paragraph(_escape(_condition_trigger(condition)), STYLES["cell"]),
            Paragraph(f'<font color="{_hex(colour)}"><b>{label}</b></font>',
                      STYLES["cell"]),
        ])

    return _data_table(
        ["Condition", "Actual", "Fails when", "Status"],
        rows,
        [width * 0.40, width * 0.17, width * 0.28, width * 0.15],
        ["left", "right", "left", "left"],
    )


def _condition_trigger(condition) -> str:
    """Describe the value that makes a condition fail, as SonarQube defines it."""
    comparators = {"GT": "greater than", "LT": "less than", "GTE": "at least",
                   "LTE": "at most", "EQ": "equal to", "NE": "not equal to"}
    comparator = (condition.comparator or "").upper()
    threshold = _format_condition_value(condition.metric, condition.threshold)

    # Ratings are numbers where higher is worse, so describe them in those terms.
    if condition.metric.endswith("_rating"):
        if comparator in ("GT", "GTE"):
            return f"worse than {threshold}"
        if comparator in ("LT", "LTE"):
            return f"better than {threshold}"

    return f"{comparators.get(comparator, comparator.lower())} {threshold}".strip()


def _format_condition_value(metric: str, value: str | None) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
    except ValueError:
        return value
    if metric.endswith("_rating"):
        return fmt_rating(number)
    if "density" in metric or metric.endswith("coverage") or metric.endswith("_ratio"):
        return fmt_pct(number)
    if metric in ("sqale_index", "new_technical_debt", "reliability_remediation_effort",
                  "security_remediation_effort"):
        return fmt_effort(number)
    return fmt_int(number)


def _metric_label(metric: str) -> str:
    known = {
        "new_reliability_rating": "Reliability rating on new code",
        "new_security_rating": "Security rating on new code",
        "new_maintainability_rating": "Maintainability rating on new code",
        "new_security_review_rating": "Security review rating on new code",
        "new_coverage": "Coverage on new code",
        "new_duplicated_lines_density": "Duplicated lines on new code",
        "new_violations": "Issues on new code",
        "sqale_index": "Technical debt",
        "sqale_debt_ratio": "Technical debt ratio",
        "duplicated_lines_density": "Duplicated lines",
        "ncloc": "Lines of code",
    }
    if metric in known:
        return known[metric]
    return metric.replace("new_", "New ").replace("_", " ").capitalize()


def _issue_breakdown(health: ProjectHealth, width: float) -> list[Flowable]:
    if not health.severities and not health.issue_types:
        return [Paragraph("No open issues were reported for this project.", STYLES["muted"])]

    ordered = sorted(
        health.severities.items(),
        key=lambda kv: SEVERITY_ORDER.index(kv[0]) if kv[0] in SEVERITY_ORDER else 99,
    )
    segments = [
        (name, count, SEVERITY_COLOURS.get(name.upper(), MUTED))
        for name, count in ordered
    ]

    total = sum(count for _, count, _ in segments) or 1
    legend_cells = [
        Paragraph(
            f'<font color="{_hex(colour)}">■</font> '
            f'{_escape(name.title())} <b>{count:,}</b> '
            f'<font color="{_hex(MUTED)}">({count / total:.0%})</font>',
            STYLES["cell"])
        for name, count, colour in segments
    ]
    columns = min(4, max(1, len(legend_cells)))
    padded = legend_cells + [""] * ((columns - len(legend_cells) % columns) % columns)
    legend = Table(
        [padded[i:i + columns] for i in range(0, len(padded), columns)],
        colWidths=[width / columns] * columns,
    )
    legend.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    content: list[Flowable] = [
        Paragraph(f"<b>{health.total_issues:,}</b> open issues by severity", STYLES["body"]),
        Spacer(1, 5),
        DistributionBar(segments),
        Spacer(1, 3),
        legend,
    ]

    if health.issue_types:
        type_rows = [
            [_metric_label(name.title()), fmt_int(count), f"{count / (health.total_issues or 1):.0%}"]
            for name, count in sorted(health.issue_types.items(), key=lambda kv: -kv[1])
        ]
        content += [
            Spacer(1, 9),
            _data_table(["Issue type", "Count", "Share"], type_rows,
                        [width * 0.5, width * 0.25, width * 0.25],
                        ["left", "right", "right"]),
        ]

    return content


def _new_code_section(health: ProjectHealth, width: float) -> list[Flowable] | None:
    metrics = [
        ("New lines", fmt_int(health.number("new_lines"))),
        ("New bugs", fmt_int(health.number("new_bugs"))),
        ("New vulnerabilities", fmt_int(health.number("new_vulnerabilities"))),
        ("New code smells", fmt_int(health.number("new_code_smells"))),
        ("Coverage on new code", fmt_pct(health.number("new_coverage"))),
        ("Duplication on new code", fmt_pct(health.number("new_duplicated_lines_density"))),
        ("New security hotspots", fmt_int(health.number("new_security_hotspots"))),
        ("Debt on new code", fmt_effort(health.number("new_technical_debt"))),
    ]
    if all(value == "-" for _, value in metrics):
        return None

    columns = 4
    gutter = 6
    tile_width = (width - gutter * (columns - 1)) / columns
    tiles = [_tile(tile_width, label, value) for label, value in metrics]
    return [_tile_row(tiles, width, columns, tile_width)]


def _trend_chart(health: ProjectHealth, width: float, metrics: Sequence[str],
                 title: str, percentage: bool) -> Flowable | None:
    series = [(m, health.history.get(m)) for m in metrics]
    series = [(m, points) for m, points in series if points and len(points) > 1]
    if not series:
        return None

    # Align every series onto a common, evenly spaced set of dates so the
    # category axis stays readable regardless of analysis frequency.
    dates = sorted({point[0] for _, points in series for point in points})
    dates = _downsample(dates, 10)
    labels = [d.strftime("%d %b") for d in dates]

    palette = [ACCENT, colors.HexColor("#d6304a"), colors.HexColor("#ef9a2f"),
               colors.HexColor("#2e9e5b")]

    data, legend_pairs = [], []
    for index, (metric, points) in enumerate(series):
        data.append([_value_at(points, date) for date in dates])
        legend_pairs.append((palette[index % len(palette)], _metric_label(metric)))

    height = 150
    drawing = Drawing(width, height)
    chart = HorizontalLineChart()
    chart.x = 34
    chart.y = 34
    chart.width = width - 50
    chart.height = height - 60
    chart.data = data
    chart.joinedLines = 1
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 6.5
    chart.categoryAxis.labels.fillColor = MUTED
    chart.categoryAxis.labels.angle = 30
    chart.categoryAxis.labels.boxAnchor = "ne"
    chart.categoryAxis.labels.dy = -3
    chart.categoryAxis.strokeColor = RULE
    chart.valueAxis.valueMin = 0
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labels.fontSize = 6.5
    chart.valueAxis.labels.fillColor = MUTED
    chart.valueAxis.strokeColor = RULE
    chart.valueAxis.gridStrokeColor = colors.HexColor("#eef2f6")
    chart.valueAxis.visibleGrid = 1
    if percentage:
        chart.valueAxis.valueMax = 100
        chart.valueAxis.labelTextFormat = "%d%%"

    for index in range(len(data)):
        chart.lines[index].strokeColor = palette[index % len(palette)]
        chart.lines[index].strokeWidth = 1.4

    drawing.add(chart)

    legend = Legend()
    legend.x = 34
    legend.y = height - 6
    legend.boxAnchor = "nw"
    legend.alignment = "right"
    legend.columnMaximum = 1
    legend.deltax = 12
    legend.dx = 5
    legend.dy = 5
    legend.dxTextSpace = 4
    legend.fontName = "Helvetica"
    legend.fontSize = 7
    legend.fillColor = MUTED
    legend.strokeWidth = 0
    legend.colorNamePairs = legend_pairs
    drawing.add(legend)
    drawing.add(Line(0, height - 20, width, height - 20, strokeColor=colors.white,
                     strokeWidth=0))

    return KeepTogether([
        Paragraph(_escape(title), STYLES["body"]),
        drawing,
    ])


def _downsample(items: list, limit: int) -> list:
    if len(items) <= limit:
        return items
    step = (len(items) - 1) / (limit - 1)
    picked = [items[int(round(index * step))] for index in range(limit)]
    # Guard against duplicates introduced by rounding.
    return list(dict.fromkeys(picked))


def _value_at(points: list[tuple[datetime, float]], date: datetime) -> float:
    """The most recent value at or before `date`, forward filling gaps."""
    value = points[0][1]
    for point_date, point_value in points:
        if point_date > date:
            break
        value = point_value
    return value


def _top_table(title: str, header: str, rows: Sequence[tuple[str, int]],
               width: float) -> list[Flowable]:
    if not rows:
        return []
    total = sum(count for _, count in rows) or 1
    body = [
        [_truncate(name, 90), fmt_int(count), f"{count / total:.0%}"]
        for name, count in rows
    ]
    return _section(
        title,
        _data_table([header, "Issues", "Share of top 10"], body,
                    [width * 0.62, width * 0.19, width * 0.19],
                    ["left", "right", "right"]),
    )


# --------------------------------------------------------------------------
# Page furniture
# --------------------------------------------------------------------------

def _page_decorations(health: ProjectHealth):
    def draw(canvas, doc):
        canvas.saveState()
        width, height = A4

        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.6)
        canvas.line(MARGIN, height - MARGIN + 6, width - MARGIN, height - MARGIN + 6)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN, height - MARGIN + 10,
                          _truncate(f"{health.name} — SonarQube code health", 90))
        canvas.drawRightString(width - MARGIN, height - MARGIN + 10,
                               health.generated_at.strftime("%d %b %Y"))

        canvas.line(MARGIN, MARGIN - 6, width - MARGIN, MARGIN - 6)
        canvas.drawString(MARGIN, MARGIN - 16,
                          _truncate(f"{health.key} ({health.branch or 'default branch'})", 90))
        canvas.drawRightString(width - MARGIN, MARGIN - 16, f"Page {doc.page}")
        canvas.restoreState()

    return draw


def build_report(health: ProjectHealth, output_path: str) -> str:
    """Render the report to `output_path` and return that path."""
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN + 6,
        title=f"{health.name} code health report",
        author="Telicent shared-workflows",
        subject=f"SonarQube code health for {health.key}",
    )
    width = doc.width

    story: list[Flowable] = []
    story += _title_block(health, width)
    story.append(_quality_gate_banner(health, width))

    story += _section("Overall ratings", _ratings_row(health, width))
    story += _section("Headline metrics", _headline_tiles(health, width))
    story += _section("Quality gate conditions", _conditions_table(health, width))

    new_code = _new_code_section(health, width)
    if new_code:
        story += _section("New code", *new_code)

    story += _section("Issue breakdown", *_issue_breakdown(health, width))

    # Code smells usually outnumber the other issue types by orders of
    # magnitude, so they get a chart of their own rather than flattening
    # everything else onto the axis.
    charts = [
        _trend_chart(health, width, ["bugs", "vulnerabilities", "security_hotspots"],
                     "Bugs, vulnerabilities and hotspots over time", percentage=False),
        _trend_chart(health, width, ["code_smells"],
                     "Code smells over time", percentage=False),
        _trend_chart(health, width, ["coverage", "duplicated_lines_density"],
                     "Coverage and duplication over time", percentage=True),
        _trend_chart(health, width, ["ncloc"], "Lines of code over time", percentage=False),
    ]
    charts = [chart for chart in charts if chart is not None]
    if charts:
        spaced: list[Flowable] = []
        for chart in charts:
            spaced += [chart, Spacer(1, 8)]
        story += _section("Trends", *spaced)

    story += _top_table("Most frequent rule violations", "Rule", health.top_rules, width)
    story += _top_table("Files with the most issues", "File", health.top_files, width)

    doc.build(story, onFirstPage=_page_decorations(health),
              onLaterPages=_page_decorations(health))
    return output_path
