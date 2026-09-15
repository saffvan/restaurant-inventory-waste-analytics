"""
app.py
------
This is the ENTRY POINT of the Streamlit app — the Home page.
"""

import streamlit as st
from datetime import date
from db import init_db
from engine import (
    get_dashboard_summary,
    get_all_batches_with_status,
    get_expiry_alert_items,
    get_reorder_alert_items,
    get_period_bounds,
)
from style import inject_custom_css, show_footer

st.set_page_config(
    page_title="Restaurant Inventory & Waste Analytics",
    page_icon="🍽️",
    layout="wide"
)
inject_custom_css()

init_db()

st.markdown("""
    <div style="
        background: linear-gradient(135deg, #0C447C 0%, #185FA5 100%);
        border-radius: 16px;
        padding: 32px 36px;
        margin-bottom: 24px;
    ">
        <div style="font-size: 28px; font-weight: 600; color: #FFFFFF; margin-bottom: 6px;">
            🍽️ Restaurant Inventory & Food Waste Analytics
        </div>
        <div style="font-size: 15px; color: #D6E8F7; max-width: 640px;">
            Track ingredient stock, purchases, usage, and waste — with FEFO-based
            batch consumption, expiry alerts, and live cost analytics.
        </div>
    </div>
""", unsafe_allow_html=True)

month_start, _ = get_period_bounds("This Month")
summary = get_dashboard_summary(start_date=month_start, end_date=date.today())

# ----------------------------------------------------------------------
# NOTIFICATION BELL
# Alerts live inside a bell icon with a badge count. Each alert names
# the actual ingredient/batch affected (not just a count) and gives a
# button that jumps straight to the page where you'd act on it — Waste
# for anything expired/critical, Purchases for anything needing
# reorder — with that ingredient pre-selected.
#
# PRIORITY ORDER (fix): alerts are now shown in a deliberate urgency
# order — Expired (food-safety, act now) > Critical (expiring within
# hours/a day) > Reorder needed (could halt service soon) >
# Near-Expiry (plan ahead) — instead of the previous count-only list
# with no real ordering logic. Each tier is capped at MAX_PER_TIER so
# the bell itself can't turn into the same "long unreadable list"
# problem as the old Dashboard expiry section; anything beyond that
# is summarized with a link to the Dashboard, which shows everything.
# ----------------------------------------------------------------------
MAX_PER_TIER = 4

expiry_alerts = get_expiry_alert_items()
reorder_alerts = get_reorder_alert_items()
expired_items = [a for a in expiry_alerts if a["status"] == "Expired"]
critical_items = [a for a in expiry_alerts if a["status"] == "Critical"]
near_items = [a for a in expiry_alerts if a["status"] == "Near-Expiry"]
total_alerts = len(expiry_alerts) + len(reorder_alerts)


def _go_to(page_path, ingredient_id):
    st.session_state["prefill_ingredient_id"] = ingredient_id
    st.switch_page(page_path)


def _render_tier(items, label_fn, button_label, page_path, key_prefix, box_fn):
    shown, remaining = items[:MAX_PER_TIER], items[MAX_PER_TIER:]
    for item in shown:
        c1, c2 = st.columns([3, 2])
        box_fn(c1, label_fn(item))
        if c2.button(button_label, key=f"{key_prefix}_{item.get('batch_id', item.get('ingredient_id'))}"):
            _go_to(page_path, item["ingredient_id"])
    if remaining:
        st.caption(f"+{len(remaining)} more — see the Dashboard for the full list.")


_, bell_col = st.columns([6, 1])
with bell_col:
    bell_label = f"🔔 {total_alerts}" if total_alerts > 0 else "🔔"
    with st.popover(bell_label, width="stretch"):
        st.markdown("**Notifications**")
        if total_alerts == 0:
            st.success("✅ No urgent alerts right now.")
        else:
            if expired_items:
                st.markdown(f"**🚨 Expired — discard now ({len(expired_items)})**")
                _render_tier(
                    expired_items,
                    lambda it: f"**{it['ingredient_name']}** expired {abs(it['days_left'])}d ago ({it['quantity_remaining']} {it['unit']})",
                    "Log Waste →", "pages/5_Waste.py", "bell_exp", lambda col, txt: col.error(txt)
                )
            if critical_items:
                st.markdown(f"**⏳ Critical — expiring very soon ({len(critical_items)})**")
                _render_tier(
                    critical_items,
                    lambda it: f"**{it['ingredient_name']}** expires in {it['days_left']}d ({it['quantity_remaining']} {it['unit']})",
                    "Use/Waste →", "pages/5_Waste.py", "bell_crit", lambda col, txt: col.error(txt)
                )
            if reorder_alerts:
                st.markdown(f"**🔔 Reorder needed ({len(reorder_alerts)})**")
                _render_tier(
                    reorder_alerts,
                    lambda it: f"**{it['name']}** low: {it['current_stock']} {it['unit']}" + (
                        f" — ~{it['days_to_stockout']}d left" if it['days_to_stockout'] is not None else ""
                    ),
                    "Log Purchase →", "pages/3_Purchases.py", "bell_reorder", lambda col, txt: col.error(txt)
                )
            if near_items:
                st.markdown(f"**⚠️ Near-Expiry — plan ahead ({len(near_items)})**")
                _render_tier(
                    near_items,
                    lambda it: f"**{it['ingredient_name']}** expires in {it['days_left']}d ({it['quantity_remaining']} {it['unit']})",
                    "View →", "pages/5_Waste.py", "bell_near", lambda col, txt: col.warning(txt)
                )

col1, col2, col3 = st.columns(3)
col1.metric("Total Ingredients Tracked", summary["total_ingredients"])
col2.metric(
    "Waste Cost (This Month)", f"₹{summary['total_waste_cost']:,.2f}",
    help=f"All-time total: ₹{summary['all_time_waste_cost']:,.2f} — see Dashboard for other time ranges."
)
col3.metric("Items Needing Reorder", summary["reorder_needed_count"])

st.write("")
st.subheader("Get started")
st.caption("Set these up in order — each page builds on the one before it.")

nav_col1, nav_col2, nav_col3 = st.columns(3)

with nav_col1:
    with st.container(border=True):
        st.markdown('<div style="width:32px;height:32px;border-radius:8px;background:#E6F1FB;display:flex;align-items:center;justify-content:center;font-size:16px;margin-bottom:6px;">🗂️</div>', unsafe_allow_html=True)
        st.page_link("pages/1_Categories.py", label="**1. Categories**")
        st.caption("Group ingredients and set expiry alert thresholds.")

with nav_col2:
    with st.container(border=True):
        st.markdown('<div style="width:32px;height:32px;border-radius:8px;background:#EAF3DE;display:flex;align-items:center;justify-content:center;font-size:16px;margin-bottom:6px;">🧂</div>', unsafe_allow_html=True)
        st.page_link("pages/2_Ingredients.py", label="**2. Ingredients**")
        st.caption("Add ingredients with opening stock and reorder settings.")

with nav_col3:
    with st.container(border=True):
        st.markdown('<div style="width:32px;height:32px;border-radius:8px;background:#FAEEDA;display:flex;align-items:center;justify-content:center;font-size:16px;margin-bottom:6px;">🛒</div>', unsafe_allow_html=True)
        st.page_link("pages/3_Purchases.py", label="**3. Purchases**")
        st.caption("Log purchases — each one creates a new expiry-dated batch.")

nav_col4, nav_col5, nav_col6 = st.columns(3)

with nav_col4:
    with st.container(border=True):
        st.markdown('<div style="width:32px;height:32px;border-radius:8px;background:#FAECE7;display:flex;align-items:center;justify-content:center;font-size:16px;margin-bottom:6px;">🍳</div>', unsafe_allow_html=True)
        st.page_link("pages/4_Usage.py", label="**4. Usage**")
        st.caption("Log cooking consumption — stock deducted automatically via FEFO.")

with nav_col5:
    with st.container(border=True):
        st.markdown('<div style="width:32px;height:32px;border-radius:8px;background:#FCEBEB;display:flex;align-items:center;justify-content:center;font-size:16px;margin-bottom:6px;">🗑️</div>', unsafe_allow_html=True)
        st.page_link("pages/5_Waste.py", label="**5. Waste**")
        st.caption("Log discarded ingredients with automatic cost calculation.")

with nav_col6:
    with st.container(border=True):
        st.markdown('<div style="width:32px;height:32px;border-radius:8px;background:#EEEDFE;display:flex;align-items:center;justify-content:center;font-size:16px;margin-bottom:6px;">📊</div>', unsafe_allow_html=True)
        st.page_link("pages/6_Dashboard.py", label="**6. Dashboard**")
        st.caption("View stock health, expiry risk, and waste analytics.")

show_footer()
