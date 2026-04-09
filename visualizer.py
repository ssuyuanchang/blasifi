"""Visualization module: Plotly Sankey income statement chart.

Layout inspired by App Economy Insights:

  GREEN profit stream flows across the TOP, ascending rightward:
    Revenue → Gross Profit → Operating Income → Pretax Income → Net Income

  RED cost streams branch DOWNWARD at each stage:
    Revenue ↘ COGS
    Gross   ↘ OpEx → R&D, SG&A, Amort
    Op Inc  ↘ Other (non-op)
    Pretax  ↘ Tax

  Visual logic: at every step, subtract the red flowing down = green continuing right
"""

import plotly.graph_objects as go
from finance_data import QuarterlyReport

# ── Colour palette ──
REV_NODE    = "rgba(50, 50, 50, 0.60)"
GREEN       = "rgba(44, 160, 44, 0.55)"
GREEN_NODE  = "rgba(44, 160, 44, 0.85)"
GREEN_DARK  = "rgba(35, 139, 69, 0.85)"
RED_LINK    = "rgba(210, 50, 50, 0.35)"
RED_NODE    = "rgba(210, 50, 50, 0.75)"
RED_DARK    = "rgba(180, 40, 40, 0.80)"

# ── Text colours (for annotation labels) ──
GREEN_TEXT  = "rgb(30, 120, 30)"
RED_TEXT    = "rgb(180, 40, 40)"
REV_TEXT    = "rgb(30, 30, 30)"

# ── Column x-positions (5 columns) ──
X0, X1, X2, X3, X4 = 0.01, 0.25, 0.50, 0.75, 0.99

# ── Y-positions: profit on TOP, costs on BOTTOM ──
REV_Y      = 0.48
GROSS_Y    = 0.28
OP_Y       = 0.16
PRETAX_Y   = 0.10
NET_Y      = 0.05
COGS_Y     = 0.88
OPEX_Y     = 0.58
NONOP_Y    = 0.36
TAX_Y      = 0.30


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


def create_sankey_chart(report: QuarterlyReport, output_path: str = None, segment_breakdown=None) -> str:
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
    other_nonop = report.other_non_operating
    pretax = report.pretax_income
    tax   = report.tax_provision
    net   = report.net_income
    other_adj = pretax - tax - net          # minority interests, discontinued ops, etc.

    # Unified unit for the entire chart based on revenue scale
    abs_rev = abs(rev)
    if abs_rev >= 1e9:
        _div, _sfx = 1e9, "B"
    elif abs_rev >= 1e6:
        _div, _sfx = 1e6, "M"
    else:
        _div, _sfx = 1e3, "K"

    def fmt(value):
        neg = value < 0
        v = abs(value) / _div
        if v >= 100:
            core = f"${v:,.0f}{_sfx}"
        elif v >= 1:
            core = f"${v:,.1f}{_sfx}"
        else:
            core = f"${v:.2f}{_sfx}"
        return f"({core})" if neg else core

    labels, node_colors, x_pos, y_pos, text_colors = [], [], [], [], []
    sources, targets, values, link_colors = [], [], [], []
    nid = {}

    def node(name, label, color, x, y, tc=REV_TEXT):
        nid[name] = len(labels)
        labels.append(label)
        node_colors.append(color)
        x_pos.append(x)
        y_pos.append(y)
        text_colors.append(tc)

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
         _join("Revenue", fmt(rev), _yoy_label(report, "revenue")),
         REV_NODE, X0, REV_Y)

    # ═══════════════════════════════════════════
    #  Col 1 — Gross Profit (TOP) + COGS (BOTTOM)
    # ═══════════════════════════════════════════
    gross_color = GREEN_NODE if gross >= 0 else RED_NODE
    gross_tc = GREEN_TEXT if gross >= 0 else RED_TEXT
    node("gross",
         _join("Gross Profit", fmt(gross),
               _margin_label(gross, rev),
               _yoy_label(report, "gross_profit")),
         gross_color, X1, GROSS_Y, tc=gross_tc)

    node("cogs",
         _join("Cost of Revenue", fmt(cogs)),
         RED_DARK, X1, COGS_Y, tc=RED_TEXT)

    # ═══════════════════════════════════════════
    #  Col 2 — Op Income (TOP) + OpEx (BOTTOM)
    # ═══════════════════════════════════════════
    op_color = GREEN_NODE if op_income >= 0 else RED_NODE
    op_tc = GREEN_TEXT if op_income >= 0 else RED_TEXT
    node("op_income",
         _join("Operating Income", fmt(op_income),
               _margin_label(op_income, rev),
               _yoy_label(report, "operating_income")),
         op_color, X2, OP_Y, tc=op_tc)

    node("opex",
         _join("Operating Expenses", fmt(total_opex)),
         RED_NODE, X2, OPEX_Y, tc=RED_TEXT)

    # ═══════════════════════════════════════════
    #  Col 3 — Pretax (TOP) + Non-operating (MID)
    #         + OpEx breakdown (BOTTOM, stacked)
    # ═══════════════════════════════════════════
    pretax_color = GREEN_NODE if pretax >= 0 else RED_NODE
    pretax_tc = GREEN_TEXT if pretax >= 0 else RED_TEXT
    node("pretax",
         _join("Pretax Income", fmt(pretax)),
         pretax_color, X3, PRETAX_Y, tc=pretax_tc)

    has_nonop = abs(other_nonop) > abs(rev) * 0.005
    if has_nonop:
        if other_nonop < 0:
            node("nonop",
                 _join("Non-operating", fmt(abs(other_nonop))),
                 RED_DARK, X3, NONOP_Y, tc=RED_TEXT)
        else:
            node("nonop",
                 _join("Non-op Income", fmt(other_nonop)),
                 GREEN_NODE, X2, NONOP_Y, tc=GREEN_TEXT)

    opex_items = []
    if rd > 0:
        opex_items.append(("rd", rd, "R&D", _pct_of_rev(rd, rev)))
    if sga > 0:
        opex_items.append(("sga", sga, "SG&A", _pct_of_rev(sga, rev)))
    if amort > 0:
        opex_items.append(("amort", amort, "Amortization", _pct_of_rev(amort, rev)))
    if other_opex > 0:
        opex_items.append(("other_opex", other_opex, "Other OpEx", ""))

    opex_ys = _spread(len(opex_items), 0.58, 0.94)
    for i, (name, val, display, extra) in enumerate(opex_items):
        node(name,
             _join(display, fmt(val), extra),
             RED_NODE, X3, opex_ys[i], tc=RED_TEXT)

    # ═══════════════════════════════════════════
    #  Col 4 — Net Income (TOP) + Tax (MID)
    #         + Other Adj (if material)
    # ═══════════════════════════════════════════
    net_color = GREEN_DARK if net >= 0 else RED_NODE
    net_tc = GREEN_TEXT if net >= 0 else RED_TEXT
    node("net",
         _join("Net Income", fmt(net),
               _margin_label(net, rev),
               _yoy_label(report, "net_income")),
         net_color, X4, NET_Y, tc=net_tc)

    tax_is_benefit = tax < 0
    if tax_is_benefit:
        node("tax",
             _join("Tax Benefit", fmt(abs(tax))),
             GREEN_NODE, X3, TAX_Y, tc=GREEN_TEXT)
    else:
        node("tax",
             _join("Tax", fmt(tax)),
             RED_DARK, X4, TAX_Y, tc=RED_TEXT)

    has_adj = abs(other_adj) > abs(rev) * 0.005
    if has_adj:
        if other_adj > 0:
            node("other_adj",
                 _join("Other Adj.", fmt(other_adj)),
                 RED_DARK, X4, 0.50, tc=RED_TEXT)
        else:
            node("other_adj",
                 _join("Other Adj.", fmt(abs(other_adj))),
                 GREEN_NODE, X3, 0.50, tc=GREEN_TEXT)

    # ═══════════════════════════════════════════
    #  LINKS — flow-conserving: each node's
    #  outgoing sum == incoming sum so Revenue
    #  is always the visually largest node.
    # ═══════════════════════════════════════════
    rev_total = abs(rev)
    min_flow = max(rev_total * 0.005, 1)

    # Stage 1: Revenue → COGS + Gross Profit
    g_share, c_share = max(abs(gross), min_flow), max(abs(cogs), min_flow)
    s1 = g_share + c_share
    gross_lv = rev_total * g_share / s1
    cogs_lv = rev_total - gross_lv

    link("revenue", "gross", gross_lv, GREEN)
    link("revenue", "cogs",  cogs_lv,  RED_LINK)

    # Stage 2: Gross Profit → OpEx + Operating Income
    ox_share = max(abs(total_opex), min_flow)
    op_share = max(abs(op_income), min_flow)
    s2 = ox_share + op_share
    opex_lv = gross_lv * ox_share / s2
    op_lv = gross_lv - opex_lv

    link("gross", "opex",      opex_lv, RED_LINK)
    link("gross", "op_income", op_lv,   GREEN)

    # Stage 2b: OpEx → sub-items (proportional)
    opex_sub_total = sum(abs(v) for _, v, _, _ in opex_items) or 1
    for name, val, _, _ in opex_items:
        sub_val = opex_lv * abs(val) / opex_sub_total
        link("opex", name, max(sub_val, 1), RED_LINK)

    # Stage 3: Operating Income → Pretax [+ Non-operating]
    if has_nonop and other_nonop < 0:
        p_share = max(abs(pretax), min_flow)
        no_share = max(abs(other_nonop), min_flow)
        s3 = p_share + no_share
        pretax_lv = op_lv * p_share / s3
        nonop_lv = op_lv - pretax_lv
        link("op_income", "pretax", pretax_lv, GREEN)
        link("op_income", "nonop", nonop_lv, RED_LINK)
    elif has_nonop and other_nonop > 0:
        link("op_income", "pretax", op_lv, GREEN)
        nonop_lv = op_lv * abs(other_nonop) / max(abs(op_income), 1)
        link("nonop", "pretax", nonop_lv, GREEN)
        pretax_lv = op_lv + nonop_lv
    else:
        link("op_income", "pretax", op_lv, GREEN)
        pretax_lv = op_lv

    # Stage 4: Pretax → Net Income [+ Tax / Other Adj]
    #
    # Outflows from Pretax (red): Tax (when >= 0), Other Adj (when > 0)
    # Inflows to Net (green):     Tax Benefit (when < 0), Other Adj (when < 0)

    # --- outflows: things that leave Pretax ---
    outflows = [("net", abs(net))]
    if not tax_is_benefit:
        outflows.append(("tax", max(abs(tax), min_flow)))
    if has_adj and other_adj > 0:
        outflows.append(("other_adj", abs(other_adj)))

    out_total = sum(max(v, min_flow) for _, v in outflows)
    allocated = 0
    for i, (nm, v) in enumerate(outflows):
        if i == len(outflows) - 1:
            lv = pretax_lv - allocated
        else:
            lv = pretax_lv * max(v, min_flow) / out_total
            allocated += lv
        if nm == "net":
            net_lv = lv
            link("pretax", nm, lv, GREEN if net >= 0 else RED_LINK)
        elif nm == "tax":
            link("pretax", nm, lv, RED_LINK)
        elif nm == "other_adj":
            link("pretax", nm, lv, RED_LINK)

    # --- inflows: things that flow INTO Net Income ---
    if tax_is_benefit:
        tax_lv = max(net_lv * abs(tax) / max(abs(net), 1), min_flow)
        link("tax", "net", tax_lv, GREEN)
    if has_adj and other_adj < 0:
        adj_lv = net_lv * abs(other_adj) / max(abs(net), 1)
        link("other_adj", "net", adj_lv, GREEN)

    # ═══════════════════════════════════════════
    #  BUILD FIGURE
    # ═══════════════════════════════════════════
    fig = go.Figure(data=[go.Sankey(
        arrangement="fixed",
        node=dict(
            pad=35,
            thickness=22,
            line=dict(color="white", width=1),
            label=[""] * len(labels),
            customdata=labels,
            color=node_colors,
            x=x_pos,
            y=y_pos,
            hovertemplate="%{customdata}<extra></extra>",
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

    ann_list = []
    ANN_Y_OFFSET = 0.03
    for i in range(len(labels)):
        sx, sy = x_pos[i], y_pos[i]
        py = min(1.0 - sy + ANN_Y_OFFSET, 0.98)

        if sx < 0.15:
            xa, align = "left", "left"
        elif sx > 0.85:
            xa, align = "right", "right"
        else:
            xa, align = "center", "center"

        lines = labels[i].split("\n")
        if len(lines) >= 2:
            header = f"<b>{lines[0]}  {lines[1]}</b>"
            rest = "  ".join(l for l in lines[2:] if l)
            ann_text = header + (f"<br>{rest}" if rest else "")
        elif lines:
            ann_text = f"<b>{lines[0]}</b>"
        else:
            continue

        ann_list.append(dict(
            x=sx, y=py,
            xref="paper", yref="paper",
            text=ann_text,
            showarrow=False,
            font=dict(size=13, color=text_colors[i],
                      family="Arial, sans-serif"),
            xanchor=xa, yanchor="bottom", align=align,
        ))

    ann_list.append(dict(
        text=(f"Period ending: {report.period_end}  •  "
              "Data: Yahoo Finance  •  Generated by blasifi"),
        x=0.5, y=-0.04,
        xref="paper", yref="paper",
        showarrow=False,
        font=dict(size=10, color="#aaa"),
    ))

    fig.update_layout(
        title=dict(text=title,
                   font=dict(size=26,
                             family="Arial Black, Arial, sans-serif",
                             color="#1a1a2e"),
                   x=0.5, xanchor="center"),
        font=dict(size=11, family="Arial, sans-serif", color="#444"),
        paper_bgcolor="white",
        plot_bgcolor="white",
        width=1500,
        height=580,
        margin=dict(l=10, r=10, t=100, b=40),
        annotations=ann_list,
    )

    if output_path is None:
        output_path = (
            f"{report.symbol}_"
            f"{report.fiscal_quarter.replace(' ', '_').lower()}_income.html"
        )

    import os
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    fig.write_html(output_path, auto_open=False)

    png_path = output_path.replace(".html", ".png")
    try:
        fig.write_image(png_path, width=1500, height=580, scale=2)
    except Exception:
        pass

    fig.show()

    return output_path
