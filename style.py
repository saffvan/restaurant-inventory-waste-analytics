"""
style.py
---------
Small shared styling tweaks applied on top of the config.toml theme.
Streamlit re-runs each page as a fresh script, so this function must
be called at the top of EVERY page (app.py and each file in pages/)
to keep the look consistent everywhere.
"""

import streamlit as st


def inject_custom_css():
    st.markdown("""
        <style>
        /* Rounded corners + subtle shadow on metric cards */
        div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            padding: 14px 16px;
            box-shadow: 0 1px 3px rgba(12, 34, 59, 0.06);
        }

        /* Rounded, slightly bolder buttons */
        div.stButton > button, div.stFormSubmitButton > button {
            border-radius: 8px;
            font-weight: 500;
        }

        /* Rounded corners on tables/dataframes */
        div[data-testid="stDataFrame"] {
            border-radius: 10px;
            overflow: hidden;
        }

        /* Hide the default "Made with Streamlit" footer for a cleaner look */
        footer {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)


def flash(message, kind="success"):
    """
    Queue a one-shot message to be shown AFTER the next st.rerun().

    Streamlit's st.rerun() immediately halts the current script run,
    so anything rendered earlier in that run (like a plain st.success()
    call) is discarded before the user ever sees it. Stashing the
    message in st.session_state lets it survive the rerun; show_flash()
    (called near the top of the page) then displays it once and clears
    it, so it doesn't reappear on the next unrelated rerun.

    kind: "success", "error", "warning", or "info" (any valid
    st.<kind>() method name).
    """
    st.session_state["_flash"] = (kind, message)


def show_flash():
    """Display and clear a pending flash() message, if any. Call this
    near the top of a page, after inject_custom_css()/title."""
    if "_flash" in st.session_state:
        kind, message = st.session_state.pop("_flash")
        getattr(st, kind)(message)


def show_footer():
    """
    A small personal/professional footer, shown at the bottom of every
    page in place of Streamlit's default "Made with Streamlit" footer
    (which is hidden via CSS above). Call this as the LAST line of
    every page.
    """
    st.markdown("""
        <div style="
            margin-top: 32px;
            padding-top: 12px;
            border-top: 1px solid #E2E8F0;
            font-size: 12px;
            color: #94A3B8;
            text-align: center;
        ">
            Built by Saf — MCA Mini Project 2026
        </div>
    """, unsafe_allow_html=True)


def history_filter_controls(df, date_col, name_col, category_col=None, key_prefix="hist", default_period="Last 30 Days"):
    """
    FIX: Purchases/Usage/Waste history tables kept every record ever
    logged with no way to narrow them down, so after weeks of use the
    table becomes a long, hard-to-scan wall of rows. This renders a
    compact search + category + time-range bar above such a table and
    returns the filtered DataFrame — old records are NEVER deleted
    (that would break the audit trail these tables exist for), they're
    just not all shown by default. "All Time" always remains one click
    away, and the CSV download still reflects whatever is filtered.
    """
    from datetime import date as _date, timedelta as _timedelta

    if df.empty:
        return df

    periods = ["Last 7 Days", "Last 30 Days", "Last 90 Days", "All Time"]
    c1, c2, c3 = st.columns([2, 1.3, 1.7]) if category_col else st.columns([2.5, 1.5])

    with c1:
        search = st.text_input(
            "🔎 Search ingredient", key=f"{key_prefix}_search", placeholder="Type to filter…"
        )
    if category_col:
        with c2:
            cats = ["All"] + sorted(df[category_col].dropna().unique().tolist())
            category = st.selectbox("Category", cats, key=f"{key_prefix}_cat")
        period_col = c3
    else:
        category = "All"
        period_col = c2

    with period_col:
        period = st.selectbox(
            "Show", periods, index=periods.index(default_period), key=f"{key_prefix}_period"
        )

    filtered = df.copy()
    if search:
        filtered = filtered[filtered[name_col].str.contains(search, case=False, na=False)]
    if category_col and category != "All":
        filtered = filtered[filtered[category_col] == category]
    if period != "All Time":
        days = {"Last 7 Days": 7, "Last 30 Days": 30, "Last 90 Days": 90}[period]
        cutoff = (_date.today() - _timedelta(days=days - 1)).isoformat()
        filtered = filtered[filtered[date_col] >= cutoff]

    if len(filtered) < len(df):
        st.caption(f"Showing {len(filtered)} of {len(df)} record(s) — change **Show** above to widen the range.")
    else:
        st.caption(f"Showing all {len(df)} record(s).")

    return filtered
