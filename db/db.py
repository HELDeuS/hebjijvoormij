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
                pool_size = int(os.environ.get("DB_POOL_SIZE", "10"))
                _pool = pooling.MySQLConnectionPool(
                    pool_size=pool_size, **DB_CONFIG
                )
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
                   l.borrower_id, l.status AS loan_status,
                   bf.name AS borrower_name,
                   l.date_from, l.date_until
            FROM tools t
            JOIN friends f ON f.id = t.owner_id
            LEFT JOIN loans l ON l.tool_id = t.id AND l.status IN ('aangevraagd', 'uitgeleend')
            LEFT JOIN friends bf ON bf.id = l.borrower_id
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
                if not statement.strip():
                    continue
                try:
                    db._execute(statement)
                except Exception as exc:
                    print(
                        f"ensure_schema: statement overgeslagen: {exc} "
                        f"(statement: {statement.strip()[:60]}...)"
                    )
        existing = {
            row["COLUMN_NAME"]
            for row in db._query(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'friends'",
                (DB_CONFIG["database"],),
            )
        }
        try:
            db._execute(
                "ALTER TABLE friends ADD UNIQUE KEY uq_email (email)"
            )
        except Exception:
            pass
        migrations = {
            "password_hash": "ALTER TABLE friends ADD COLUMN password_hash VARCHAR(255)",
            "is_admin": "ALTER TABLE friends ADD COLUMN is_admin TINYINT(1) NOT NULL DEFAULT 0",
            "is_super_admin": (
                "ALTER TABLE friends ADD COLUMN is_super_admin TINYINT(1) NOT NULL DEFAULT 0"
            ),
            "must_change_password": (
                "ALTER TABLE friends ADD COLUMN must_change_password TINYINT(1) NOT NULL DEFAULT 0"
            ),
            "status": (
                "ALTER TABLE friends ADD COLUMN status ENUM('in_behandeling', 'actief', 'nonactief') "
                "NOT NULL DEFAULT 'actief'"
            ),
            "deactivation_reason": "ALTER TABLE friends ADD COLUMN deactivation_reason TEXT",
            "date_format": (
                "ALTER TABLE friends ADD COLUMN date_format VARCHAR(10) NOT NULL DEFAULT 'dmy'"
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
        loan_columns = {
            row["COLUMN_NAME"]
            for row in db._query(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'loans'",
                (DB_CONFIG["database"],),
            )
        }
        for column, statement in {
            "note": "ALTER TABLE loans ADD COLUMN note TEXT",
            "date_from": "ALTER TABLE loans ADD COLUMN date_from DATE",
            "date_until": "ALTER TABLE loans ADD COLUMN date_until DATE",
        }.items():
            if column not in loan_columns:
                db._execute(statement)
        for column, statement in tool_migrations.items():
            if column not in tool_columns:
                db._execute(statement)


def get_friends():
    with Database() as db:
        return db.get_friends()


def get_setting(key, default=None):
    with Database() as db:
        rows = db._query(
            "SELECT value FROM settings WHERE `key` = %s", (key,)
        )
        return rows[0]["value"] if rows else default


def set_setting(key, value):
    with Database() as db:
        try:
            db._execute(
                "INSERT INTO settings (`key`, value) VALUES (%s, %s) "
                "ON DUPLICATE KEY UPDATE value = %s",
                (key, value, value),
            )
            return True
        except mysql.connector.errors.Error:
            return False


def get_friend(friend_id):
    with Database() as db:
        rows = db._query("SELECT * FROM friends WHERE id = %s", (friend_id,))
        return rows[0] if rows else None


def add_friend(name, email, phone, password_hash=None, must_change_password=False):
    if not email or get_friend_by_email(email):
        return None
    default_fmt = get_setting("default_date_format", "dmy")
    with Database() as db:
        try:
            db._execute(
                "INSERT INTO friends (name, email, phone, password_hash, must_change_password, date_format) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (name, email, phone, password_hash, must_change_password, default_fmt),
            )
            return db._query("SELECT LAST_INSERT_ID() AS id")[0]["id"]
        except mysql.connector.errors.IntegrityError:
            return None


def get_friend_by_email(email):
    with Database() as db:
        rows = db._query("SELECT * FROM friends WHERE email = %s", (email,))
        return rows[0] if rows else None


def set_friend_password(friend_id, password_hash):
    with Database() as db:
        db._execute(
            "UPDATE friends SET password_hash = %s, must_change_password = 0 "
            "WHERE id = %s",
            (password_hash, friend_id),
        )


def update_friend(friend_id, name, email, phone):
    """Werkt naam, e-mail en telefoon van een bestaand account bij.
    Geeft een foutmelding terug bij een dubbele naam of e-mail, anders None."""
    with Database() as db:
        if db._query(
            "SELECT id FROM friends WHERE name = %s AND id <> %s",
            (name, friend_id),
        ):
            return "Deze naam is al in gebruik."
        if db._query(
            "SELECT id FROM friends WHERE email = %s AND id <> %s",
            (email, friend_id),
        ):
            return "Dit e-mailadres is al in gebruik."
        db._execute(
            "UPDATE friends SET name = %s, email = %s, phone = %s WHERE id = %s",
            (name, email, phone, friend_id),
        )
        return None


def reset_friend_password(friend_id, password_hash):
    """Stelt een nieuw (start)wachtwoord in; de vriend moet het bij de
    eerste login wijzigen."""
    with Database() as db:
        db._execute(
            "UPDATE friends SET password_hash = %s, must_change_password = 1 "
            "WHERE id = %s",
            (password_hash, friend_id),
        )


def register_friend(name, email, password_hash):
    """Eigen registratie door een nieuwe gebruiker; wacht op goedkeuring.
    De datumnotatie wordt de systeemstandaard."""
    if not email or get_friend_by_email(email):
        return None
    default_fmt = get_setting("default_date_format", "dmy")
    with Database() as db:
        try:
            return db._execute(
                "INSERT INTO friends (name, email, phone, password_hash, status, date_format) "
                "VALUES (%s, %s, '', %s, 'in_behandeling', %s)",
                (name, email, password_hash, default_fmt),
            )
        except mysql.connector.errors.IntegrityError:
            return None


def approve_friend(friend_id):
    with Database() as db:
        db._execute(
            "UPDATE friends SET status = 'actief' WHERE id = %s", (friend_id,)
        )


def set_friend_status(friend_id, status, reason=None):
    with Database() as db:
        if status == "nonactief":
            db._execute(
                "UPDATE friends SET status = 'nonactief', deactivation_reason = %s "
                "WHERE id = %s",
                (reason, friend_id),
            )
        else:
            db._execute(
                "UPDATE friends SET status = %s, deactivation_reason = NULL "
                "WHERE id = %s",
                (status, friend_id),
            )


def set_friend_date_format(friend_id, date_format):
    with Database() as db:
        db._execute(
            "UPDATE friends SET date_format = %s WHERE id = %s",
            (date_format, friend_id),
        )


def set_friend_admin(friend_id, is_admin):
    with Database() as db:
        db._execute(
            "UPDATE friends SET is_admin = %s WHERE id = %s",
            (is_admin, friend_id),
        )


def delete_friend(friend_id):
    """Verwijdert een account inclusief gereedschap, leningen en kringen.
    Weigert zolang gereedschap van dit account is uitgeleend of aangevraagd.
    Geeft (True, None) of (False, melding) terug."""
    with Database() as db:
        active = db._query(
            """
            SELECT t.name FROM loans l
            JOIN tools t ON t.id = l.tool_id
            WHERE t.owner_id = %s AND l.status IN ('aangevraagd', 'uitgeleend')
            LIMIT 1
            """,
            (friend_id,),
        )
        if active:
            return False, (
                f"Kan account niet verwijderen: gereedschap "
                f"'{active[0]['name']}' is nog uitgeleend of aangevraagd."
            )
        db._execute("DELETE FROM loans WHERE borrower_id = %s", (friend_id,))
        db._execute(
            "DELETE FROM loans WHERE tool_id IN (SELECT id FROM tools WHERE owner_id = %s)",
            (friend_id,),
        )
        db._execute(
            "DELETE FROM tool_links WHERE tool_id IN (SELECT id FROM tools WHERE owner_id = %s)",
            (friend_id,),
        )
        db._execute(
            "DELETE FROM tool_links WHERE linked_tool_id IN "
            "(SELECT id FROM tools WHERE owner_id = %s)",
            (friend_id,),
        )
        db._execute("DELETE FROM tools WHERE owner_id = %s", (friend_id,))
        db._execute("DELETE FROM circles WHERE created_by = %s", (friend_id,))
        db._execute("DELETE FROM circle_members WHERE friend_id = %s", (friend_id,))
        db._execute("DELETE FROM friends WHERE id = %s", (friend_id,))
        return True, None


def ensure_admin():
    """Maakt de beheerder aan met de vooraf bekende standaardgegevens als er
    nog geen beheerder bestaat. De beheerder moet bij de eerste login een
    nieuw wachtwoord kiezen. Een bestaande beheerder zonder e-mailadres
    krijgt het standaardadres toegewezen (inloggen gaat via e-mail)."""
    name = os.environ.get("ADMIN_NAME", "admin")
    email = os.environ.get("ADMIN_EMAIL", "admin@localhost")
    password = os.environ.get("ADMIN_PASSWORD", "beheer123")
    with Database() as db:
        rows = db._query(
            "SELECT id, email, is_super_admin FROM friends "
            "WHERE is_admin = 1 LIMIT 1"
        )
        if rows:
            if not rows[0]["email"]:
                db._execute(
                    "UPDATE friends SET email = %s WHERE id = %s",
                    (email, rows[0]["id"]),
                )
            if not rows[0].get("is_super_admin"):
                db._execute(
                    "UPDATE friends SET is_super_admin = 1 WHERE id = %s",
                    (rows[0]["id"],),
                )
            return
        try:
            db._execute(
                "INSERT INTO friends (name, email, phone, password_hash, "
                "is_admin, is_super_admin, must_change_password) "
                "VALUES (%s, %s, %s, %s, 1, 1, 1)",
                (name, email, "", generate_password_hash(password)),
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


def update_tool(tool_id, owner_id, name, description, category, brand, model):
    with Database() as db:
        try:
            db._execute(
                "UPDATE tools SET owner_id = %s, name = %s, description = %s, "
                "category = %s, brand = %s, model = %s WHERE id = %s",
                (owner_id, name, description, category, brand, model, tool_id),
            )
            return True
        except mysql.connector.errors.IntegrityError:
            return False


def get_loan(loan_id):
    with Database() as db:
        rows = db._query("SELECT * FROM loans WHERE id = %s", (loan_id,))
        return rows[0] if rows else None


def get_active_loan(tool_id):
    """Geeft de openstaande lening of leenaanvraag van een gereedschap
    terug, of None als het gereedschap beschikbaar is."""
    with Database() as db:
        rows = db._query(
            "SELECT * FROM loans WHERE tool_id = %s "
            "AND status IN ('aangevraagd', 'uitgeleend') LIMIT 1",
            (tool_id,),
        )
        return rows[0] if rows else None


def delete_tool(tool_id):
    """Verwijdert gereedschap inclusief koppelingen en leengeschiedenis.
    Geeft False terug zolang er openstaande leningen of verzoeken zijn."""
    with Database() as db:
        active = db._query(
            "SELECT id FROM loans WHERE tool_id = %s "
            "AND status IN ('aangevraagd', 'uitgeleend')",
            (tool_id,),
        )
        if active:
            return False
        db._execute("DELETE FROM loans WHERE tool_id = %s", (tool_id,))
        db._execute(
            "DELETE FROM tool_links WHERE tool_id = %s OR linked_tool_id = %s",
            (tool_id, tool_id),
        )
        db._execute("DELETE FROM tools WHERE id = %s", (tool_id,))
        return True


def get_distinct_values(column):
    """Geeft alle eerder gebruikte waardes van een kolom van tools terug."""
    allowed = {"category", "brand"}
    if column not in allowed:
        raise ValueError(f"Kolom {column} is niet toegestaan")
    with Database() as db:
        return [
            row["value"]
            for row in db._query(
                f"SELECT DISTINCT {column} AS value FROM tools "
                "WHERE {0} IS NOT NULL AND {0} != '' ORDER BY value".format(column)
            )
        ]


def get_tool(tool_id):
    with Database() as db:
        rows = db._query("SELECT * FROM tools WHERE id = %s", (tool_id,))
        return rows[0] if rows else None


def get_friend_tools(owner_id):
    with Database() as db:
        return db._query(
            """
            SELECT t.*, l.id AS loan_id, l.status AS loan_status,
                   l.borrower_id, bf.name AS borrower_name,
                   l.date_from, l.date_until
            FROM tools t
            LEFT JOIN loans l ON l.tool_id = t.id AND l.status IN ('aangevraagd', 'uitgeleend')
            LEFT JOIN friends bf ON bf.id = l.borrower_id
            WHERE t.owner_id = %s
            ORDER BY t.name
            """,
            (owner_id,),
        )


def create_loan_request(tool_id, borrower_id, note=None, date_from=None, date_until=None):
    with Database() as db:
        try:
            db._execute(
                "INSERT INTO loans (tool_id, borrower_id, status, note, date_from, date_until) "
                "VALUES (%s, %s, 'aangevraagd', %s, %s, %s)",
                (tool_id, borrower_id, note, date_from, date_until),
            )
            return True
        except mysql.connector.errors.IntegrityError:
            return False


def create_notification(friend_id, type_, message, link=None, ref_id=None):
    with Database() as db:
        db._execute(
            "INSERT INTO notifications (friend_id, type, message, link, ref_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            (friend_id, type_, message, link, ref_id),
        )


def get_notifications(friend_id):
    with Database() as db:
        return db._query(
            "SELECT * FROM notifications WHERE friend_id = %s "
            "ORDER BY created_at DESC LIMIT 50",
            (friend_id,),
        )


def get_unread_notification_count(friend_id):
    with Database() as db:
        rows = db._query(
            "SELECT COUNT(*) AS n FROM notifications "
            "WHERE friend_id = %s AND is_read = 0",
            (friend_id,),
        )
        return rows[0]["n"] if rows else 0


def mark_notification_read(notification_id, friend_id):
    with Database() as db:
        db._execute(
            "UPDATE notifications SET is_read = 1 "
            "WHERE id = %s AND friend_id = %s",
            (notification_id, friend_id),
        )


def mark_all_notifications_read(friend_id):
    with Database() as db:
        db._execute(
            "UPDATE notifications SET is_read = 1 WHERE friend_id = %s",
            (friend_id,),
        )


DATE_FORMATS = {
    "dmy": "%d-%m-%Y",
    "ymd": "%Y-%m-%d",
    "mdy": "%m/%d/%Y",
}


def _format_date_for(value, db, friend_id):
    rows = db._query(
        "SELECT date_format FROM friends WHERE id = %s", (friend_id,)
    )
    fmt = DATE_FORMATS.get(rows[0]["date_format"]) if rows else None
    return value.strftime(fmt or "%d-%m-%Y")


def create_overdue_reminders():
    """Maakt een herinnering voor elke uitlening die over de afgesproken
    einddatum heen is; maximaal een herinnering per lening per dag."""
    with Database() as db:
        overdue = db._query(
            """
            SELECT l.id, l.tool_id, l.borrower_id, l.date_until,
                   t.name AS tool_name, t.owner_id,
                   bf.name AS borrower_name
            FROM loans l
            JOIN tools t ON t.id = l.tool_id
            JOIN friends bf ON bf.id = l.borrower_id
            WHERE l.status = 'uitgeleend'
              AND l.date_until IS NOT NULL
              AND l.date_until < CURDATE()
              AND NOT EXISTS (
                  SELECT 1 FROM notifications n
                  WHERE n.ref_id = l.id AND n.type = 'herinnering'
                    AND n.created_at >= CURDATE()
              )
            """
        )
        created = []
        for loan in overdue:
            date_str = _format_date_for(
                loan["date_until"], db, loan["owner_id"]
            )
            message = (
                f"'{loan['tool_name']}' is nog niet terug van "
                f"{loan['borrower_name']} (afgesproken tot {date_str})."
            )
            db._execute(
                "INSERT INTO notifications (friend_id, type, message, link, ref_id) "
                "VALUES (%s, 'herinnering', %s, %s, %s)",
                (loan["owner_id"], message, f"/tools/{loan['tool_id']}", loan["id"]),
            )
            created.append({"friend_id": loan["owner_id"], "message": message})
        return created


def send_message(sender_id, recipient_id, body):
    with Database() as db:
        db._execute(
            "INSERT INTO messages (sender_id, recipient_id, body) "
            "VALUES (%s, %s, %s)",
            (sender_id, recipient_id, body),
        )


def get_inbox(friend_id):
    with Database() as db:
        return db._query(
            """
            SELECT m.*, f.name AS sender_name, f.email AS sender_email
            FROM messages m
            JOIN friends f ON f.id = m.sender_id
            WHERE m.recipient_id = %s
            ORDER BY m.created_at DESC LIMIT 50
            """,
            (friend_id,),
        )


def get_sent_messages(friend_id):
    with Database() as db:
        return db._query(
            """
            SELECT m.*, f.name AS recipient_name
            FROM messages m
            JOIN friends f ON f.id = m.recipient_id
            WHERE m.sender_id = %s
            ORDER BY m.created_at DESC LIMIT 50
            """,
            (friend_id,),
        )


def mark_message_read(message_id, friend_id):
    with Database() as db:
        db._execute(
            "UPDATE messages SET is_read = 1 "
            "WHERE id = %s AND recipient_id = %s",
            (message_id, friend_id),
        )


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


def create_circle(name, creator_id):
    """Maakt een kring aan; de maker wordt automatisch kringbeheerder."""
    with Database() as db:
        try:
            circle_id = db._execute(
                "INSERT INTO circles (name, created_by) VALUES (%s, %s)",
                (name, creator_id),
            )
            db._execute(
                "INSERT INTO circle_members (circle_id, friend_id, is_circle_admin) "
                "VALUES (%s, %s, 1)",
                (circle_id, creator_id),
            )
            return circle_id
        except mysql.connector.errors.IntegrityError:
            return None


def get_circles(friend_id=None):
    """Geeft alle kringen terug, of alleen de kringen waar de vriend lid van
    is. Elke kring bevat het aantal leden en of de opgevraagde vriend
    kringbeheerder is. Ledenaantal en kringbeheerderschap worden via
    subqueries opgehaald, zodat een kring nooit meer dan één rij oplevert."""
    with Database() as db:
        if friend_id is None:
            return db._query(
                """
                SELECT c.*,
                       (SELECT COUNT(*) FROM circle_members x
                        WHERE x.circle_id = c.id) AS member_count
                FROM circles c
                ORDER BY c.name
                """
            )
        return db._query(
            """
            SELECT c.*,
                   (SELECT COUNT(*) FROM circle_members x
                    WHERE x.circle_id = c.id) AS member_count,
                   EXISTS(SELECT 1 FROM circle_members x
                          WHERE x.circle_id = c.id AND x.friend_id = %s
                             AND x.is_circle_admin = 1) AS is_circle_admin
            FROM circles c
            JOIN circle_members my ON my.circle_id = c.id AND my.friend_id = %s
            GROUP BY c.id
            ORDER BY c.name
            """,
            (friend_id, friend_id),
        )


def get_circle(circle_id):
    with Database() as db:
        rows = db._query("SELECT * FROM circles WHERE id = %s", (circle_id,))
        return rows[0] if rows else None


def get_circle_members(circle_id):
    with Database() as db:
        return db._query(
            """
            SELECT cm.friend_id, cm.is_circle_admin, f.name, f.email
            FROM circle_members cm
            JOIN friends f ON f.id = cm.friend_id
            WHERE cm.circle_id = %s
            ORDER BY cm.is_circle_admin DESC, f.name
            """,
            (circle_id,),
        )


def is_circle_admin(circle_id, friend_id):
    with Database() as db:
        return bool(
            db._query(
                "SELECT id FROM circle_members WHERE circle_id = %s "
                "AND friend_id = %s AND is_circle_admin = 1",
                (circle_id, friend_id),
            )
        )


def add_circle_member(circle_id, friend_id):
    with Database() as db:
        try:
            db._execute(
                "INSERT INTO circle_members (circle_id, friend_id) VALUES (%s, %s)",
                (circle_id, friend_id),
            )
            return True
        except mysql.connector.errors.IntegrityError:
            return False


def remove_circle_member(circle_id, friend_id):
    with Database() as db:
        db._execute(
            "DELETE FROM circle_members WHERE circle_id = %s AND friend_id = %s",
            (circle_id, friend_id),
        )


def update_circle(circle_id, name):
    with Database() as db:
        try:
            db._execute("UPDATE circles SET name = %s WHERE id = %s", (name, circle_id))
            return True
        except mysql.connector.errors.IntegrityError:
            return False


def delete_circle(circle_id):
    with Database() as db:
        db._execute("DELETE FROM circles WHERE id = %s", (circle_id,))


def get_visible_friend_ids(friend_id):
    """Vrienden met wie je minstens een kring deelt."""
    with Database() as db:
        rows = db._query(
            """
            SELECT DISTINCT cm2.friend_id AS id
            FROM circle_members cm1
            JOIN circle_members cm2 ON cm2.circle_id = cm1.circle_id
            WHERE cm1.friend_id = %s AND cm2.friend_id <> %s
            """,
            (friend_id, friend_id),
        )
        return {row["id"] for row in rows}


def get_visible_tools(friend_id):
    """Gereedschap van de vriend zelf en van vrienden met wie hij een
    kring deelt."""
    with Database() as db:
        return db._query(
            """
            SELECT t.*, f.name AS owner_name,
                   l.id AS active_loan_id, l.borrower_id, l.status AS loan_status,
                   bf.name AS borrower_name,
                   l.date_from, l.date_until
            FROM tools t
            JOIN friends f ON f.id = t.owner_id
            LEFT JOIN loans l ON l.tool_id = t.id
                 AND l.status IN ('aangevraagd', 'uitgeleend')
            LEFT JOIN friends bf ON bf.id = l.borrower_id
            WHERE t.owner_id = %s OR t.owner_id IN (
                SELECT cm2.friend_id FROM circle_members cm1
                JOIN circle_members cm2 ON cm2.circle_id = cm1.circle_id
                WHERE cm1.friend_id = %s
            )
            ORDER BY t.name
            """,
            (friend_id, friend_id),
        )


def get_global_stats():
    """Totale aantallen: gereedschap, actieve gebruikers en uitleningen."""
    with Database() as db:
        rows = db._query(
            """
            SELECT
              (SELECT COUNT(*) FROM tools) AS tool_count,
              (SELECT COUNT(*) FROM friends WHERE status = 'actief') AS user_count,
              (SELECT COUNT(*) FROM loans) AS loan_count
            """
        )
        return rows[0] if rows else {"tool_count": 0, "user_count": 0, "loan_count": 0}


def get_circle_stats(circle_ids=None):
    """Statistieken per kring: leden, gereedschap van leden en uitleningen
    van dat gereedschap. Optioneel beperkt tot de opgegeven kring-ids."""
    with Database() as db:
        scope = ""
        params = ()
        if circle_ids is not None:
            if not circle_ids:
                return []
            placeholders = ",".join(["%s"] * len(circle_ids))
            scope = f"WHERE c.id IN ({placeholders})"
            params = tuple(circle_ids)
        return db._query(
            """
            SELECT c.id, c.name,
                   (SELECT COUNT(*) FROM circle_members x
                    WHERE x.circle_id = c.id) AS member_count,
                   (SELECT COUNT(*) FROM tools t
                    WHERE t.owner_id IN (SELECT friend_id FROM circle_members x
                                         WHERE x.circle_id = c.id)) AS tool_count,
                   (SELECT COUNT(*) FROM loans l JOIN tools t ON t.id = l.tool_id
                    WHERE t.owner_id IN (SELECT friend_id FROM circle_members x
                                         WHERE x.circle_id = c.id)) AS loan_count
            FROM circles c
            """ + scope + """
            ORDER BY c.name
            """,
            params,
        )


def get_scoped_loans(friend_id, admin_circle_ids=None):
    """Uitleningen binnen de beheerscope van een gebruiker.

    - admin_circle_ids None: alles (beheerder)
    - admin_circle_ids leeg: alleen eigen uitleningen (als lener of eigenaar)
    - anders: eigen uitleningen plus die van de kringen waarvan de
      gebruiker kringbeheerder is
    """
    with Database() as db:
        base = """
            SELECT l.*, t.name AS tool_name, t.owner_id,
                   of.name AS owner_name, bf.name AS borrower_name
            FROM loans l
            JOIN tools t ON t.id = l.tool_id
            JOIN friends of ON of.id = t.owner_id
            JOIN friends bf ON bf.id = l.borrower_id
        """
        if admin_circle_ids is None:
            return db._query(base + " ORDER BY l.created_at DESC")
        if not admin_circle_ids:
            return db._query(
                base + " WHERE (t.owner_id = %s OR l.borrower_id = %s) "
                "ORDER BY l.created_at DESC",
                (friend_id, friend_id),
            )
        placeholders = ",".join(["%s"] * len(admin_circle_ids))
        return db._query(
            base
            + f"""
              WHERE (t.owner_id = %s OR l.borrower_id = %s
                 OR t.owner_id IN (SELECT friend_id FROM circle_members
                                   WHERE circle_id IN ({placeholders}))
                 OR l.borrower_id IN (SELECT friend_id FROM circle_members
                                      WHERE circle_id IN ({placeholders})))
              ORDER BY l.created_at DESC
            """,
            (friend_id, friend_id, *admin_circle_ids, *admin_circle_ids),
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


def get_overview(friend_id=None):
    with Database() as db:
        scope = ""
        params = ()
        if friend_id is not None:
            scope = """
              AND (t.owner_id IN (
                    SELECT cm2.friend_id FROM circle_members cm1
                    JOIN circle_members cm2 ON cm2.circle_id = cm1.circle_id
                    WHERE cm1.friend_id = %s
                  ) OR l.borrower_id IN (
                    SELECT cm2.friend_id FROM circle_members cm1
                    JOIN circle_members cm2 ON cm2.circle_id = cm1.circle_id
                    WHERE cm1.friend_id = %s
                  ) OR t.owner_id = %s OR l.borrower_id = %s)
            """
            params = (friend_id, friend_id, friend_id, friend_id)
        return db._query(
            """
            SELECT l.*, t.name AS tool_name,
                   of.name AS owner_name, bf.name AS borrower_name
            FROM loans l
            JOIN tools t ON t.id = l.tool_id
            JOIN friends of ON of.id = t.owner_id
            JOIN friends bf ON bf.id = l.borrower_id
            WHERE l.status IN ('aangevraagd', 'uitgeleend')""" + scope + """
            ORDER BY l.status, l.created_at
            """,
            params,
        )


def get_friend_stats(friend_id=None):
    """Statistieken per vriend; optioneel beperkt tot vrienden met wie de
    opgegeven vriend een kring deelt."""
    with Database() as db:
        scope = ""
        params = ()
        if friend_id is not None:
            scope = """
            WHERE f.id = %s OR f.id IN (
                SELECT cm2.friend_id FROM circle_members cm1
                JOIN circle_members cm2 ON cm2.circle_id = cm1.circle_id
                WHERE cm1.friend_id = %s
            )
            """
            params = (friend_id, friend_id)
        return db._query(
            """
            SELECT f.id, f.name,
                   COUNT(DISTINCT t.id) AS tool_count,
                   COALESCE(SUM(l.status = 'uitgeleend'), 0) AS active_lent,
                   COALESCE(SUM(l.status = 'aangevraagd'), 0) AS pending_requests
            FROM friends f
            LEFT JOIN tools t ON t.owner_id = f.id
            LEFT JOIN loans l ON l.tool_id = t.id AND l.status IN ('aangevraagd', 'uitgeleend')
            """ + scope + """
            GROUP BY f.id, f.name
            ORDER BY f.name
            """,
            params,
        )
