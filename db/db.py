import os
import threading

import mysql.connector
from mysql.connector import pooling
from werkzeug.security import generate_password_hash

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "127.0.0.1"),
    "port": int(os.environ.get("DB_PORT", "3306")),
    "user": os.environ.get("DB_USER", "gereedschap"),
    "password": os.environ.get("DB_PASSWORD", "gereedschap"),
    "database": os.environ.get("DB_NAME", "gereedschap_leensysteem"),
    "autocommit": True,
}

_pool = None
_pool_lock = threading.Lock()


def _connect():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = pooling.MySQLConnectionPool(pool_size=5, **DB_CONFIG)
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
        "password_hash": (
            "ALTER TABLE friends ADD COLUMN password_hash VARCHAR(255)"
        ),
        "is_admin": "ALTER TABLE friends ADD COLUMN is_admin TINYINT(1) NOT NULL DEFAULT 0",
        "must_change_password": (
            "ALTER TABLE friends ADD COLUMN must_change_password TINYINT(1) NOT NULL DEFAULT 0"
        ),
    }
    for column, statement in migrations.items():
        if column not in existing:
            cur.execute(statement)


def ensure_schema():
    """Zet het databaseschema recht met de gewone app-gebruiker (die alle
    rechten heeft op de database): voert schema.sql uit en voegt ontbrekende
    kolommen toe aan bestaande tabellen. Werkt dus ook als de automatische
    migratie via de root-verbinding niet kon draaien (unix-socket-auth)."""
    with Database() as db:
        with open(os.path.join(os.path.dirname(__file__), "schema.sql")) as f:
            for statement in f.read().split(";"):
                if statement.strip():
                    db._execute(statement)
        existing = {
            row["COLUMN_NAME"]
            for row in db._query(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'friends'",
                (DB_CONFIG["database"],),
            )
        }
        migrations = {
            "password_hash": "ALTER TABLE friends ADD COLUMN password_hash VARCHAR(255)",
            "is_admin": "ALTER TABLE friends ADD COLUMN is_admin TINYINT(1) NOT NULL DEFAULT 0",
            "must_change_password": (
                "ALTER TABLE friends ADD COLUMN must_change_password TINYINT(1) NOT NULL DEFAULT 0"
            ),
        }
        for column, statement in migrations.items():
            if column not in existing:
                db._execute(statement)
        tool_columns = {
            row["COLUMN_NAME"]
            for row in db._query(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'tools'",
                (DB_CONFIG["database"],),
            )
        }
        tool_migrations = {
            "brand": "ALTER TABLE tools ADD COLUMN brand VARCHAR(100)",
            "model": "ALTER TABLE tools ADD COLUMN model VARCHAR(100)",
            "image_path": "ALTER TABLE tools ADD COLUMN image_path VARCHAR(255)",
        }
        for column, statement in tool_migrations.items():
            if column not in tool_columns:
                db._execute(statement)


def get_friend(friend_id):
    with Database() as db:
        rows = db._query("SELECT * FROM friends WHERE id = %s", (friend_id,))
        return rows[0] if rows else None


def add_friend(name, email, phone, password_hash=None, must_change_password=False):
    with Database() as db:
        try:
            db._execute(
                "INSERT INTO friends (name, email, phone, password_hash, must_change_password) "
                "VALUES (%s, %s, %s, %s, %s)",
                (name, email, phone, password_hash, must_change_password),
            )
            return db._query("SELECT LAST_INSERT_ID() AS id")[0]["id"]
        except mysql.connector.errors.IntegrityError:
            return None


def get_friend_by_name(name):
    with Database() as db:
        rows = db._query("SELECT * FROM friends WHERE name = %s", (name,))
        return rows[0] if rows else None


def set_friend_password(friend_id, password_hash):
    with Database() as db:
        db._execute(
            "UPDATE friends SET password_hash = %s, must_change_password = 0 "
            "WHERE id = %s",
            (password_hash, friend_id),
        )


def ensure_admin():
    """Maakt de beheerder aan met de vooraf bekende standaardgegevens als er
    nog geen beheerder bestaat. De beheerder moet bij de eerste login een
    nieuw wachtwoord kiezen."""
    name = os.environ.get("ADMIN_NAME", "admin")
    password = os.environ.get("ADMIN_PASSWORD", "beheer123")
    with Database() as db:
        rows = db._query("SELECT id FROM friends WHERE is_admin = 1 LIMIT 1")
        if rows:
            return
        try:
            db._execute(
                "INSERT INTO friends (name, email, phone, password_hash, "
                "is_admin, must_change_password) VALUES (%s, %s, %s, %s, 1, 1)",
                (name, "", "", generate_password_hash(password)),
            )
        except mysql.connector.errors.IntegrityError:
            pass


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


def add_tool_link(tool_id, linked_tool_id):
    """Koppelt twee gereedschappen symmetrisch aan elkaar."""
    if tool_id == linked_tool_id:
        return False
    with Database() as db:
        try:
            db._execute(
                "INSERT INTO tool_links (tool_id, linked_tool_id) "
                "VALUES (%s, %s), (%s, %s)",
                (tool_id, linked_tool_id, linked_tool_id, tool_id),
            )
            return True
        except mysql.connector.errors.IntegrityError:
            return False


def remove_tool_link(tool_id, linked_tool_id):
    with Database() as db:
        db._execute(
            "DELETE FROM tool_links "
            "WHERE (tool_id = %s AND linked_tool_id = %s) "
            "   OR (tool_id = %s AND linked_tool_id = %s)",
            (tool_id, linked_tool_id, linked_tool_id, tool_id),
        )


def get_linked_tools_map(tool_ids):
    """Geeft per gereedschap-id een lijst van gekoppelde gereedschappen terug."""
    if not tool_ids:
        return {}
    placeholders = ",".join(["%s"] * len(tool_ids))
    with Database() as db:
        rows = db._query(
            f"""
            SELECT tl.tool_id, t.id AS linked_id, t.name AS linked_name,
                   t.brand AS linked_brand, t.model AS linked_model,
                   f.name AS linked_owner, t.image_path AS linked_image
            FROM tool_links tl
            JOIN tools t ON t.id = tl.linked_tool_id
            JOIN friends f ON f.id = t.owner_id
            WHERE tl.tool_id IN ({placeholders})
            ORDER BY t.name
            """,
            tuple(tool_ids),
        )
    links = {}
    for row in rows:
        links.setdefault(row["tool_id"], []).append(row)
    return links


def get_combi_suggestions(friend_id):
    """Geeft per openstaande lening van een vriend het beschikbare, gekoppelde
    gereedschap terug dat nog niet door die vriend is aangevraagd of geleend."""
    with Database() as db:
        return db._query(
            """
            SELECT DISTINCT lt.id, lt.name, lt.brand, lt.model,
                   f.name AS owner_name,
                   pt.id AS primary_tool_id, pt.name AS primary_tool_name,
                   l.status AS primary_loan_status
            FROM loans l
            JOIN tools pt ON pt.id = l.tool_id
            JOIN tool_links tl ON tl.tool_id = pt.id
            JOIN tools lt ON lt.id = tl.linked_tool_id
            JOIN friends f ON f.id = lt.owner_id
            LEFT JOIN loans l2 ON l2.tool_id = lt.id
                 AND l2.status IN ('aangevraagd', 'uitgeleend')
            LEFT JOIN loans l3 ON l3.tool_id = lt.id
                 AND l3.borrower_id = l.borrower_id
                 AND l3.status IN ('aangevraagd', 'uitgeleend')
            WHERE l.borrower_id = %s
              AND l.status IN ('aangevraagd', 'uitgeleend')
              AND l2.id IS NULL
              AND l3.id IS NULL
              AND lt.owner_id <> l.borrower_id
            ORDER BY pt.name, lt.name
            """,
            (friend_id,),
        )


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
