"""
pages/6_Dashboard.py
-----------------------
The analytics dashboard.

DESIGN NOTE (fix): waste-cost figures used to be shown only as a
single all-time running total, which only ever grows and tells a
manager nothing about whether this week/month is better or worse
than usual. This page now defaults to "This Month", lets you pick
any period, and shows the % change vs. the previous period of equal
length plus waste-cost as a % of what was purchased in that window —
the actual number a manager would care about.

Alerts (expiry risk, reorder) are also now named per-item instead of
just counted, and each has a button that jumps to the page where
you'd act on it with that ingredient pre-selected.
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
import plotly.express as px
from db import get_connection
from engine import (
    get_dashboard_summary,
    get_reorder_status,
    get_all_batches_with_status,
    get_waste_summary,
    get_top_wasted_ingredients,
    get_period_bounds,
    get_total_purchase_cost,
    get_avg_daily_waste_cost,
    get_expiry_alert_items,
    get_reorder_alert_items,
)
from style import inject_custom_css, show_footer

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
inject_custom_css()
st.title("📊 Analytics Dashboard")
st.markdown("Live overview of stock health, expiry risk, and waste costs.")

st.divider()

# ----------------------------------------------------------------------
# PERIOD SELECTOR — everything under "Waste Cost Analytics" below
# respects this. Reorder/expiry status stays live (point-in-time) since
# "currently needs reordering" isn't a thing you scope to a date range.
# ----------------------------------------------------------------------
PERIOD_OPTIONS = ["Today", "This Week", "This Month", "Last 30 Days", "All Time", "Custom"]
period_choice = st.radio("Waste analytics period", PERIOD_OPTIONS, index=2, horizontal=True)

custom_start, custom_end = None, None
if period_choice == "Custom":
    c1, c2 = st.columns(2)
    custom_start = c1.date_input("From", value=date.today() - timedelta(days=30))
    custom_end = c2.date_input("To", value=date.today())

start_date, end_date = get_period_bounds(period_choice, custom_start, custom_end)
if start_date and end_date:
    st.caption(f"📅 Covers **{start_date.isoformat()}** to **{end_date.isoformat()}** ({(end_date - start_date).days + 1} days).")

# Previous period of equal length, for the trend comparison.
if start_date and end_date:
    span_days = (end_date - start_date).days + 1
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=span_days - 1)
else:
    prev_start, prev_end = None, None

summary = get_dashboard_summary(start_date=start_date, end_date=end_date)
period_waste_df = get_waste_summary(start_date, end_date)
period_waste_cost = round(period_waste_df["waste_cost"].sum(), 2) if not period_waste_df.empty else 0.0

prev_waste_df = get_waste_summary(prev_start, prev_end) if prev_start else pd.DataFrame()
prev_waste_cost = round(prev_waste_df["waste_cost"].sum(), 2) if not prev_waste_df.empty else None

purchase_cost = get_total_purchase_cost(start_date, end_date)
waste_pct_of_spend = round((period_waste_cost / purchase_cost) * 100, 1) if purchase_cost > 0 else None

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Ingredients", summary["total_ingredients"])

delta_str = None
if prev_waste_cost is not None:
    if prev_waste_cost > 0:
        pct_change = round(((period_waste_cost - prev_waste_cost) / prev_waste_cost) * 100, 1)
        delta_str = f"{pct_change:+.1f}% vs previous period"
    elif period_waste_cost > 0:
        delta_str = "vs ₹0 previous period"
col2.metric(
    f"Waste Cost ({period_choice})", f"₹{period_waste_cost:,.2f}",
    delta=delta_str, delta_color="inverse"
)

col3.metric("Items Needing Reorder", summary["reorder_needed_count"])
col4.metric(
    "Waste as % of Spend",
    f"{waste_pct_of_spend}%" if waste_pct_of_spend is not None else "—",
    help="Waste cost ÷ purchase cost for the selected period — the figure that actually shows whether waste is under control, independent of how much business grew."
)

st.caption(
    f"All-time waste cost: ₹{summary['all_time_waste_cost']:,.2f} · "
    f"Average ₹{get_avg_daily_waste_cost():,.2f}/day since your first logged waste entry."
)

st.divider()


def _go_to(page_path, ingredient_id):
    st.session_state["prefill_ingredient_id"] = ingredient_id
    st.switch_page(page_path)


st.subheader("🔔 Reorder Alerts")

reorder_items = get_reorder_alert_items()
if not reorder_items:
    st.success("No ingredients currently need reordering.")
else:
    reorder_search = st.text_input(
        "🔎 Search reorder alerts", key="reorder_search", placeholder="Filter by ingredient name…"
    )
    visible_reorder = (
        [it for it in reorder_items if reorder_search.lower() in it["name"].lower()]
        if reorder_search else reorder_items
    )
    if not visible_reorder:
        st.caption("No reorder alerts match that search.")
    else:
        MAX_REORDER_ROWS = 8
        for item in visible_reorder[:MAX_REORDER_ROWS]:
            c1, c2, c3, c4, c5 = st.columns([2.5, 1.5, 1.5, 1.5, 1.5])
            c1.markdown(f"**{item['name']}**")
            c2.write(f"{item['current_stock']} {item['unit']}")
            c3.write(
                f"~{item['days_to_stockout']}d to stockout" if item["days_to_stockout"] is not None
                else "usage rate unknown"
            )
            c4.write(f"{item['avg_daily_usage']}/day avg")
            if c5.button("Log Purchase →", key=f"dash_reorder_{item['ingredient_id']}"):
                _go_to("pages/3_Purchases.py", item["ingredient_id"])
        if len(visible_reorder) > MAX_REORDER_ROWS:
            st.caption(f"+{len(visible_reorder) - MAX_REORDER_ROWS} more matching — narrow your search to see them.")

st.divider()

st.subheader("⏳ Expiry Risk — Items Needing Attention")

expiry_items = get_expiry_alert_items()
batches_df = get_all_batches_with_status()

if batches_df.empty:
    st.info("No active batches to analyze yet.")
else:
    col1, col2 = st.columns([1, 1.3])

    with col1:
        status_counts = batches_df["status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]
        fig1 = px.pie(
            status_counts, names="Status", values="Count",
            title="Batches by Expiry Status",
            color="Status",
            color_discrete_map={
                "OK": "#2ecc71", "Near-Expiry": "#f39c12",
                "Critical": "#e74c3c", "Expired": "#7f8c8d"
            }
        )
        st.plotly_chart(fig1, width="stretch")

    with col2:
        if not expiry_items:
            st.success("No batches are near expiry right now.")
        else:
            # FIX: this used to be one long, flat list mixing every
            # urgency level together — with more than a handful of
            # ingredients it became a wall of text to scan. Splitting
            # into tabs by urgency (with counts in the tab label) plus
            # a shared search lets you jump straight to what matters,
            # and each tab is capped with a "show more" expander
            # instead of dumping everything on screen at once.
            expiry_search = st.text_input(
                "🔎 Search expiring items", key="expiry_search", placeholder="Filter by ingredient name…"
            )

            def _filtered(items, status):
                pool = [i for i in items if i["status"] == status]
                if expiry_search:
                    pool = [i for i in pool if expiry_search.lower() in i["ingredient_name"].lower()]
                return pool

            expired_tab_items = _filtered(expiry_items, "Expired")
            critical_tab_items = _filtered(expiry_items, "Critical")
            near_tab_items = _filtered(expiry_items, "Near-Expiry")

            tabs = st.tabs([
                f"🚨 Expired ({len(expired_tab_items)})",
                f"⏳ Critical ({len(critical_tab_items)})",
                f"⚠️ Near-Expiry ({len(near_tab_items)})",
            ])
            MAX_VISIBLE = 6
            for tab, items, box_fn in zip(
                tabs,
                [expired_tab_items, critical_tab_items, near_tab_items],
                [st.error, st.error, st.warning],
            ):
                with tab:
                    if not items:
                        st.caption("Nothing here.")
                        continue

                    def _render_row(item):
                        r1, r2, r3 = st.columns([3, 1.6, 1.3])
                        days_txt = (
                            f"expired {abs(item['days_left'])}d ago" if item["days_left"] < 0
                            else f"{item['days_left']}d left"
                        )
                        r1.markdown(f"**{item['ingredient_name']}** ({item['category_name']}) — {days_txt}")
                        r2.write(f"{item['quantity_remaining']} {item['unit']} · ₹{item['cost_at_risk']:,.2f} at risk")
                        if r3.button("Log Waste →", key=f"dash_exp_{item['batch_id']}"):
                            _go_to("pages/5_Waste.py", item["ingredient_id"])

                    for item in items[:MAX_VISIBLE]:
                        _render_row(item)
                    if len(items) > MAX_VISIBLE:
                        with st.expander(f"Show {len(items) - MAX_VISIBLE} more"):
                            for item in items[MAX_VISIBLE:]:
                                _render_row(item)

st.divider()

st.subheader("🏆 Top Wasted Ingredients (by cost)")

top_wasted_df = get_top_wasted_ingredients(limit=5, start_date=start_date, end_date=end_date)

if top_wasted_df.empty:
    st.info(f"No waste logged for **{period_choice}** — this ranking will appear once you log some.")
else:
    display_top = top_wasted_df.rename(columns={
        "ingredient_name": "Ingredient",
        "total_quantity_wasted": "Total Quantity Wasted",
        "total_waste_cost": "Total Waste Cost (₹)"
    })

    col1, col2 = st.columns([1, 1])
    with col1:
        fig_top = px.bar(
            top_wasted_df, x="ingredient_name", y="total_waste_cost",
            title=f"Top 5 Ingredients by Waste Cost ({period_choice})",
            labels={"ingredient_name": "Ingredient", "total_waste_cost": "Waste Cost (₹)"},
            color="total_waste_cost", color_continuous_scale="Reds"
        )
        st.plotly_chart(fig_top, width="stretch")
    with col2:
        st.dataframe(display_top, width="stretch", hide_index=True)

    # Only surface the "biggest source of waste cost" insight when there's
    # an actual cost behind it — otherwise (e.g. all logged waste has ₹0
    # cost, such as opening-stock batches entered with no unit cost) the
    # caption would misleadingly call a ₹0.00 item the "biggest" problem.
    if top_wasted_df.iloc[0]["total_waste_cost"] > 0:
        st.caption(
            f"💡 **{top_wasted_df.iloc[0]['ingredient_name']}** is your single biggest source of "
            f"waste cost this period (₹{top_wasted_df.iloc[0]['total_waste_cost']:.2f}) — worth investigating "
            f"whether purchase quantities or storage practices need adjusting."
        )

st.divider()

st.subheader("💸 Waste Cost Analytics")

waste_df = get_waste_summary(start_date, end_date)

if waste_df.empty:
    st.info(f"No waste logged for **{period_choice}** — analytics will appear here once you log some.")
else:
    col1, col2 = st.columns(2)

    with col1:
        by_category = waste_df.groupby("category_name")["waste_cost"].sum().reset_index()
        fig2 = px.bar(
            by_category, x="category_name", y="waste_cost",
            title=f"Waste Cost by Category ({period_choice})",
            labels={"category_name": "Category", "waste_cost": "Waste Cost (₹)"},
            color="category_name"
        )
        st.plotly_chart(fig2, width="stretch")

    with col2:
        by_reason = waste_df.groupby("reason")["waste_cost"].sum().reset_index()
        fig3 = px.pie(
            by_reason, names="reason", values="waste_cost",
            title=f"Waste Cost by Reason ({period_choice})"
        )
        st.plotly_chart(fig3, width="stretch")

    waste_df["waste_date"] = pd.to_datetime(waste_df["waste_date"])
    by_date = waste_df.groupby("waste_date")["waste_cost"].sum().reset_index()
    fig4 = px.line(
        by_date, x="waste_date", y="waste_cost",
        title="Waste Cost Over Time",
        labels={"waste_date": "Date", "waste_cost": "Waste Cost (₹)"},
        markers=True
    )
    st.plotly_chart(fig4, width="stretch")

    st.download_button(
        label="📥 Download Waste Data for This Period (CSV)",
        data=waste_df.to_csv(index=False).encode("utf-8"),
        file_name=f"waste_analytics_{period_choice.lower().replace(' ', '_')}.csv",
        mime="text/csv"
    )
show_footer()
