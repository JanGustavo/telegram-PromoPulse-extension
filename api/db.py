import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "sessions" / "promopulse.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id BIGINT,
                group_title TEXT,
                username TEXT,
                message TEXT,
                message_id INTEGER,
                offer_score INTEGER,
                offer_categories TEXT,
                extracted_price REAL,
                link TEXT,
                clean_title TEXT,
                image_url TEXT,
                price_drop_percentage INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migration to add image_url if database already exists
        try:
            conn.execute("ALTER TABLE alerts ADD COLUMN image_url TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists

        # Migration to add price_drop_percentage if database already exists
        try:
            conn.execute("ALTER TABLE alerts ADD COLUMN price_drop_percentage INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # column already exists

        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_price ON alerts(extracted_price)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_message_id ON alerts(message_id)")
        conn.commit()


def save_config(config: dict):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO system_config (key, value) VALUES ('watch_config', ?)",
            (json.dumps(config),),
        )
        conn.commit()


def load_config(default_config: dict) -> dict:
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM system_config WHERE key = 'watch_config'").fetchone()
        if row:
            try:
                loaded = json.loads(row[0])
                merged = default_config.copy()
                merged.update(loaded)
                return merged
            except Exception:
                pass
        return default_config


def save_monitoring_state(active: bool, group_ids: list[int]):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO system_config (key, value) VALUES ('monitoring_active', ?)",
            (json.dumps(active),),
        )
        conn.execute(
            "INSERT OR REPLACE INTO system_config (key, value) VALUES ('active_group_ids', ?)",
            (json.dumps(group_ids),),
        )
        conn.commit()


def load_monitoring_state() -> tuple[bool, list[int]]:
    with get_connection() as conn:
        row_active = conn.execute("SELECT value FROM system_config WHERE key = 'monitoring_active'").fetchone()
        row_groups = conn.execute("SELECT value FROM system_config WHERE key = 'active_group_ids'").fetchone()
        active = False
        groups = []
        if row_active:
            try:
                active = json.loads(row_active[0])
            except Exception:
                pass
        if row_groups:
            try:
                groups = json.loads(row_groups[0])
            except Exception:
                pass
        return active, groups


def get_min_historical_price(clean_title: str) -> float | None:
    if not clean_title or clean_title == "Produto não identificado":
        return None
    with get_connection() as conn:
        row = conn.execute(
            "SELECT MIN(extracted_price) FROM alerts WHERE clean_title = ? AND extracted_price IS NOT NULL",
            (clean_title,),
        ).fetchone()
        return row[0] if row and row[0] is not None else None


def save_alert(alert: dict) -> int:
    clean_title = alert.get("clean_title")
    extracted_price = alert.get("extracted_price")
    price_drop = 0

    if clean_title and clean_title != "Produto não identificado" and extracted_price is not None:
        min_price = get_min_historical_price(clean_title)
        if min_price is not None and extracted_price < min_price:
            price_drop = round(((min_price - extracted_price) / min_price) * 100)

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO alerts (
                group_id, group_title, username, message, message_id,
                offer_score, offer_categories, extracted_price, link, clean_title, image_url, price_drop_percentage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                alert["group_id"],
                alert["group_title"],
                alert.get("username"),
                alert["message"],
                alert["message_id"],
                alert.get("offer_score"),
                json.dumps(alert.get("offer_categories") or []),
                extracted_price,
                alert.get("link"),
                clean_title,
                alert.get("image_url"),
                price_drop,
            ),
        )
        conn.execute("""
            DELETE FROM alerts WHERE id NOT IN (
                SELECT id FROM alerts ORDER BY id DESC LIMIT 1000
            )
        """)
        conn.commit()
        return cursor.lastrowid or 0


def update_alert_details(
    alert_id: int,
    clean_title: str | None = None,
    extracted_price: float | None = None,
    image_url: str | None = None,
):
    with get_connection() as conn:
        if clean_title is None or extracted_price is None:
            row = conn.execute("SELECT clean_title, extracted_price FROM alerts WHERE id = ?", (alert_id,)).fetchone()
            if row:
                if clean_title is None:
                    clean_title = row["clean_title"]
                if extracted_price is None:
                    extracted_price = row["extracted_price"]

        price_drop = 0
        if clean_title and extracted_price is not None:
            row_min = conn.execute(
                "SELECT MIN(extracted_price) FROM alerts WHERE clean_title = ? AND id != ? AND extracted_price IS NOT NULL",
                (clean_title, alert_id),
            ).fetchone()
            if row_min and row_min[0] is not None:
                min_price = row_min[0]
                if extracted_price < min_price:
                    price_drop = round(((min_price - extracted_price) / min_price) * 100)

        fields = []
        params = []
        if clean_title is not None:
            fields.append("clean_title = ?")
            params.append(clean_title)
        if extracted_price is not None:
            fields.append("extracted_price = ?")
            params.append(extracted_price)
            fields.append("price_drop_percentage = ?")
            params.append(price_drop)
        if image_url is not None:
            fields.append("image_url = ?")
            params.append(image_url)
        if fields:
            params.append(alert_id)
            conn.execute(f"UPDATE alerts SET {', '.join(fields)} WHERE id = ?", params)
            conn.commit()


def clear_alerts():
    with get_connection() as conn:
        conn.execute("DELETE FROM alerts")
        conn.commit()


def get_alerts(
    limit: int = 50,
    min_price: float | None = None,
    max_price: float | None = None,
    category: str | None = None,
    q: str | None = None,
) -> list[dict]:
    query = "SELECT * FROM alerts WHERE 1=1"
    params = []

    if min_price is not None:
        query += " AND extracted_price >= ?"
        params.append(min_price)

    if max_price is not None:
        query += " AND extracted_price <= ?"
        params.append(max_price)

    if category:
        query += " AND offer_categories LIKE ?"
        params.append(f'%"{category}"%')

    if q:
        query += " AND (message LIKE ? OR clean_title LIKE ?)"
        params.append(f"%{q}%")
        params.append(f"%{q}%")

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    alerts = []
    with get_connection() as conn:
        cursor = conn.execute(query, params)
        for row in cursor.fetchall():
            try:
                cats = json.loads(row["offer_categories"])
            except Exception:
                cats = []
            alerts.append(
                {
                    "group_id": row["group_id"],
                    "group_title": row["group_title"],
                    "username": row["username"],
                    "message": row["message"],
                    "message_id": row["message_id"],
                    "offer_score": row["offer_score"],
                    "offer_categories": cats,
                    "extracted_price": row["extracted_price"],
                    "link": row["link"],
                    "clean_title": row["clean_title"],
                    "image_url": row["image_url"] if "image_url" in row.keys() else None,
                    "price_drop_percentage": (
                        row["price_drop_percentage"] if "price_drop_percentage" in row.keys() else 0
                    ),
                }
            )

    alerts.reverse()
    return alerts


def get_alerts_count() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()
        return row[0] if row else 0


def get_price_history_by_msg_id(message_id: int) -> list[dict]:
    with get_connection() as conn:
        row = conn.execute("SELECT clean_title FROM alerts WHERE message_id = ?", (message_id,)).fetchone()
        if not row or not row["clean_title"]:
            return []
        clean_title = row["clean_title"]

        cursor = conn.execute(
            """
            SELECT extracted_price, created_at
            FROM alerts
            WHERE clean_title = ? AND extracted_price IS NOT NULL
            ORDER BY created_at ASC
        """,
            (clean_title,),
        )

        history = []
        for r in cursor.fetchall():
            history.append({"price": r["extracted_price"], "date": r["created_at"]})
        return history
