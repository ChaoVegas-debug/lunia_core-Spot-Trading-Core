"""Chart helpers for Telegram reporting."""
from __future__ import annotations

import base64
import io
from typing import Iterable

try:  # pragma: no cover - matplotlib optional
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover - offline fallback
    plt = None

_FALLBACK_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABDQottAAAAABJRU5ErkJggg=="
)


def _render(plotter) -> bytes:
    if plt is None:
        return _FALLBACK_PNG
    fig, ax = plt.subplots()
    try:
        plotter(ax)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        return buf.getvalue()
    finally:  # pragma: no cover - cleanup
        plt.close(fig)


def plot_equity_curve(points: Iterable[dict]) -> bytes:
    points = list(points)
    if not points:
        return _FALLBACK_PNG

    def _plot(ax):
        xs = [item["ts"] for item in points]
        ys = [item["equity"] for item in points]
        ax.plot(xs, ys, marker="o")
        ax.set_title("Equity Curve")
        ax.set_xlabel("Timestamp")
        ax.set_ylabel("Equity")
        ax.tick_params(axis="x", rotation=45)

    return _render(_plot)


def plot_pnl_bars(rows: Iterable[dict]) -> bytes:
    rows = list(rows)
    if not rows:
        return _FALLBACK_PNG

    def _plot(ax):
        xs = [item["ts"] for item in rows]
        ys = [item["pnl"] for item in rows]
        ax.bar(xs, ys)
        ax.set_title("PnL by Period")
        ax.set_xlabel("Timestamp")
        ax.set_ylabel("PnL")
        ax.tick_params(axis="x", rotation=45)

    return _render(_plot)


__all__ = ["plot_equity_curve", "plot_pnl_bars"]
