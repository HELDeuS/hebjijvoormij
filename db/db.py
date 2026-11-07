import os

import mysql.connector
from mysql.connector import pooling

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "127.0.0.1"),
    "port": int(os.environ.get("DB_PORT", "3306")),
    "user": os.environ.get("DB_USER", "gereedschap"),
    "password": os.environ.get("DB_PASSWORD", "gereedschap"),
    "database": os.environ.get("DB_NAME", "gereedschap_leensysteem"),
    "autocommit": True,
}

_pool = pooling.MySQLConnectionPool(pool_size=5, **DB_CONFIG)


def _connect():
    return _pool.get_connection()


class Database:
    def __init__(self):
        self.cnx = _connect()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.cnx.close()

    def _query(self, sql, params=()):
        with self.cnx.cursor(dictionary=True) as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def _execute(self, sql, params=()):
        with self.cnx.cursor() as cur:
            cur.execute(sql, params)
            return cur.lastrowid

    def get_friends(self):
        return self._query("SELECT * FROM friends ORDER BY name")

    def get_tools(self, owner_id=None, available_only=False):
        sql = """
            SELECT t.*, f.name AS owner_name,
                   l.id AS active_loan_id,
                   l.borrower_id, l.status AS loan_status
            FROM tools t
            JOIN friends f ON f.id = t.owner_id
            LEFT JOIN loans l ON l.tool_id = t.id AND l.status IN ('aangevraagd', 'uitgeleend')
            WHERE 1=1
        """
        params = []
        if owner_id:
            sql += " AND t.owner_id = %s"
            params.append(owner_id)
        if available_only:
            sql += " AND l.id IS NULL"
        sql += " ORDER BY t.name"
        return self._query(sql, params)


def init_db():
    cnx = mysql.connector.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=os.environ.get("DB_USER_ROOT", "root"),
        password=os.environ.get("DB_PASSWORD_ROOT", ""),
    )
    try:
        with cnx.cursor() as cur:
            cur.execute(
                "CREATE DATABASE IF NOT EXISTS gereedschap_leensysteem "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            with open(os.path.join(os.path.dirname(__file__), "schema.sql")) as f:
                for statement in f.read().split(";"):
                    if statement.strip():
                        cur.execute(statement)
            _migrate(cur)
    finally:
        cnx.close()


def _migrate(cur):
    cur.execute(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = 'gereedschap_leensysteem' AND TABLE_NAME = 'tools'"
    )
    existing = {row[0] for row in cur.fetchall()}
    migrations = {
        "brand": "ALTER TABLE tools ADD COLUMN brand VARCHAR(100)",
        "model": "ALTER TABLE tools ADD COLUMN model VARCHAR(100)",
        "image_path": "ALTER TABLE tools ADD COLUMN image_path VARCHAR(255)",
    }
    for column, statement in migrations.items():
        if column not in existing:
            cur.execute(statement)


def get_friend(friend_id):
    with Database() as db:
        rows = db._query("SELECT * FROM friends WHERE id = %s", (friend_id,))
        return rows[0] if rows else None


def add_friend(name, email, phone):
    with Database() as db:
        try:
            db._execute(
                "INSERT INTO friends (name, email, phone) VALUES (%s, %s, %s)",
                (name, email, phone),
            )
            return True
        except mysql.connector.errors.IntegrityError:
            return False


def add_tool(owner_id, name, description, category, brand=None, model=None):
    with Database() as db:
        try:
            db._execute(
                "INSERT INTO tools (owner_id, name, description, category, brand, model) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (owner_id, name, description, category, brand, model),
            )
            return db._query("SELECT LAST_INSERT_ID() AS id")[0]["id"]
        except mysql.connector.errors.IntegrityError:
            return None


def set_tool_image(tool_id, image_path):
    with Database() as db:
        db._execute(
            "UPDATE tools SET image_path = %s WHERE id = %s", (image_path, tool_id)
        )


def remove_tool_image(tool_id):
    with Database() as db:
        db._execute(
            "UPDATE tools SET image_path = NULL WHERE id = %s", (tool_id,)
        )


def get_tools(owner_id=None, available_only=False):
    with Database() as db:
        return db.get_tools(owner_id=owner_id, available_only=available_only)


def get_tool(tool_id):
    with Database() as db:
        rows = db._query("SELECT * FROM tools WHERE id = %s", (tool_id,))
        return rows[0] if rows else None


def get_friend_tools(owner_id):
    with Database() as db:
        return db._query(
            """
            SELECT t.*, l.id AS loan_id, l.status AS loan_status,
                   l.borrower_id, bf.name AS borrower_name
            FROM tools t
            LEFT JOIN loans l ON l.tool_id = t.id AND l.status IN ('aangevraagd', 'uitgeleend')
            LEFT JOIN friends bf ON bf.id = l.borrower_id
            WHERE t.owner_id = %s
            ORDER BY t.name
            """,
            (owner_id,),
        )


def create_loan_request(tool_id, borrower_id):
    with Database() as db:
        try:
            db._execute(
                "INSERT INTO loans (tool_id, borrower_id, status) "
                "VALUES (%s, %s, 'aangevraagd')",
                (tool_id, borrower_id),
            )
            return True
        except mysql.connector.errors.IntegrityError:
            return False


def approve_loan(loan_id):
    with Database() as db:
        return db._execute(
            "UPDATE loans SET status = 'uitgeleend', lent_at = CURDATE() "
            "WHERE id = %s AND status = 'aangevraagd'",
            (loan_id,),
        ) > 0


def reject_loan(loan_id):
    with Database() as db:
        return db._execute(
            "UPDATE loans SET status = 'geweigerd' "
            "WHERE id = %s AND status = 'aangevraagd'",
            (loan_id,),
        ) > 0


def return_loan(loan_id):
    with Database() as db:
        return db._execute(
            "UPDATE loans SET status = 'teruggekeerd', returned_at = CURDATE() "
            "WHERE id = %s AND status = 'uitgeleend'",
            (loan_id,),
        ) > 0


def get_friend_transactions(friend_id):
    with Database() as db:
        return db._query(
            """
            SELECT l.*, t.name AS tool_name, t.owner_id,
                   of.name AS owner_name, bf.name AS borrower_name
            FROM loans l
            JOIN tools t ON t.id = l.tool_id
            JOIN friends of ON of.id = t.owner_id
            JOIN friends bf ON bf.id = l.borrower_id
            WHERE l.borrower_id = %s OR t.owner_id = %s
            ORDER BY l.created_at DESC
            """,
            (friend_id, friend_id),
        )


def get_overview():
    with Database() as db:
        return db._query(
            """
            SELECT l.*, t.name AS tool_name,
                   of.name AS owner_name, bf.name AS borrower_name
            FROM loans l
            JOIN tools t ON t.id = l.tool_id
            JOIN friends of ON of.id = t.owner_id
            JOIN friends bf ON bf.id = l.borrower_id
            WHERE l.status IN ('aangevraagd', 'uitgeleend')
            ORDER BY l.status, l.created_at
            """
        )


def get_friend_stats():
    with Database() as db:
        return db._query(
            """
            SELECT f.id, f.name,
                   COUNT(DISTINCT t.id) AS tool_count,
                   COALESCE(SUM(l.status = 'uitgeleend'), 0) AS active_lent,
                   COALESCE(SUM(l.status = 'aangevraagd'), 0) AS pending_requests
            FROM friends f
            LEFT JOIN tools t ON t.owner_id = f.id
            LEFT JOIN loans l ON l.tool_id = t.id AND l.status IN ('aangevraagd', 'uitgeleend')
            GROUP BY f.id, f.name
            ORDER BY f.name
            """
        )
