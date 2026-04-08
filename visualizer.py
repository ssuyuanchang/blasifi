"""Visualization module: Plotly Sankey income statement chart.

Layout inspired by App Economy Insights:

  GREEN profit stream flows across the TOP, ascending rightward:
    Revenue → Gross Profit → Operating Income → Net Income

  RED cost streams branch DOWNWARD at each stage:
    Revenue ↘ COGS
    Gross   ↘ OpEx → R&D, SG&A, Amort
    Op Inc  ↘ Tax, Other, Disc

  Visual logic: at every step, subtract the red flowing down = green continuing right
"""

import plotly.graph_objects as go
from finance_data import QuarterlyReport, format_billions

# ── Colour palette ──
REV_NODE    = "rgba(30, 30, 30, 0.90)"
GREEN       = "rgba(44, 160, 44, 0.55)"
GREEN_NODE  = "rgba(44, 160, 44, 0.85)"
GREEN_DARK  = "rgba(35, 139, 69, 0.85)"
RED_LINK    = "rgba(210, 50, 50, 0.35)"
RED_NODE    = "rgba(210, 50, 50, 0.75)"
RED_DARK    = "rgba(180, 40, 40, 0.80)"

# ── Column x-positions ──
X0, X1, X2, X3, X4 = 0.01, 0.25, 0.50, 0.75, 0.99

# ── Y-positions: profit on TOP, costs on BOTTOM ──
REV_Y    = 0.45    # Revenue: center (starting point)
GROSS_Y  = 0.20    # Gross Profit: upper
OP_Y     = 0.08    # Operating Income: higher
NET_Y    = 0.03    # Net Income: highest (top-right corner)
COGS_Y   = 0.85    # Cost of Revenue: lower
OPEX_Y   = 0.55    # Operating Expenses: mid-lower
TAX_Y    = 0.42    # Tax: between profit & cost streams


def _yoy_label(report, key):
    if report.yoy and key in report.yoy:
        pct = report.yoy[key].get("change_pct")
        if pct is not None:
            sign = "+" if pct > 0 else ""
            return f"{sign}{pct}% Y/Y"
    return ""


def _margin_label(part, whole):
    if whole and whole != 0:
        return f"{abs(part / whole * 100):.0f}% margin"
    return ""


def _pct_of_rev(part, revenue):
    if revenue and revenue != 0:
        return f"{abs(part / revenue * 100):.0f}% of revenue"
    return ""


def _join(*parts):
    return "\n".join(p for p in parts if p)


def _spread(n, y_lo, y_hi):
    if n <= 0:
        return []
    if n == 1:
        return [(y_lo + y_hi) / 2]
    step = (y_hi - y_lo) / (n - 1)
    return [y_lo + i * step for i in range(n)]


def create_sankey_chart(report: QuarterlyReport, output_path: str = None) -> str:
    """Generate a Sankey diagram from quarterly income statement data."""

    rev   = report.total_revenue
    cogs  = report.cost_of_revenue
    gross = report.gross_profit or (rev - cogs)
    rd    = report.research_development
    sga   = report.selling_general_admin
    amort = report.amortization
    other_opex = report.other_operating_expenses
    total_opex = report.total_operating_expenses
    op_income  = report.operating_income or (gross - total_opex)
    other_non_op = report.other_non_operating
    tax   = report.tax_provision
    disc  = report.discontinued_operations
    net   = report.net_income

    has_other_pos = other_non_op and other_non_op > 0
    has_other_neg = other_non_op and other_non_op < 0
    has_disc      = disc and abs(disc) > 0

    labels, node_colors, x_pos, y_pos = [], [], [], []
    sources, targets, values, link_colors = [], [], [], []
    nid = {}

    def node(name, label, color, x, y):
        nid[name] = len(labels)
        labels.append(label)
        node_colors.append(color)
        x_pos.append(x)
        y_pos.append(y)

    def link(src, tgt, val, color):
        if val and val > 0:
            sources.append(nid[src])
            targets.append(nid[tgt])
            values.append(val)
            link_colors.append(color)

    # ═══════════════════════════════════════════
    #  Col 0 — Revenue (center, starting point)
    # ═══════════════════════════════════════════
    node("revenue",
         _join("Revenue", format_billions(rev), _yoy_label(report, "revenue")),
         REV_NODE, X0, REV_Y)

    # ═══════════════════════════════════════════
    #  Col 1 — Gross Profit (TOP) + COGS (BOTTOM)
    # ═══════════════════════════════════════════
    node("gross",
         _join("Gross Profit", format_billions(gross),
               _margin_label(gross, rev),
               _yoy_label(report, "gross_profit")),
         GREEN_NODE, X1, GROSS_Y)

    node("cogs",
         _join("Cost of Revenue", f"({format_billions(cogs)})"),
         RED_DARK, X1, COGS_Y)

    # ═══════════════════════════════════════════
    #  Col 2 — Op Income (TOP) + OpEx (BOTTOM)
    #           + Other+ standalone source
    # ═══════════════════════════════════════════
    op_color = GREEN_NODE if op_income >= 0 else RED_NODE
    node("op_income",
         _join("Operating Income", format_billions(op_income),
               _margin_label(op_income, rev),
               _yoy_label(report, "operating_income")),
         op_color, X2, OP_Y)

    node("opex",
         _join("Operating Expenses", f"({format_billions(total_opex)})"),
         RED_NODE, X2, OPEX_Y)

    if has_other_pos:
        node("other",
             _join("Other (non-op)", f"+{format_billions(other_non_op)}"),
             RED_DARK, X3, 0.18)

    # ═══════════════════════════════════════════
    #  Col 3 — OpEx breakdown (BOTTOM, stacked)
    #           + Other neg / Disc (MID)
    # ═══════════════════════════════════════════
    opex_items = []
    if rd > 0:
        opex_items.append(("rd", rd, "R&D", _pct_of_rev(rd, rev)))
    if sga > 0:
        opex_items.append(("sga", sga, "SG&A", _pct_of_rev(sga, rev)))
    if amort > 0:
        opex_items.append(("amort", amort, "Amortization", _pct_of_rev(amort, rev)))
    if other_opex > 0:
        opex_items.append(("other_opex", other_opex, "Other OpEx", ""))

    opex_ys = _spread(len(opex_items), 0.48, 0.92)
    for i, (name, val, display, extra) in enumerate(opex_items):
        node(name,
             _join(display, f"({format_billions(val)})", extra),
             RED_NODE, X3, opex_ys[i])

    # Mid-zone items at Col 3 (between profit and cost streams)
    mid_items = []
    if has_other_neg:
        mid_items.append("other_neg")
    if has_disc and disc < 0:
        mid_items.append("disc_neg")

    if mid_items:
        mid_ys = _spread(len(mid_items), 0.25, 0.35)
        for i, item in enumerate(mid_items):
            if item == "other_neg":
                node("other",
                     _join("Other (non-op)", format_billions(other_non_op)),
                     RED_DARK, X3, mid_ys[i])
            elif item == "disc_neg":
                node("discontinued",
                     _join("Discontinued", format_billions(disc)),
                     RED_DARK, X3, mid_ys[i])

    # ═══════════════════════════════════════════
    #  Col 4 — Net Income (TOP) + Tax (MID)
    # ═══════════════════════════════════════════
    net_color = GREEN_DARK if net >= 0 else RED_NODE
    node("net",
         _join("Net Income", format_billions(net),
               _margin_label(net, rev),
               _yoy_label(report, "net_income")),
         net_color, X4, NET_Y)

    node("tax",
         _join("Tax", f"({format_billions(tax)})"),
         RED_DARK, X4, TAX_Y)

    if has_disc and disc > 0:
        node("discontinued",
             _join("Discontinued", f"+{format_billions(disc)}"),
             RED_DARK, X3, 0.12)

    # ═══════════════════════════════════════════
    #  LINKS — green goes UP-right, red goes DOWN-right
    # ═══════════════════════════════════════════

    # Col 0 → 1: Revenue splits
    link("revenue", "gross", abs(gross), GREEN)        # ↗ green up
    link("revenue", "cogs",  abs(cogs),  RED_LINK)      # ↘ red down

    # Col 1 → 2: Gross Profit splits
    link("gross", "op_income", max(0, op_income), GREEN)     # ↗ green up
    link("gross", "opex",      abs(total_opex),   RED_LINK)  # ↘ red down

    # Col 2 → 3: OpEx breakdown
    for name, val, _, _ in opex_items:
        link("opex", name, abs(val), RED_LINK)  # → red continues right

    # Col 2 → 3/4: Operating Income splits
    op_out = abs(op_income)

    link("op_income", "tax", abs(tax), RED_LINK)        # ↘ red down
    op_out -= abs(tax)

    if has_other_neg:
        link("op_income", "other", abs(other_non_op), RED_LINK)     # ↘ red down
        op_out -= abs(other_non_op)

    if has_disc and disc < 0:
        link("op_income", "discontinued", abs(disc), RED_LINK)    # ↘ red down
        op_out -= abs(disc)

    link("op_income", "net", max(0, op_out), GREEN)    # ↗ green up to top

    # Other+ → Net (additional income flowing UP into profit stream)
    if has_other_pos:
        link("other", "net", abs(other_non_op), RED_LINK)

    # Disc+ → Net (rare positive discontinued)
    if has_disc and disc > 0:
        link("discontinued", "net", abs(disc), RED_LINK)

    # ═══════════════════════════════════════════
    #  BUILD FIGURE
    # ═══════════════════════════════════════════
    fig = go.Figure(data=[go.Sankey(
        arrangement="fixed",
        node=dict(
            pad=35,
            thickness=22,
            line=dict(color="white", width=1),
            label=labels,
            color=node_colors,
            x=x_pos,
            y=y_pos,
            hovertemplate="%{label}<extra></extra>",
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color=link_colors,
            hovertemplate=(
                "%{source.label} → %{target.label}<br>"
                "$%{value:,.0f}<extra></extra>"
            ),
        ),
    )])

    title = (
        f"<b>{report.company_name} ({report.symbol})</b><br>"
        f"<span style='font-size:18px'>"
        f"{report.fiscal_quarter} Income Statement</span>"
    )

    fig.update_layout(
        title=dict(text=title,
                   font=dict(size=26,
                             family="Arial Black, Arial, sans-serif",
                             color="#1a1a2e"),
                   x=0.5, xanchor="center"),
        font=dict(size=11, family="Arial, sans-serif", color="#444"),
        paper_bgcolor="white",
        plot_bgcolor="white",
        width=1400,
        height=780,
        margin=dict(l=10, r=10, t=100, b=50),
        annotations=[dict(
            text=(f"Period ending: {report.period_end}  •  "
                  "Data: Yahoo Finance  •  Generated by blasifi"),
            x=0.5, y=-0.04,
            xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=10, color="#aaa"),
        )],
    )

    if output_path is None:
        output_path = (
            f"{report.symbol}_"
            f"{report.fiscal_quarter.replace(' ', '_').lower()}_income.html"
        )

    fig.write_html(output_path, auto_open=False)

    png_path = output_path.replace(".html", ".png")
    try:
        fig.write_image(png_path, width=1400, height=780, scale=2)
        print(f"PNG saved: {png_path}")
    except Exception:
        pass

    print(f"Interactive chart saved: {output_path}")
    fig.show()

    return output_path
