"""Build the report charts from reports/tables/ and save them to reports/figures/.

Usage from the project root: python -m src.viz
Every number in a title or label is read from a result table, never typed by hand.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLES_DIR = ROOT / "reports" / "tables"
FIGURES_DIR = ROOT / "reports" / "figures"

# FY28 is the first full forward year with a quoted futures price; FY29-FY30 follow the same pattern.
FY = 2028

# One colour per strategy in every chart. Blue, orange and aqua are the colour-blind-safe leading slots;
# every strategy is also named in text on the chart, so colour is never the only cue.
STRATEGY_COLOURS = {
    "spot": "#eb6834",
    "hedge_100": "#2a78d6",
    "battery": "#1baf7a",
    "ppa": "#6250d6",
    "ppa_plus_battery": "#e87ba4",
}
STRATEGY_LABELS = {
    "spot": "Spot only",
    "hedge_100": "100% futures hedge",
    "battery": "Battery",
    "ppa": "Solar PPA ($65 strike)",
    "ppa_plus_battery": "Solar PPA + battery",
}
HIGHLIGHT = "#e34948"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"],
    "font.size": 10,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": "#c3c2b7",
    "axes.labelcolor": INK_SECONDARY,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "xtick.color": INK_SECONDARY,
    "ytick.color": INK_SECONDARY,
    "legend.frameon": False,
    # Dollar signs in titles are prices, not maths.
    "text.parse_math": False,
})


def read_table(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES_DIR / f"{name}.csv")


def titled_figure(title: str, subtitle: str, size: tuple[float, float] = (9, 5.2)):
    """Figure with a left-aligned takeaway title and a smaller subtitle that states the measure."""
    fig, ax = plt.subplots(figsize=size)
    fig.subplots_adjust(top=0.80, left=0.10, right=0.96, bottom=0.13)
    fig.text(0.02, 0.965, title, fontsize=13, fontweight="bold", color=INK, va="top", wrap=True)
    fig.text(0.02, 0.885, subtitle, fontsize=9.5, color=INK_SECONDARY, va="top", wrap=True)
    return fig, ax


def save(fig, name: str) -> None:
    fig.savefig(FIGURES_DIR / f"{name}.png", dpi=150)
    plt.close(fig)


def hedge_curve_chart() -> None:
    """Expected vs P95 cost across hedge levels 0-130% of average load."""
    curve = read_table("hedge_curve").query("fy == @FY")
    unhedged = curve.query("hedge_pct == 0").iloc[0]
    best = curve.loc[curve["p95_cost_m"].idxmin()]
    fig, ax = titled_figure(
        f"Hedging {best.hedge_pct:.0f}% of average load cuts FY{FY % 100} bad-year cost by "
        f"${best.p95_reduction_m:.1f}M, with no change in expected cost",
        f"Annual wholesale cost by baseload hedge level, FY{FY % 100}, $M. P95 = cost in a 1-in-20 bad year. "
        "Past 100% the surplus hedge adds risk again.",
    )
    # Stopping slightly short of the P95 minimum leaves room for volume risk, collateral and any futures premium.
    ax.axvspan(90, 100, color=STRATEGY_COLOURS["hedge_100"], alpha=0.08, lw=0)
    ax.text(95, curve["p95_cost_m"].max(), "recommended\n90-100%", ha="center", va="top",
            fontsize=8.5, color=INK_SECONDARY)
    ax.plot(curve["hedge_pct"], curve["p95_cost_m"], color=STRATEGY_COLOURS["hedge_100"], lw=2,
            marker="o", ms=5, label="P95 (bad-year) cost")
    ax.plot(curve["hedge_pct"], curve["expected_cost_m"], color=MUTED, lw=2, ls="--", label="Expected cost")
    ax.annotate(f"Spot only: ${unhedged.p95_cost_m:.2f}M", (0, unhedged.p95_cost_m), xytext=(8, 4),
                textcoords="offset points", fontsize=9, color=INK)
    ax.annotate(f"{best.hedge_pct:.0f}% hedge: ${best.p95_cost_m:.2f}M", (best.hedge_pct, best.p95_cost_m),
                xytext=(best.hedge_pct, best.p95_cost_m + 2), ha="center", fontsize=9, color=INK,
                arrowprops={"arrowstyle": "-", "color": INK_SECONDARY, "lw": 0.8})
    ax.annotate(f"Expected ${unhedged.expected_cost_m:.2f}M at every level", (0, unhedged.expected_cost_m),
                xytext=(4, 6), textcoords="offset points", fontsize=9, color=INK_SECONDARY)
    ax.set_xlabel("Hedge volume (% of average load)")
    ax.set_ylabel("Annual cost ($M)")
    ax.set_xticks(range(0, 131, 10))
    ax.set_ylim(unhedged.expected_cost_m - 1.5, unhedged.p95_cost_m + 1)
    ax.legend(loc="upper right")
    save(fig, "01_hedge_curve")


def strategy_chart() -> None:
    """Expected and P95 cost per strategy as a dumbbell; the gap is the cost of uncertainty."""
    summary = read_table("strategy_summary").query("fy == @FY").set_index("strategy")
    strategies = list(STRATEGY_COLOURS)[::-1]
    battery_capex = summary.loc["battery", "capex_m"]
    fig, ax = titled_figure(
        "Only the hedge shrinks the bad year; battery and solar PPA cost more than spot on both measures",
        f"Expected (filled) and P95 bad-year (hollow) annual cost, FY{FY % 100}, $M. Battery rows include "
        f"${battery_capex:.2f}M a year of equivalent capex + O&M.",
    )
    fig.subplots_adjust(left=0.22)
    for row, strategy in enumerate(strategies):
        expected, p95 = summary.loc[strategy, ["expected_cost_m", "p95_cost_m"]]
        colour = STRATEGY_COLOURS[strategy]
        ax.plot([expected, p95], [row, row], color=colour, lw=2.5)
        ax.scatter(expected, row, s=70, color=colour, zorder=3)
        ax.scatter(p95, row, s=70, facecolor=SURFACE, edgecolor=colour, lw=2, zorder=3)
        ax.text(expected - 0.15, row + 0.18, f"{expected:.2f}", ha="right", fontsize=9, color=INK)
        ax.text(p95 + 0.15, row + 0.18, f"{p95:.2f}", ha="left", fontsize=9, color=INK)
    ax.axvline(summary.loc["spot", "expected_cost_m"], color=MUTED, lw=1, ls=":")
    ax.set_yticks(range(len(strategies)), [STRATEGY_LABELS[s] for s in strategies])
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Annual cost ($M)")
    ax.set_xlim(summary["expected_cost_m"].min() - 1.5, summary.loc[strategies, "p95_cost_m"].max() + 1.5)
    save(fig, "02_strategy_comparison")


def realised_vs_futures_chart() -> None:
    """Expected cost for spot and the full hedge when realised spot ends 20% below, at, or 20% above futures."""
    realised = read_table("realised_vs_futures").query("fy == @FY and strategy in ['spot', 'hedge_100']")
    payoff = read_table("hedge_breakeven").query("fy == @FY").iloc[0]
    hedged = realised.query("strategy == 'hedge_100'")["expected_cost_m"]
    fig, ax = titled_figure(
        f"A full hedge holds FY{FY % 100} cost near ${hedged.mean():.0f}M whether spot ends 20% below "
        "or above futures",
        f"Expected annual cost, $M. Each $1/MWh that spot averages above the ${payoff.futures_price:.2f} futures "
        f"price pays the hedge ${payoff.payoff_m_per_dollar_100:.2f}M; below futures the hedge pays the same back.",
    )
    levels = sorted(realised["realised_level"].unique())
    width = 0.36
    for offset, strategy in [(-width / 2, "spot"), (width / 2, "hedge_100")]:
        costs = realised.query("strategy == @strategy").set_index("realised_level").loc[levels, "expected_cost_m"]
        positions = [i + offset for i in range(len(levels))]
        ax.bar(positions, costs, width=width - 0.03, color=STRATEGY_COLOURS[strategy],
               label=STRATEGY_LABELS[strategy])
        for x, cost in zip(positions, costs):
            ax.text(x, cost + 0.6, f"{cost:.2f}", ha="center", fontsize=9, color=INK)
    prices = realised.drop_duplicates("realised_level").set_index("realised_level")["realised_price"]
    ax.set_xticks(range(len(levels)), [
        f"Spot {abs(level - 1):.0%} {'below' if level < 1 else 'above'} futures\n(${prices[level]:.2f}/MWh)"
        if level != 1 else f"Spot equals futures\n(${prices[level]:.2f}/MWh)"
        for level in levels
    ])
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Expected annual cost ($M)")
    ax.legend(loc="upper left")
    save(fig, "03_realised_vs_futures")


def capture_price_chart() -> None:
    """Baseload futures price vs the solar capture price, with the assumed PPA strike as a reference."""
    breakeven = read_table("ppa_breakeven").query("fy == @FY").iloc[0]
    fig, ax = titled_figure(
        f"Solar output earns only {breakeven.capture_ratio:.0%} of the baseload price, below the "
        f"${breakeven.assumed_strike:.0f}/MWh assumed PPA strike",
        f"FY{FY % 100}, $/MWh. Capture price = generation-weighted average spot price; most solar output lands "
        "at midday, when prices are lowest.",
        size=(9, 4.2),
    )
    fig.subplots_adjust(left=0.24, top=0.76, bottom=0.16)
    bars = [("Solar capture price", breakeven.solar_capture_price, STRATEGY_COLOURS["ppa"]),
            ("Baseload futures price", breakeven.futures_price, STRATEGY_COLOURS["hedge_100"])]
    for row, (label, price, colour) in enumerate(bars):
        ax.barh(row, price, height=0.55, color=colour)
        ax.text(price + 1, row, f"${price:.2f}", va="center", fontsize=10, color=INK)
    ax.axvline(breakeven.assumed_strike, color=INK, lw=1.2, ls="--")
    ax.text(breakeven.assumed_strike + 1, 1.45, f"Assumed strike ${breakeven.assumed_strike:.0f} (unsourced)",
            fontsize=9, color=INK)
    ax.set_yticks(range(len(bars)), [label for label, _, _ in bars])
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="y", visible=False)
    ax.set_ylim(-0.5, 1.7)
    ax.set_xlim(0, breakeven.futures_price * 1.15)
    ax.set_xlabel("Price ($/MWh)")
    save(fig, "04_solar_capture_price")


def ppa_strike_chart() -> None:
    """PPA expected saving vs spot by strike, settled on every interval or suspended when spot < 0."""
    strikes = read_table("ppa_strike_sensitivity").query("fy == @FY")
    breakeven = read_table("ppa_breakeven").query("fy == @FY").iloc[0]
    settlements = [("all_intervals", "Settled on every interval", "-",
                    breakeven.breakeven_strike_all_intervals),
                   ("suspend_negative", "Suspended when spot < $0", "--",
                    breakeven.breakeven_strike_suspend_negative)]
    fig, ax = titled_figure(
        f"A negative-price clause lifts the PPA break-even strike from ${breakeven.breakeven_strike_all_intervals:.0f} "
        f"to ${breakeven.breakeven_strike_suspend_negative:.0f}/MWh",
        f"Solar PPA expected saving vs spot by strike, FY{FY % 100}, $M. Above zero the PPA lowers expected cost; "
        "break-even marked where each line crosses zero.",
    )
    ax.axhline(0, color=INK_SECONDARY, lw=1)
    for settlement, label, style, breakeven_strike in settlements:
        line = strikes.query("settlement == @settlement")
        # Saving is linear in strike, so the break-even point sits on the same straight line.
        points = pd.concat([line[["strike", "expected_saving_vs_spot_m"]],
                            pd.DataFrame({"strike": [breakeven_strike], "expected_saving_vs_spot_m": [0.0]})])
        points = points.sort_values("strike")
        ax.plot(points["strike"], points["expected_saving_vs_spot_m"], color=STRATEGY_COLOURS["ppa"], lw=2,
                ls=style, label=label)
        ax.scatter(line["strike"], line["expected_saving_vs_spot_m"], s=30, color=STRATEGY_COLOURS["ppa"], zorder=3)
        ax.scatter(breakeven_strike, 0, s=80, facecolor=SURFACE, edgecolor=INK, lw=1.5, zorder=4)
        ax.annotate(f"break-even ${breakeven_strike:.2f}", (breakeven_strike, 0), xytext=(4, 10),
                    textcoords="offset points", fontsize=9, color=INK)
    ax.set_xlabel("PPA strike ($/MWh)")
    ax.set_ylabel("Expected saving vs spot ($M a year)")
    ax.legend(loc="upper right")
    save(fig, "05_ppa_breakeven_strike")


def top_intervals_chart() -> None:
    """Share of the top 1% price intervals by month, with the May-Jul 2022 crisis window highlighted."""
    months = read_table("crisis_diagnostics")
    crisis = read_table("crisis_sensitivity").query("fy == @FY and strategy == 'spot'").set_index("pool")
    crisis_share = months.loc[months["in_crisis_window"], "share_of_top_intervals_pct"].sum()
    fig, ax = titled_figure(
        f"May-Jul 2022 holds {crisis_share:.0f}% of the top 1% prices, yet excluding it gives no reduction "
        "in cost of uncertainty",
        f"Share of the top 1% of 5-minute prices ({months['n_top_intervals'].sum():,} intervals at "
        f"${months['top_price_cut'].iloc[0]:.0f}/MWh or more, FY{FY % 100} re-levelled) by month. "
        f"Spot cost of uncertainty: {crisis.loc['all_days', 'cost_of_uncertainty_pct']:.1f}% of expected "
        f"with all days, {crisis.loc['excl_may_jul_2022', 'cost_of_uncertainty_pct']:.1f}% without May-Jul 2022.",
        size=(10.5, 5.2),
    )
    colours = [HIGHLIGHT if in_crisis else MUTED for in_crisis in months["in_crisis_window"]]
    ax.bar(range(len(months)), months["share_of_top_intervals_pct"], width=0.8, color=colours)
    labels = pd.PeriodIndex(months["month"], freq="M").strftime("%b %y")
    ax.set_xticks(range(0, len(months), 3), labels[::3])
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Share of top 1% intervals (%)")
    ax.set_xlabel("Month (historical pool, Oct 2021 - Jun 2024)")
    peak = months["share_of_top_intervals_pct"].idxmax()
    ax.annotate("May-Jul 2022\n(dropped in the sensitivity run)", (peak, months.loc[peak, "share_of_top_intervals_pct"]),
                xytext=(14, -10), textcoords="offset points", fontsize=9, color=INK)
    save(fig, "06_top_intervals_by_month")


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    hedge_curve_chart()
    strategy_chart()
    realised_vs_futures_chart()
    capture_price_chart()
    ppa_strike_chart()
    top_intervals_chart()


if __name__ == "__main__":
    main()
