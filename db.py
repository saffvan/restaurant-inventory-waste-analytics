"""
db.py
------
This file is responsible for ONE thing: setting up the SQLite database
and giving the rest of the app a way to connect to it.
"""

import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "inventory.db")


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            near_expiry_days INTEGER NOT NULL DEFAULT 3,
            critical_expiry_days INTEGER NOT NULL DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ingredients (
            ingredient_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            unit TEXT NOT NULL,
            opening_stock REAL NOT NULL DEFAULT 0,
            opening_stock_date TEXT NOT NULL,
            reorder_period_days INTEGER NOT NULL DEFAULT 7,
            FOREIGN KEY (category_id) REFERENCES categories(category_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS batches (
            batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ingredient_id INTEGER NOT NULL,
            purchase_date TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            quantity_purchased REAL NOT NULL,
            quantity_remaining REAL NOT NULL,
            unit_cost REAL NOT NULL,
            is_opening_stock INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (ingredient_id) REFERENCES ingredients(ingredient_id)
        )
    """)

    conn.commit()
    conn.close()
    print(f"Database initialized successfully -> {DB_NAME}")


if __name__ == "__main__":
    init_db()
