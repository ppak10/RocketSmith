"""Flight report generation: plots + markdown from OpenRocket simulation data."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from orhelper import FlightDataType, FlightEvent

from rocketsmith.openrocket.models import FlightReportResult, OpenRocketSimulation


# ── Plot style ────────────────────────────────────────────────────────────────

_BG = "white"
_GRID = "#dddddd"
_TEXT = "#333333"
_TITLE_COLOR = "#111111"
_LINE_PRIMARY = "#2266aa"
_LINE_SECONDARY = "#cc6622"
_EVENT_COLORS = {
    "burnout": "#cc3333",
    "apogee": "#228833",
    "deployment": "#8833aa",
    "ground_hit": "#888888",
}
_FIG_W, _FIG_H, _DPI = 10.0, 5.0, 200


# ── Helpers ──────────────────────────────────────────────────────────────────


def _get(sim: OpenRocketSimulation, fdt: FlightDataType) -> np.ndarray | None:
    return sim.timeseries.get(fdt)


def _event_times(sim: OpenRocketSimulation) -> dict[str, float | None]:
    """Extract the first occurrence of key flight events as {label: time_s}."""

    def _first(evt: FlightEvent) -> float | None:
        t = sim.events.get(evt)
        return float(t[0]) if t else None

    return {
        "burnout": _first(FlightEvent.BURNOUT),
        "apogee": _first(FlightEvent.APOGEE),
        "deployment": _first(FlightEvent.RECOVERY_DEVICE_DEPLOYMENT),
        "ground_hit": _first(FlightEvent.GROUND_HIT),
    }


def _setup_axes(ax, xlabel: str, ylabel: str) -> None:
    ax.set_facecolor(_BG)
    ax.set_xlabel(xlabel, color=_TEXT, fontsize=10)
    ax.set_ylabel(ylabel, color=_TEXT, fontsize=10)
    ax.tick_params(colors=_TEXT, labelsize=9)
    ax.grid(True, color=_GRID, linewidth=0.5, alpha=0.8)
    for spine in ax.spines.values():
        spine.set_color("#cccccc")


def _draw_events(ax, events: dict[str, float | None]) -> None:
    for label, t in events.items():
        if t is None:
            continue
        color = _EVENT_COLORS.get(label, "#888888")
        ax.axvline(t, color=color, linestyle="--", linewidth=0.8, alpha=0.8)
        ax.text(
            t,
            ax.get_ylim()[1] * 0.97,
            f" {label}",
            color=color,
            fontsize=7,
            rotation=90,
            va="top",
            ha="left",
        )


def _save_plot(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=_DPI, bbox_inches="tight", facecolor="white")


# ── Individual plot generators ───────────────────────────────────────────────


def _plot_single(
    time: np.ndarray,
    y: np.ndarray,
    events: dict[str, float | None],
    title: str,
    ylabel: str,
    out_path: Path,
    hlines: list[tuple[float, str, str]] | None = None,
) -> None:
    import matplotlib.pyplot as plt

    plt.switch_backend("agg")

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H))
    fig.patch.set_facecolor(_BG)
    ax.set_title(title, color=_TITLE_COLOR, fontsize=13, fontweight="bold", pad=10)
    _setup_axes(ax, "Time (s)", ylabel)
    ax.plot(time, y, color=_LINE_PRIMARY, linewidth=1.2)

    if hlines:
        for val, label, color in hlines:
            ax.axhline(val, color=color, linestyle=":", linewidth=0.8, alpha=0.6)
            ax.text(
                time[-1] * 0.98,
                val,
                f" {label}",
                color=color,
                fontsize=7,
                va="bottom",
                ha="right",
            )

    _draw_events(ax, events)
    plt.tight_layout()
    _save_plot(fig, out_path)
    plt.close(fig)


def _plot_thrust_mass(
    sim: OpenRocketSimulation,
    events: dict[str, float | None],
    out_path: Path,
) -> None:
    import matplotlib.pyplot as plt

    plt.switch_backend("agg")

    time = _get(sim, FlightDataType.TYPE_TIME)
    thrust = _get(sim, FlightDataType.TYPE_THRUST_FORCE)
    mass = _get(sim, FlightDataType.TYPE_MASS)
    if time is None:
        return

    fig, ax1 = plt.subplots(figsize=(_FIG_W, _FIG_H))
    fig.patch.set_facecolor(_BG)
    ax1.set_title(
        "Thrust & Mass vs Time",
        color=_TITLE_COLOR,
        fontsize=13,
        fontweight="bold",
        pad=10,
    )
    _setup_axes(ax1, "Time (s)", "Thrust (N)")

    if thrust is not None:
        ax1.plot(time, thrust, color=_LINE_PRIMARY, linewidth=1.2, label="Thrust")

    if mass is not None:
        ax2 = ax1.twinx()
        _setup_axes(ax2, "", "Mass (kg)")
        ax2.plot(time, mass, color=_LINE_SECONDARY, linewidth=1.2, label="Mass")
        ax2.set_ylabel("Mass (kg)", color=_LINE_SECONDARY, fontsize=10)
        ax2.tick_params(axis="y", colors=_LINE_SECONDARY)

    _draw_events(ax1, events)
    plt.tight_layout()
    _save_plot(fig, out_path)
    plt.close(fig)


def _plot_drag_mach(
    sim: OpenRocketSimulation,
    out_path: Path,
) -> None:
    import matplotlib.pyplot as plt

    plt.switch_backend("agg")

    mach = _get(sim, FlightDataType.TYPE_MACH_NUMBER)
    cd = _get(sim, FlightDataType.TYPE_DRAG_COEFF)
    if mach is None or cd is None:
        return

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H))
    fig.patch.set_facecolor(_BG)
    ax.set_title(
        "Drag Coefficient vs Mach Number",
        color=_TITLE_COLOR,
        fontsize=13,
        fontweight="bold",
        pad=10,
    )
    _setup_axes(ax, "Mach Number", "CD")
    ax.plot(mach, cd, color=_LINE_PRIMARY, linewidth=1.0, alpha=0.8)

    plt.tight_layout()
    _save_plot(fig, out_path)
    plt.close(fig)


# ── Main entry point ────────────────────────────────────────────────────────


def generate_flight_report(
    sim: OpenRocketSimulation,
    out_dir: Path,
) -> FlightReportResult:
    """Generate a flight report (markdown + plots) for a single simulation.

    Args:
        sim:     A completed OpenRocket simulation with timeseries data.
        out_dir: Directory to write report.md and *.png plots into.

    Returns:
        FlightReportResult with paths to all generated files.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    time = _get(sim, FlightDataType.TYPE_TIME)
    events = _event_times(sim)
    plot_paths: list[str] = []

    # ── Generate plots ──

    def _maybe_plot(fdt: FlightDataType, name: str, title: str, ylabel: str, **kw):
        y = _get(sim, fdt)
        if y is not None and time is not None:
            p = out_dir / f"{name}.png"
            _plot_single(time, y, events, title, ylabel, p, **kw)
            plot_paths.append(str(p))

    _maybe_plot(
        FlightDataType.TYPE_ALTITUDE,
        "altitude",
        "Altitude vs Time",
        "Altitude (m)",
    )
    _maybe_plot(
        FlightDataType.TYPE_VELOCITY_TOTAL,
        "velocity",
        "Velocity vs Time",
        "Velocity (m/s)",
    )
    _maybe_plot(
        FlightDataType.TYPE_ACCELERATION_TOTAL,
        "acceleration",
        "Acceleration vs Time",
        "Acceleration (m/s\u00b2)",
    )
    _maybe_plot(
        FlightDataType.TYPE_STABILITY,
        "stability",
        "Stability Margin vs Time",
        "Stability (cal)",
        hlines=[
            (1.0, "1.0 cal", "#44cc66"),
            (1.5, "1.5 cal", "#cccc44"),
        ],
    )

    # Thrust & mass (dual-axis)
    thrust_path = out_dir / "thrust_mass.png"
    _plot_thrust_mass(sim, events, thrust_path)
    if thrust_path.exists():
        plot_paths.append(str(thrust_path))

    # Drag vs Mach
    drag_path = out_dir / "drag_mach.png"
    _plot_drag_mach(sim, drag_path)
    if drag_path.exists():
        plot_paths.append(str(drag_path))

    # ── Extract summary values ──

    altitude = _get(sim, FlightDataType.TYPE_ALTITUDE)
    velocity = _get(sim, FlightDataType.TYPE_VELOCITY_TOTAL)
    max_altitude = float(altitude.max()) if altitude is not None else 0.0
    max_velocity = float(velocity.max()) if velocity is not None else 0.0
    flight_time = float(time.max()) if time is not None else 0.0
    time_to_apogee = events.get("apogee")

    # Stability: prefer FlightData values, fallback to timeseries
    min_stab = sim.min_stability_cal
    max_stab = sim.max_stability_cal
    if min_stab is None or max_stab is None:
        stab_ts = _get(sim, FlightDataType.TYPE_STABILITY)
        if stab_ts is not None and len(stab_ts) > 0:
            valid = stab_ts[np.isfinite(stab_ts)]
            if len(valid) > 0:
                min_stab = min_stab or float(valid.min())
                max_stab = max_stab or float(valid.max())

    # ── Write markdown ──

    report_path = out_dir / "report.md"
    _write_markdown(
        sim_name=sim.name,
        report_path=report_path,
        plot_names=[Path(p).name for p in plot_paths],
        max_altitude_m=max_altitude,
        max_velocity_ms=max_velocity,
        time_to_apogee_s=time_to_apogee,
        flight_time_s=flight_time,
        min_stability_cal=min_stab,
        max_stability_cal=max_stab,
        events=events,
    )

    # ── Write PDF ──

    pdf_path = out_dir / "report.pdf"
    _write_pdf(
        sim_name=sim.name,
        pdf_path=pdf_path,
        plot_paths=plot_paths,
        max_altitude_m=max_altitude,
        max_velocity_ms=max_velocity,
        time_to_apogee_s=time_to_apogee,
        flight_time_s=flight_time,
        min_stability_cal=min_stab,
        max_stability_cal=max_stab,
        events=events,
    )

    return FlightReportResult(
        simulation_name=sim.name,
        report_dir=str(out_dir),
        report_path=str(report_path),
        pdf_path=str(pdf_path),
        plot_paths=plot_paths,
        max_altitude_m=max_altitude,
        max_velocity_ms=max_velocity,
        time_to_apogee_s=time_to_apogee,
        flight_time_s=flight_time,
        min_stability_cal=min_stab,
        max_stability_cal=max_stab,
    )


# ── Markdown writer ──────────────────────────────────────────────────────────


def _fmt(val: float | None, unit: str = "", decimals: int = 1) -> str:
    if val is None:
        return "N/A"
    return f"{val:.{decimals}f}{(' ' + unit) if unit else ''}"


def _write_markdown(
    *,
    sim_name: str,
    report_path: Path,
    plot_names: list[str],
    max_altitude_m: float,
    max_velocity_ms: float,
    time_to_apogee_s: float | None,
    flight_time_s: float,
    min_stability_cal: float | None,
    max_stability_cal: float | None,
    events: dict[str, float | None],
) -> None:
    lines = [
        f"# Flight Report: {sim_name}",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Max Altitude | {_fmt(max_altitude_m, 'm')} |",
        f"| Max Velocity | {_fmt(max_velocity_ms, 'm/s')} |",
        f"| Time to Apogee | {_fmt(time_to_apogee_s, 's')} |",
        f"| Flight Time | {_fmt(flight_time_s, 's')} |",
        f"| Min Stability | {_fmt(min_stability_cal, 'cal')} |",
        f"| Max Stability | {_fmt(max_stability_cal, 'cal')} |",
        "",
        "## Flight Events",
        "",
        "| Event | Time (s) |",
        "|-------|----------|",
    ]

    event_labels = {
        "burnout": "Motor Burnout",
        "apogee": "Apogee",
        "deployment": "Recovery Deployment",
        "ground_hit": "Ground Hit",
    }
    for key, label in event_labels.items():
        t = events.get(key)
        lines.append(f"| {label} | {_fmt(t, 's')} |")

    lines.append("")

    # Plot sections
    plot_sections = {
        "altitude.png": ("Altitude", "Altitude above launch site vs flight time."),
        "velocity.png": ("Velocity", "Total velocity magnitude vs flight time."),
        "acceleration.png": (
            "Acceleration",
            "Total acceleration magnitude vs flight time.",
        ),
        "stability.png": (
            "Stability",
            "Stability margin in calibers vs flight time. "
            "Target range: 1.0-1.5 cal.",
        ),
        "thrust_mass.png": (
            "Thrust & Mass",
            "Motor thrust and total rocket mass vs flight time.",
        ),
        "drag_mach.png": (
            "Drag vs Mach",
            "Drag coefficient vs Mach number during flight.",
        ),
    }

    for filename in plot_names:
        section = plot_sections.get(filename)
        if section:
            title, desc = section
            lines.extend(
                [
                    f"## {title}",
                    "",
                    desc,
                    "",
                    f"![{title}]({filename})",
                    "",
                ]
            )

    report_path.write_text("\n".join(lines), encoding="utf-8")


# ── PDF writer ───────────────────────────────────────────────────────────────


def _write_pdf(
    *,
    sim_name: str,
    pdf_path: Path,
    plot_paths: list[str],
    max_altitude_m: float,
    max_velocity_ms: float,
    time_to_apogee_s: float | None,
    flight_time_s: float,
    min_stability_cal: float | None,
    max_stability_cal: float | None,
    events: dict[str, float | None],
) -> None:
    """Compose a multi-page PDF: cover page with summary, then one page per plot."""
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    plt.switch_backend("agg")

    pdf_dpi = 300

    with PdfPages(str(pdf_path)) as pdf:
        # ── Page 1: Summary ──────────────────────────────────────
        fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H * 1.4))
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        ax.axis("off")

        generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        summary_rows = [
            ("Max Altitude", _fmt(max_altitude_m, "m")),
            ("Max Velocity", _fmt(max_velocity_ms, "m/s")),
            ("Time to Apogee", _fmt(time_to_apogee_s, "s")),
            ("Flight Time", _fmt(flight_time_s, "s")),
            ("Min Stability", _fmt(min_stability_cal, "cal")),
            ("Max Stability", _fmt(max_stability_cal, "cal")),
        ]

        event_labels = {
            "burnout": "Motor Burnout",
            "apogee": "Apogee",
            "deployment": "Recovery Deployment",
            "ground_hit": "Ground Hit",
        }
        event_rows = [
            (label, _fmt(events.get(key), "s")) for key, label in event_labels.items()
        ]

        # Title
        ax.text(
            0.5,
            0.95,
            f"Flight Report: {sim_name}",
            transform=ax.transAxes,
            ha="center",
            va="top",
            fontsize=20,
            color="#111111",
            fontweight="bold",
        )
        ax.text(
            0.5,
            0.88,
            f"Generated: {generated}",
            transform=ax.transAxes,
            ha="center",
            va="top",
            fontsize=10,
            color="#666666",
        )

        # Summary table
        y = 0.78
        ax.text(
            0.15,
            y,
            "Summary",
            transform=ax.transAxes,
            fontsize=14,
            color="#111111",
            fontweight="bold",
        )
        y -= 0.06
        for label, value in summary_rows:
            ax.text(
                0.18, y, label, transform=ax.transAxes, fontsize=11, color="#555555"
            )
            ax.text(
                0.65,
                y,
                value,
                transform=ax.transAxes,
                fontsize=11,
                color="#111111",
                ha="left",
                fontweight="medium",
            )
            y -= 0.05

        # Events table
        y -= 0.04
        ax.text(
            0.15,
            y,
            "Flight Events",
            transform=ax.transAxes,
            fontsize=14,
            color="#111111",
            fontweight="bold",
        )
        y -= 0.06
        for label, value in event_rows:
            ax.text(
                0.18, y, label, transform=ax.transAxes, fontsize=11, color="#555555"
            )
            ax.text(
                0.65,
                y,
                value,
                transform=ax.transAxes,
                fontsize=11,
                color="#111111",
                ha="left",
                fontweight="medium",
            )
            y -= 0.05

        pdf.savefig(fig, dpi=pdf_dpi, facecolor="white")
        plt.close(fig)

        # ── Plot pages ───────────────────────────────────────────
        for plot_path_str in plot_paths:
            plot_path = Path(plot_path_str)
            if not plot_path.exists():
                continue

            img = plt.imread(str(plot_path))
            fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H))
            fig.patch.set_facecolor("white")
            ax.set_facecolor("white")
            ax.axis("off")
            ax.imshow(img, aspect="equal")
            plt.tight_layout(pad=0)
            pdf.savefig(fig, dpi=pdf_dpi, facecolor="white")
            plt.close(fig)
