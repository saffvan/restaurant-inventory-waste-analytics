"""
engine.py
---------
This is the "brain" of the app. It contains no UI code at all — just
pure calculation functions that the Streamlit pages will call.
"""

from datetime import datetime, date, timedelta
import pandas as pd
from db import get_connection


# ======================================================================
# SECTION 1: BASIC HELPERS
# ======================================================================

def today_str():
    return date.today().isoformat()


def days_between(date1_str, date2_str):
    d1 = datetime.strptime(date1_str, "%Y-%m-%d").date()
    d2 = datetime.strptime(date2_str, "%Y-%m-%d").date()
    return (d2 - d1).days


# ======================================================================
# SECTION 3: CURRENT STOCK CALCULATION
# ======================================================================

def get_current_stock(ingredient_id, conn=None):
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(SUM(quantity_remaining), 0) AS total
        FROM batches
        WHERE ingredient_id = ?
    """, (ingredient_id,))
    total = cur.fetchone()["total"]
    if own_conn:
        conn.close()
    return round(total, 2)


# ======================================================================
# SECTION 4: REORDER POINT & STATUS
# ======================================================================

def get_average_daily_usage(ingredient_id, lookback_days=14, conn=None):
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    cur = conn.cursor()
    cutoff_date = (date.today() - timedelta(days=lookback_days)).isoformat()
    cur.execute("""
        SELECT COALESCE(SUM(quantity_used), 0) AS total
        FROM usage_log
        WHERE ingredient_id = ?
          AND usage_date >= ?
    """, (ingredient_id, cutoff_date))
    total = cur.fetchone()["total"]

    cur.execute("SELECT opening_stock_date FROM ingredients WHERE ingredient_id = ?", (ingredient_id,))
    row = cur.fetchone()
    if own_conn:
        conn.close()

    days_tracked = lookback_days
    if row and row["opening_stock_date"]:
        try:
            tracked_since = datetime.strptime(row["opening_stock_date"], "%Y-%m-%d").date()
            days_tracked = (date.today() - tracked_since).days + 1
        except ValueError:
            pass

    effective_days = max(1, min(lookback_days, days_tracked))
    return round(total / effective_days, 2)


def get_reorder_status(ingredient_id, conn=None):
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    cur = conn.cursor()
    cur.execute("SELECT reorder_period_days FROM ingredients WHERE ingredient_id = ?", (ingredient_id,))
    row = cur.fetchone()
    reorder_period = row["reorder_period_days"] if row else 7

    avg_daily_usage = get_average_daily_usage(ingredient_id, conn=conn)
    reorder_point = round(avg_daily_usage * reorder_period, 2)
    current_stock = get_current_stock(ingredient_id, conn=conn)

    if own_conn:
        conn.close()

    return {
        "current_stock": current_stock,
        "avg_daily_usage": avg_daily_usage,
        "reorder_point": reorder_point,
        "needs_reorder": current_stock <= reorder_point
    }


# ======================================================================
# SECTION 5: EXPIRY CLASSIFICATION
# ======================================================================

def classify_batch_expiry(expiry_date_str, near_expiry_days, critical_expiry_days):
    days_left = days_between(today_str(), expiry_date_str)

    if days_left < 0:
        return "Expired"
    elif days_left <= critical_expiry_days:
        return "Critical"
    elif days_left <= near_expiry_days:
        return "Near-Expiry"
    else:
        return "OK"


def get_all_batches_with_status():
    conn = get_connection()
    query = """
        SELECT
            b.batch_id,
            i.ingredient_id,
            i.name AS ingredient_name,
            c.name AS category_name,
            i.unit,
            b.purchase_date,
            b.expiry_date,
            b.quantity_remaining,
            b.unit_cost,
            c.near_expiry_days,
            c.critical_expiry_days
        FROM batches b
        JOIN ingredients i ON b.ingredient_id = i.ingredient_id
        JOIN categories c ON i.category_id = c.category_id
        WHERE b.quantity_remaining > 0
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        return df

    df["status"] = df.apply(
        lambda row: classify_batch_expiry(
            row["expiry_date"], row["near_expiry_days"], row["critical_expiry_days"]
        ),
        axis=1
    )
    df["days_left"] = df["expiry_date"].apply(lambda d: days_between(today_str(), d))
    return df
