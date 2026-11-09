import os
import time
from functools import wraps

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from db.db import (
    Database,
    add_circle_member,
    add_friend,
    add_tool,
    add_tool_link,
    approve_friend,
    approve_loan,
    create_circle,
    create_loan_request,
    create_notification,
    create_overdue_reminders,
    delete_circle,
    delete_friend,
    delete_tool,
    ensure_admin,
    ensure_schema,
    get_circle,
    get_circle_members,
    get_circle_stats,
    get_circles,
    get_combi_suggestions,
    get_distinct_values,
    get_active_loan,
    get_friend,
    get_friend_by_email,
    get_friends,
    get_friend_stats,
    get_friend_tools,
    get_friend_transactions,
    get_global_stats,
    get_inbox,
    get_setting,
    get_linked_tools_map,
    get_loan,
    get_notifications,
    get_overview,
    get_sent_messages,
    get_scoped_loans,
    get_tool,
    get_tools,
    get_unread_notification_count,
    get_visible_tools,
    init_db,
    is_circle_admin,
    mark_all_notifications_read,
    mark_message_read,
    mark_notification_read,
    register_friend,
    remove_circle_member,
    remove_tool_image,
    remove_tool_link,
    reset_friend_password,
    reject_loan,
    return_loan,
    send_message,
    set_friend_admin,
    set_friend_date_format,
    set_setting,
    set_friend_password,
    set_friend_status,
    set_tool_image,
    update_circle,
    update_friend,
    update_tool,
)
from images import download_image, upload_image
from mail import send_email

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-key-verander-dit")

STATUS_LABELS = {
    "aangevraagd": "Aangevraagd",
    "uitgeleend": "Uitgeleend",
    "teruggekeerd": "Teruggekeerd",
    "geweigerd": "Geweigerd",
}

app.jinja_env.globals.update(STATUS_LABELS=STATUS_LABELS)

DATE_FORMATS = {
    "dmy": "%d-%m-%Y",
    "ymd": "%Y-%m-%d",
    "mdy": "%m/%d/%Y",
}


def _fmt_date(value):
    """Formatteert een datum volgens de voorkeur van de ingelogde
    gebruiker (of de systeemstandaard). Accepteert date, datetime en
    ISO-string; onbekende invoer wordt ongewijzigd teruggegeven."""
    from datetime import date as _date, datetime as _datetime

    if value in (None, ""):
        return value
    if isinstance(value, str):
        try:
            value = _datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return value
    if isinstance(value, _datetime):
        value = value.date()
    if not isinstance(value, _date):
        return value
    me = g.get("friend") if hasattr(g, "get") else None
    fmt_key = (me or {}).get("date_format") if me else None
    if not fmt_key:
        try:
            fmt_key = get_setting("default_date_format", "dmy")
        except Exception:
            fmt_key = "dmy"
    fmt = DATE_FORMATS.get(fmt_key, "%d-%m-%Y")
    return value.strftime(fmt)


app.jinja_env.filters["fmt_date"] = _fmt_date

NOTIFICATION_EMAIL_SUBJECTS = {
    "leenverzoek": "Nieuw leenverzoek",
    "goedgekeurd": "Leenverzoek goedgekeurd",
    "geweigerd": "Leenverzoek geweigerd",
    "teruggekeerd": "Gereedschap teruggekeerd",
    "bericht": "Nieuw bericht",
    "herinnering": "Herinnering: gereedschap nog niet terug",
}


def _notify(friend_id, type_, message, link=None, ref_id=None):
    """Maakt een melding en verstuurt indien mogelijk een e-mail."""
    create_notification(friend_id, type_, message, link, ref_id)
    try:
        recipient = get_friend(friend_id)
        if recipient and recipient.get("email"):
            subject = f"hebjijvoormij - {NOTIFICATION_EMAIL_SUBJECTS.get(type_, 'Melding')}"
            send_email(recipient["email"], subject, message)
    except Exception as exc:
        app.logger.warning("E-mail bij melding faalde: %s", exc)


@app.context_processor
def inject_globals():
    me = g.get("friend")
    return {
        "friends": get_friends() if me else [],
        "friend": me,
        "unread_notifications": get_unread_notification_count(me["id"]) if me else 0,
    }


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.get("friend"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


_last_reminder_check = {"ts": 0.0}
_schema_checked = {"done": False}


@app.before_request
def load_current_friend():
    if not _schema_checked["done"]:
        _schema_checked["done"] = True
        try:
            ensure_schema()
            ensure_admin()
        except Exception as exc:
            app.logger.warning(
                "Database-initialisatie bij eerste request mislukt: %s", exc
            )
    friend_id = session.get("friend_id")
    friend = get_friend(friend_id) if friend_id else None
    if friend and friend.get("status") != "actief":
        session.clear()
        friend = None
    g.friend = friend
    if friend and time.time() - _last_reminder_check["ts"] > 3600:
        _last_reminder_check["ts"] = time.time()
        try:
            created = create_overdue_reminders()
            for reminder in created or []:
                _notify(
                    reminder["friend_id"],
                    "herinnering",
                    reminder["message"],
                )
        except Exception as exc:
            app.logger.warning("Herinneringscontrole mislukt: %s", exc)


_login_failures = {}
_LOGIN_WINDOW_SECONDS = 15 * 60
_LOGIN_MAX_FAILURES = 5


def _login_blocked(email):
    now = time.time()
    failures = [
        t
        for t in _login_failures.get(email, [])
        if now - t < _LOGIN_WINDOW_SECONDS
    ]
    _login_failures[email] = failures
    return len(failures) >= _LOGIN_MAX_FAILURES


def _register_login_failure(email):
    _login_failures.setdefault(email, []).append(time.time())


def _clear_login_failures(email):
    _login_failures.pop(email, None)


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.friend:
        return redirect(url_for("index"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 6:
            flash(
                "Naam en e-mail zijn verplicht en het wachtwoord moet "
                "minstens 6 tekens zijn.",
                "error",
            )
        elif register_friend(name, email, generate_password_hash(password)):
            flash(
                "Je account is aangemaakt en wacht op goedkeuring door de "
                "beheerder.",
                "success",
            )
            return redirect(url_for("login"))
        else:
            flash("Deze naam of dit e-mailadres is al in gebruik.", "error")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.friend:
        return redirect(url_for("index"))
    try:
        ensure_schema()
        ensure_admin()
    except Exception as exc:
        app.logger.warning(
            "Database-schema of beheerder kon niet worden gecontroleerd: %s. "
            "Draai 'venv/bin/flask --app app ensure-admin' voor diagnostiek.",
            exc,
        )
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        new_password = request.form.get("new_password", "")
        if _login_blocked(email):
            flash(
                "Te veel mislukte inlogpogingen; probeer het over een "
                "kwartier nog eens.",
                "error",
            )
            return render_template("login.html")
        friend = get_friend_by_email(email)
        if not friend:
            _register_login_failure(email)
            flash("Onbekend e-mailadres. Ben je al geregistreerd als vriend?", "error")
        elif friend["status"] == "in_behandeling":
            flash(
                "Je account wacht nog op goedkeuring door de beheerder.",
                "warning",
            )
        elif friend["status"] == "nonactief":
            reason = friend["deactivation_reason"]
            flash(
                "Je account is non-actief gesteld"
                + (f": {reason}" if reason else "")
                + ". Neem contact op met de beheerder.",
                "error",
            )
        elif friend["password_hash"] is None:
            set_friend_password(friend["id"], generate_password_hash(password))
            session["friend_id"] = friend["id"]
            _clear_login_failures(email)
            flash(
                f"Welkom {friend['name']}! Je wachtwoord is ingesteld; "
                "gebruik het voortaan om in te loggen.",
                "success",
            )
            return redirect(url_for("index"))
        elif not check_password_hash(friend["password_hash"], password):
            _register_login_failure(email)
            flash("Onjuist wachtwoord.", "error")
        elif friend["must_change_password"]:
            if len(new_password) < 6:
                flash(
                    "Dit is je eerste login: kies een nieuw wachtwoord van "
                    "minstens 6 tekens.",
                    "warning",
                )
                return render_template("login.html", show_change=True, email=email)
            set_friend_password(friend["id"], generate_password_hash(new_password))
            session["friend_id"] = friend["id"]
            _clear_login_failures(email)
            flash(
                f"Welkom {friend['name']}! Je wachtwoord is gewijzigd.", "success"
            )
            return redirect(url_for("index"))
        else:
            session["friend_id"] = friend["id"]
            _clear_login_failures(email)
            flash(f"Welkom terug, {friend['name']}!", "success")
            return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Je bent uitgelogd.", "success")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    me = g.friend
    if me["is_admin"]:
        return render_template(
            "index.html", overview=get_overview(), stats=get_friend_stats()
        )
    return render_template(
        "index.html",
        overview=get_overview(me["id"]),
        stats=get_friend_stats(me["id"]),
    )


@app.route("/friends", methods=["GET", "POST"])
@login_required
def friends():
    me = g.friend
    if request.method == "POST" and "default_date_format" in request.form:
        value = request.form.get("default_date_format", "").strip()
        if me["is_admin"] and value in DATE_FORMATS:
            set_setting("default_date_format", value)
            flash(
                "Standaard datumnotatie voor nieuwe gebruikers is aangepast.",
                "success",
            )
        return redirect(url_for("friends"))
    if request.method == "POST":
        if not g.friend["is_admin"]:
            flash("Alleen de beheerder kan nieuwe vrienden toevoegen.", "error")
            return redirect(url_for("friends"))
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 6:
            flash(
                "Naam en e-mail zijn verplicht en het wachtwoord moet "
                "minstens 6 tekens zijn.",
                "error",
            )
        else:
            friend_id = add_friend(
                name,
                email,
                phone,
                generate_password_hash(password),
                must_change_password=True,
            )
            if friend_id is None:
                flash("Deze naam of dit e-mailadres is al in gebruik.", "error")
            else:
                flash(
                    f"Vriend {name} is geregistreerd; "
                    f"hij/zij kiest bij de eerste login een eigen wachtwoord.",
                    "success",
                )
        return redirect(url_for("friends"))
    pending = [f for f in get_friends() if f.get("status") == "in_behandeling"]
    return render_template(
        "friends.html",
        friends_list=get_friends(),
        pending=pending,
        default_date_format=get_setting("default_date_format", "dmy"),
        date_formats=DATE_FORMATS,
    )


@app.route("/friends/<int:friend_id>/approve", methods=["POST"])
@login_required
def friend_approve(friend_id):
    if not g.friend["is_admin"]:
        flash("Alleen de beheerder kan accounts goedkeuren.", "error")
        return redirect(url_for("friends"))
    friend = get_friend(friend_id)
    if friend and friend["status"] == "in_behandeling":
        approve_friend(friend_id)
        flash(f"Account van {friend['name']} is goedgekeurd.", "success")
    return redirect(url_for("friends"))


@app.route("/friends/<int:friend_id>/status", methods=["POST"])
@login_required
def friend_status(friend_id):
    me = g.friend
    if not me["is_admin"]:
        flash("Alleen de beheerder kan accounts op non-actief zetten.", "error")
        return redirect(url_for("friends"))
    friend = get_friend(friend_id)
    if not friend:
        flash("Vriend niet gevonden.", "error")
        return redirect(url_for("friends"))
    if friend["is_super_admin"]:
        flash("De hoofdbeheerder kan niet op non-actief worden gezet.", "error")
        return redirect(url_for("friends"))
    action = request.form.get("action")
    if action == "deactivate":
        reason = request.form.get("reason", "").strip()
        set_friend_status(friend_id, "nonactief", reason or None)
        flash(f"Account van {friend['name']} is non-actief gezet.", "success")
    elif action == "activate":
        set_friend_status(friend_id, "actief")
        flash(f"Account van {friend['name']} is weer actief.", "success")
    return redirect(url_for("friends"))


@app.route("/friends/<int:friend_id>/admin", methods=["POST"])
@login_required
def friend_admin(friend_id):
    me = g.friend
    if not me["is_super_admin"]:
        flash("Alleen de hoofdbeheerder kan beheerders aanwijzen.", "error")
        return redirect(url_for("friends"))
    friend = get_friend(friend_id)
    if not friend or friend["is_super_admin"]:
        flash("Dit account kan niet gewijzigd worden.", "error")
        return redirect(url_for("friends"))
    action = request.form.get("action")
    if action == "promote":
        set_friend_admin(friend_id, 1)
        flash(f"{friend['name']} is nu beheerder.", "success")
    elif action == "demote":
        set_friend_admin(friend_id, 0)
        flash(f"{friend['name']} is geen beheerder meer.", "success")
    return redirect(url_for("friends"))


@app.route("/friends/<int:friend_id>/delete", methods=["POST"])
@login_required
def friend_delete(friend_id):
    me = g.friend
    friend = get_friend(friend_id)
    if not friend:
        flash("Vriend niet gevonden.", "error")
        return redirect(url_for("friends"))
    if friend_id != me["id"] and not me["is_admin"]:
        flash("Je kunt alleen je eigen account verwijderen.", "error")
        return redirect(url_for("friends"))
    if friend["is_super_admin"]:
        flash("De hoofdbeheerder kan niet verwijderd worden.", "error")
        return redirect(url_for("friends"))
    ok, message = delete_friend(friend_id)
    if not ok:
        flash(message, "error")
        return redirect(url_for("friends"))
    if friend_id == me["id"]:
        session.clear()
        flash("Je account is verwijderd. Tot ziens!", "success")
        return redirect(url_for("login"))
    flash(f"Account van {friend['name']} is verwijderd.", "success")
    return redirect(url_for("friends"))


@app.route("/stats")
@login_required
def stats():
    me = g.friend
    my_circles = get_circles(me["id"])
    my_circle_stats = get_circle_stats([c["id"] for c in my_circles])
    all_circle_stats = get_circle_stats() if me["is_admin"] else []
    return render_template(
        "stats.html",
        global_stats=get_global_stats(),
        my_circle_stats=my_circle_stats,
        all_circle_stats=all_circle_stats,
    )


@app.route("/notifications")
@login_required
def notifications():
    me = g.friend
    return render_template(
        "notifications.html",
        notifications_list=get_notifications(me["id"]),
    )


@app.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def notification_read(notification_id):
    mark_notification_read(notification_id, g.friend["id"])
    return redirect(url_for("notifications"))


@app.route("/notifications/read-all", methods=["POST"])
@login_required
def notifications_read_all():
    mark_all_notifications_read(g.friend["id"])
    flash("Alle meldingen als gelezen gemarkeerd.", "success")
    return redirect(url_for("notifications"))


@app.route("/messages", methods=["GET", "POST"])
@login_required
def messages():
    me = g.friend
    if request.method == "POST":
        recipient_id = request.form.get("recipient_id", type=int)
        body = request.form.get("body", "").strip()
        recipient = get_friend(recipient_id) if recipient_id else None
        visible_ids = {me["id"]} | {
            t["owner_id"] for t in get_visible_tools(me["id"])
        }
        if not recipient or not body:
            flash("Kies een ontvanger en schrijf een bericht.", "error")
        elif recipient["id"] not in visible_ids and not me["is_admin"]:
            flash(
                "Je kunt alleen berichten sturen naar vrienden met wie je "
                "een kring deelt.",
                "error",
            )
        else:
            send_message(me["id"], recipient_id, body)
            _notify(
                recipient_id,
                "bericht",
                f"Je hebt een nieuw bericht van {me['name']}.",
                "/messages",
            )
            flash(f"Bericht naar {recipient['name']} verstuurd.", "success")
        return redirect(url_for("messages"))
    visible_ids = {me["id"]} | {
        t["owner_id"] for t in get_visible_tools(me["id"])
    }
    contacts = [
        f
        for f in get_friends()
        if f["id"] in visible_ids and f["id"] != me["id"]
    ]
    if me["is_admin"]:
        contacts = [f for f in get_friends() if f["id"] != me["id"]]
    return render_template(
        "messages.html",
        inbox=get_inbox(me["id"]),
        sent=get_sent_messages(me["id"]),
        contacts=contacts,
    )


@app.route("/messages/<int:message_id>/read", methods=["POST"])
@login_required
def message_read(message_id):
    mark_message_read(message_id, g.friend["id"])
    return redirect(url_for("messages"))


@app.route("/circles/<int:circle_id>/tools")
@login_required
def circle_tools(circle_id):
    me = g.friend
    circle = get_circle(circle_id)
    if not circle:
        flash("Kring niet gevonden.", "error")
        return redirect(url_for("circles"))
    member_ids = {m["friend_id"] for m in get_circle_members(circle_id)}
    if not (me["is_admin"] or me["id"] in member_ids):
        flash("Je bent geen lid van deze kring.", "error")
        return redirect(url_for("circles"))
    tools_list = [t for t in get_tools() if t["owner_id"] in member_ids]
    return render_template(
        "circle_tools.html",
        circle=circle,
        tools_list=tools_list,
        links=get_linked_tools_map([t["id"] for t in tools_list]),
    )


@app.route("/circles", methods=["GET", "POST"])
@login_required
def circles():
    me = g.friend
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        admin_id = me["id"]
        chosen = request.form.get("circle_admin_id", type=int)
        if me["is_admin"] and chosen:
            chosen_friend = get_friend(chosen)
            if chosen_friend:
                admin_id = chosen
        if not name:
            flash("Geef de kring een naam.", "error")
        elif create_circle(name, admin_id) is None:
            flash("Er bestaat al een kring met deze naam.", "error")
        else:
            if admin_id == me["id"]:
                flash(
                    f"Kring '{name}' is aangemaakt; je bent automatisch "
                    "kringbeheerder.",
                    "success",
                )
            else:
                chosen_friend = get_friend(admin_id)
                flash(
                    f"Kring '{name}' is aangemaakt; {chosen_friend['name']} "
                    "is kringbeheerder.",
                    "success",
                )
        return redirect(url_for("circles"))
    my_circles = get_circles(me["id"])
    all_circles = get_circles() if me["is_admin"] else []
    return render_template(
        "circles.html",
        my_circles=my_circles,
        all_circles=all_circles,
        friends_list=get_friends(),
        members={c["id"]: get_circle_members(c["id"]) for c in my_circles},
        all_members={c["id"]: get_circle_members(c["id"]) for c in all_circles},
    )


@app.route("/circles/<int:circle_id>/members", methods=["POST"])
@login_required
def circle_members(circle_id):
    me = g.friend
    circle = get_circle(circle_id)
    if not circle:
        flash("Kring niet gevonden.", "error")
        return redirect(url_for("circles"))
    if not (me["is_admin"] or is_circle_admin(circle_id, me["id"])):
        flash(
            "Alleen de kringbeheerder of de beheerder kan leden beheren.",
            "error",
        )
        return redirect(url_for("circles"))
    action = request.form.get("action")
    member_id = request.form.get("member_id", type=int)
    if action == "add":
        member = get_friend(member_id) if member_id else None
        if not member:
            flash("Kies een vriend om toe te voegen.", "error")
        elif add_circle_member(circle_id, member_id):
            flash(f"{member['name']} is toegevoegd aan de kring.", "success")
        else:
            flash(f"{member['name']} is al lid van deze kring.", "error")
    elif action == "remove":
        if member_id and get_friend(member_id):
            remove_circle_member(circle_id, member_id)
            flash("Lid is verwijderd uit de kring.", "success")
    return redirect(url_for("circles"))


@app.route("/circles/<int:circle_id>/edit", methods=["GET", "POST"])
@login_required
def circle_edit(circle_id):
    me = g.friend
    circle = get_circle(circle_id)
    if not circle:
        flash("Kring niet gevonden.", "error")
        return redirect(url_for("circles"))
    if not me["is_admin"]:
        flash("Alleen de beheerder kan kringen hernoemen.", "error")
        return redirect(url_for("circles"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Geef de kring een naam.", "error")
        elif update_circle(circle_id, name):
            flash("Kringnaam is aangepast.", "success")
            return redirect(url_for("circles"))
        else:
            flash("Er bestaat al een kring met deze naam.", "error")
    return render_template("circle_edit.html", circle=circle)


@app.route("/circles/<int:circle_id>/delete", methods=["POST"])
@login_required
def circle_delete(circle_id):
    me = g.friend
    circle = get_circle(circle_id)
    if not circle:
        flash("Kring niet gevonden.", "error")
        return redirect(url_for("circles"))
    if not me["is_admin"]:
        flash("Alleen de beheerder kan kringen verwijderen.", "error")
        return redirect(url_for("circles"))
    delete_circle(circle_id)
    flash(f"Kring '{circle['name']}' is verwijderd.", "success")
    return redirect(url_for("circles"))


@app.route("/friends/<int:friend_id>/edit", methods=["GET", "POST"])
@login_required
def friend_edit(friend_id):
    friend = get_friend(friend_id)
    if not friend:
        flash("Vriend niet gevonden.", "error")
        return redirect(url_for("friends"))
    me = g.friend
    if not (me["is_admin"] or friend_id == me["id"]):
        flash(
            "Alleen de beheerder of de eigenaar van het account kan het "
            "aanpassen.",
            "error",
        )
        return redirect(url_for("friends"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        new_password = request.form.get("new_password", "")
        date_format = request.form.get("date_format", "").strip()
        if date_format not in DATE_FORMATS:
            date_format = None
        if not name or not email:
            flash("Naam en e-mail zijn verplicht.", "error")
        else:
            if date_format:
                set_friend_date_format(friend_id, date_format)
            error = update_friend(friend_id, name, email, phone)
            if error:
                flash(error, "error")
            else:
                if friend_id == me["id"]:
                    flash(
                        "Je eigen gegevens zijn aangepast.",
                        "success",
                    )
                else:
                    flash(f"Account van {name} is aangepast.", "success")
                if new_password:
                    if len(new_password) < 6:
                        flash(
                            "Nieuw wachtwoord moet minstens 6 tekens zijn.",
                            "error",
                        )
                    elif friend_id == me["id"]:
                        set_friend_password(
                            friend_id, generate_password_hash(new_password)
                        )
                        flash("Je wachtwoord is gewijzigd.", "success")
                    else:
                        reset_friend_password(
                            friend_id, generate_password_hash(new_password)
                        )
                        flash(
                            "Startwachtwoord ingesteld; het moet bij de "
                            "volgende login worden gewijzigd.",
                            "success",
                        )
                return redirect(url_for("profile" if friend_id == me["id"] else "friends"))
        friend.update(name=name or friend["name"], email=email or friend["email"], phone=phone)
    return render_template(
        "friend_edit.html",
        account=friend,
        date_formats=DATE_FORMATS,
    )


@app.route("/tools", methods=["GET", "POST"])
@login_required
def tools():
    if request.method == "POST":
        owner_id = request.form.get("owner_id", type=int)
        if not g.friend["is_admin"]:
            owner_id = g.friend["id"]
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        brand = request.form.get("brand", "").strip()
        model = request.form.get("model", "").strip()
        if not owner_id or not name or not brand or not model:
            flash(
                "Eigenaar, soort, merk en type zijn verplicht.",
                "error",
            )
            return redirect(url_for("tools"))
        tool_id = add_tool(owner_id, name, description, category, brand, model)
        if tool_id is None:
            flash("Dit gereedschap bestaat al.", "error")
        else:
            flash(f"Gereedschap '{name}' is geregistreerd.", "success")
        return redirect(url_for("tools"))
    me = g.friend
    tools_list = get_tools() if me["is_admin"] else get_visible_tools(me["id"])
    search = request.args.get("q", "").strip().lower()
    category_filter = request.args.get("category", "").strip()
    if search:
        tools_list = [
            t
            for t in tools_list
            if search in (t["name"] or "").lower()
            or search in (t["brand"] or "").lower()
            or search in (t["model"] or "").lower()
            or search in (t["description"] or "").lower()
        ]
    if category_filter:
        tools_list = [t for t in tools_list if t["category"] == category_filter]
    view = request.args.get("view") or session.get("tools_view", "cards")
    if view not in ("cards", "list"):
        view = "cards"
    session["tools_view"] = view
    sort = request.args.get("sort", "name")
    direction = request.args.get("dir", "asc")
    if direction not in ("asc", "desc"):
        direction = "asc"
    sort_keys = {
        "name": lambda t: (t["name"] or "").lower(),
        "category": lambda t: (t["category"] or "").lower(),
        "brand": lambda t: (t["brand"] or "").lower(),
        "owner": lambda t: (t["owner_name"] or "").lower(),
        "status": lambda t: t["loan_status"] or "beschikbaar",
    }
    if sort in sort_keys:
        tools_list = sorted(tools_list, key=sort_keys[sort], reverse=direction == "desc")
    return render_template(
        "tools.html",
        tools_list=tools_list,
        all_tools=tools_list,
        links=get_linked_tools_map([t["id"] for t in tools_list]),
        view=view,
        sort=sort,
        direction=direction,
        categories=get_distinct_values("category"),
        brands=get_distinct_values("brand"),
        search=search,
        category_filter=category_filter,
    )


def _can_manage(tool):
    friend = g.friend
    return bool(friend and (friend["is_admin"] or tool["owner_id"] == friend["id"]))


@app.route("/profile")
@login_required
def profile():
    me = g.friend
    tools_list = get_friend_tools(me["id"])
    my_loans = get_scoped_loans(me["id"], [] if not me["is_admin"] else None)
    return render_template(
        "profile.html",
        account=me,
        tools_list=tools_list,
        links=get_linked_tools_map([t["id"] for t in tools_list]),
        my_loans=my_loans,
    )


@app.route("/mytools")
@login_required
def my_tools():
    me = g.friend
    tools_list = get_friend_tools(me["id"])
    all_tools = get_tools() if me["is_admin"] else get_visible_tools(me["id"])
    return render_template(
        "mytools.html",
        tools_list=tools_list,
        all_tools=all_tools,
        links=get_linked_tools_map([t["id"] for t in tools_list]),
    )


@app.route("/tools/<int:tool_id>")
@login_required
def tool_detail(tool_id):
    me = g.friend
    tool = get_tool(tool_id)
    if not tool:
        flash("Gereedschap niet gevonden.", "error")
        return redirect(url_for("tools"))
    visible = get_visible_tools(me["id"])
    if not (me["is_admin"] or tool["owner_id"] == me["id"]
            or any(t["id"] == tool_id for t in visible)):
        flash(
            "Dit gereedschap is niet beschikbaar binnen jouw vriendenkringen.",
            "error",
        )
        return redirect(url_for("tools"))
    links = get_linked_tools_map([tool_id]).get(tool_id, [])
    active_loan = get_active_loan(tool_id)
    owner = get_friend(tool["owner_id"])
    return render_template(
        "tool_detail.html",
        tool=tool,
        owner=owner,
        links=links,
        available=active_loan is None,
        active_loan=active_loan,
        is_own=tool["owner_id"] == me["id"],
        can_manage=_can_manage(tool),
    )


@app.route("/tools/<int:tool_id>/edit", methods=["GET", "POST"])
@login_required
def tool_edit(tool_id):
    tool = get_tool(tool_id)
    if not tool:
        flash("Gereedschap niet gevonden.", "error")
        return redirect(url_for("tools"))
    if not _can_manage(tool):
        flash("Alleen de eigenaar of de beheerder kan dit gereedschap aanpassen.", "error")
        return redirect(url_for("tools"))
    if request.method == "POST":
        owner_id = request.form.get("owner_id", type=int)
        if not g.friend["is_admin"]:
            owner_id = tool["owner_id"]
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        brand = request.form.get("brand", "").strip()
        model = request.form.get("model", "").strip()
        if not owner_id or not name or not brand or not model:
            flash(
                "Eigenaar, soort, merk en type zijn verplicht.",
                "error",
            )
        elif update_tool(tool_id, owner_id, name, description, category, brand, model):
            flash(f"Gereedschap '{name}' is aangepast.", "success")
            return redirect(url_for("tools"))
        else:
            flash(
                "Deze combinatie van eigenaar en soort gereedschap bestaat al.",
                "error",
            )
        tool.update(
            owner_id=owner_id or tool["owner_id"],
            name=name or tool["name"],
            description=description,
            category=category,
            brand=brand,
            model=model,
        )
    return render_template(
        "tool_edit.html",
        tool=tool,
        categories=get_distinct_values("category"),
        brands=get_distinct_values("brand"),
    )


@app.route("/tools/<int:tool_id>/delete", methods=["POST"])
@login_required
def tool_delete(tool_id):
    tool = get_tool(tool_id)
    if not tool:
        flash("Gereedschap niet gevonden.", "error")
        return redirect(url_for("tools"))
    if not _can_manage(tool):
        flash("Alleen de eigenaar of de beheerder kan dit gereedschap verwijderen.", "error")
        return redirect(url_for("tools"))
    if delete_tool(tool_id):
        if tool.get("image_path"):
            image_file = os.path.join(
                app.static_folder, tool["image_path"]
            )
            try:
                os.remove(image_file)
            except OSError:
                pass
        flash(f"Gereedschap '{tool['name']}' is verwijderd.", "success")
    else:
        flash(
            "Dit gereedschap is uitgeleend of aangevraagd; "
            "wacht tot het is teruggekeerd.",
            "error",
        )
    return redirect(url_for("tools"))


@app.route("/tools/<int:tool_id>/link", methods=["POST"])
@login_required
def tool_link(tool_id):
    tool = get_tool(tool_id)
    linked_id = request.form.get("linked_tool_id", type=int)
    if not tool:
        flash("Gereedschap niet gevonden.", "error")
        return redirect(url_for("tools"))
    if not _can_manage(tool):
        flash(
            "Alleen de eigenaar of de beheerder kan dit gereedschap koppelen.",
            "error",
        )
        return redirect(url_for("tools"))
    if request.form.get("action") == "remove":
        if linked_id:
            remove_tool_link(tool_id, linked_id)
            flash("Koppeling verwijderd.", "success")
    else:
        linked = get_tool(linked_id) if linked_id else None
        if not linked:
            flash("Kies een gereedschap om te koppelen.", "error")
        elif linked["id"] == tool["id"]:
            flash("Een gereedschap kan niet met zichzelf gekoppeld worden.", "error")
        elif linked["owner_id"] != tool["owner_id"]:
            flash(
                "Gereedschap kan alleen gekoppeld worden aan ander gereedschap "
                "van dezelfde eigenaar.",
                "error",
            )
        elif add_tool_link(tool_id, linked_id):
            flash(f"'{tool['name']}' is gekoppeld aan '{linked['name']}'.", "success")
        else:
            flash("Deze koppeling bestaat al.", "error")
    return redirect(url_for("tools"))


@app.route("/tools/<int:tool_id>/image", methods=["POST"])
@login_required
def tool_image(tool_id):
    tool = get_tool(tool_id)
    if not tool:
        flash("Gereedschap niet gevonden.", "error")
        return redirect(url_for("tools"))
    if not _can_manage(tool):
        flash(
            "Alleen de eigenaar of de beheerder kan het plaatje van dit "
            "gereedschap beheren.",
            "error",
        )
        return redirect(url_for("tools"))
    action = request.form.get("action")
    if action == "url":
        image_url = request.form.get("image_url", "").strip()
        image_path = download_image(image_url, tool_id) if image_url else None
        if image_path:
            set_tool_image(tool_id, image_path)
            flash("Plaatje toegevoegd en op de server opgeslagen.", "success")
        else:
            flash(
                "Deze afbeeldings-URL kon niet worden gedownload (jpg, png, "
                "webp of gif, min. 200x200, max. 5 MB).",
                "error",
            )
    elif action == "upload":
        image_path = upload_image(request.files.get("image_file"), tool_id)
        if image_path:
            set_tool_image(tool_id, image_path)
            flash("Plaatje geüpload.", "success")
        else:
            flash(
                "Geen geldig afbeeldingsbestand (jpg, png, webp of gif, "
                "max. 5 MB).",
                "error",
            )
    elif action == "remove":
        remove_tool_image(tool_id)
        flash("Plaatje verwijderd.", "success")
    return redirect(url_for("tools"))


@app.route("/loans", methods=["GET", "POST"])
@login_required
def loans():
    friend = g.friend
    if request.method == "POST":
        action = request.form.get("action")
        tool_id = request.form.get("tool_id", type=int)
        if action == "request":
            if not tool_id:
                flash("Kies een gereedschap.", "error")
            else:
                tool = get_tool(tool_id)
                visible = get_visible_tools(friend["id"])
                note = request.form.get("note", "").strip()
                date_from = request.form.get("date_from", "").strip()
                date_until = request.form.get("date_until", "").strip()
                if not date_from or not date_until:
                    flash(
                        "Geef een vanaf- en tot-datum op voor het leenverzoek.",
                        "error",
                    )
                elif date_until < date_from:
                    flash(
                        "De tot-datum mag niet voor de vanaf-datum liggen.",
                        "error",
                    )
                elif tool and tool["owner_id"] == friend["id"]:
                    flash("Je kunt niet je eigen gereedschap lenen.", "error")
                elif tool and not any(
                    t["id"] == tool_id for t in visible
                ):
                    flash(
                        "Dit gereedschap is niet beschikbaar binnen jouw "
                        "vriendenkringen.",
                        "error",
                    )
                elif create_loan_request(
                    tool_id, friend["id"], note or None, date_from, date_until
                ):
                    flash("Leenverzoek aangemaakt.", "success")
                    owner = get_friend(tool["owner_id"])
                    _notify(
                        owner["id"],
                        "leenverzoek",
                        f"{friend['name']} wil '{tool['name']}' lenen van "
                        f"{date_from} tot {date_until}.",
                        f"/tools/{tool_id}",
                        tool_id,
                    )
                    combi_ids = request.form.getlist("combi_tool_ids")
                    for combi_id in combi_ids:
                        if not str(combi_id).isdigit():
                            continue
                        combi_tool = get_tool(int(combi_id))
                        if not combi_tool or combi_tool["owner_id"] == friend["id"]:
                            continue
                        if create_loan_request(
                            int(combi_id),
                            friend["id"],
                            note or None,
                            date_from,
                            date_until,
                        ):
                            combi_owner = get_friend(combi_tool["owner_id"])
                            _notify(
                                combi_owner["id"],
                                "leenverzoek",
                                f"{friend['name']} wil '{combi_tool['name']}' "
                                f"lenen van {date_from} tot {date_until}.",
                                f"/tools/{combi_tool['id']}",
                                combi_tool["id"],
                            )
                            flash(
                                f"Combi-gereedschap '{combi_tool['name']}' is "
                                "met hetzelfde datumbereik aangevraagd.",
                                "success",
                            )
                else:
                    flash("Dit gereedschap is momenteel niet beschikbaar.", "error")
            return redirect(url_for("loans"))
        if action in ("approve", "reject", "return"):
            loan_id = request.form.get("loan_id", type=int)
            handler = {
                "approve": approve_loan,
                "reject": reject_loan,
                "return": return_loan,
            }[action]
            if loan_id and handler(loan_id):
                flash(
                    {
                        "approve": "Uitlening goedgekeurd.",
                        "reject": "Leenverzoek geweigerd.",
                        "return": "Gereedschap is teruggekeerd.",
                    }[action],
                    "success",
                )
                loan = get_loan(loan_id)
                if loan:
                    borrower = get_friend(loan["borrower_id"])
                    tool = get_tool(loan["tool_id"])
                    if action == "approve":
                        _notify(
                            loan["borrower_id"],
                            "goedgekeurd",
                            f"Je leenverzoek voor '{tool['name']}' is "
                            "goedgekeurd.",
                            f"/tools/{loan['tool_id']}",
                            loan_id,
                        )
                    elif action == "reject":
                        _notify(
                            loan["borrower_id"],
                            "geweigerd",
                            f"Je leenverzoek voor '{tool['name']}' is geweigerd.",
                            f"/tools/{loan['tool_id']}",
                            loan_id,
                        )
                    elif action == "return":
                        _notify(
                            loan["borrower_id"],
                            "teruggekeerd",
                            f"'{tool['name']}' is als teruggekeerd "
                            "geregistreerd.",
                            f"/tools/{loan['tool_id']}",
                            loan_id,
                        )
            else:
                flash("Actie niet mogelijk.", "error")
            return redirect(url_for("loans"))
    available_tools = (
        get_tools(available_only=True)
        if friend["is_admin"]
        else [
            t for t in get_visible_tools(friend["id"]) if not t["active_loan_id"]
        ]
    )
    all_tools = get_tools()
    links_map = get_linked_tools_map([t["id"] for t in all_tools])
    combi_options = {}
    for tool in available_tools:
        options = []
        for link in links_map.get(tool["id"], []):
            linked = next(
                (t for t in available_tools if t["id"] == link["linked_id"]), None
            )
            if linked:
                options.append(linked)
        if options:
            combi_options[tool["id"]] = options
    # scope bepalen: beheerder -> alles; kringbeheerder -> eigen + kringen;
    # gewone gebruiker -> alleen eigen uitleningen
    if friend["is_admin"]:
        admin_circle_ids = None
    else:
        admin_circle_ids = [
            c["id"] for c in get_circles(friend["id"]) if c.get("is_circle_admin")
        ]
    loans_list = get_scoped_loans(friend["id"], admin_circle_ids)

    # filters
    status_filter = request.args.get("status", "alle")
    if status_filter not in STATUS_LABELS:
        status_filter = "alle"
    circle_filter = request.args.get("circle_id", type=int)
    if status_filter != "alle":
        loans_list = [l for l in loans_list if l["status"] == status_filter]
    if circle_filter:
        member_ids = {m["friend_id"] for m in get_circle_members(circle_filter)}
        loans_list = [
            l
            for l in loans_list
            if l["owner_id"] in member_ids or l["borrower_id"] in member_ids
        ]

    # sortering
    sort = request.args.get("sort", "created_at")
    direction = request.args.get("dir", "desc")
    if direction not in ("asc", "desc"):
        direction = "desc"
    sort_keys = {
        "tool": lambda l: (l["tool_name"] or "").lower(),
        "owner": lambda l: (l["owner_name"] or "").lower(),
        "borrower": lambda l: (l["borrower_name"] or "").lower(),
        "status": lambda l: l["status"],
        "lent_at": lambda l: l["lent_at"] or "",
        "returned_at": lambda l: l["returned_at"] or "",
        "created_at": lambda l: l["created_at"],
    }
    if sort in sort_keys:
        loans_list = sorted(
            loans_list, key=sort_keys[sort], reverse=direction == "desc"
        )

    # kringen voor de filterlijst
    if friend["is_admin"]:
        filter_circles = get_circles()
    elif admin_circle_ids:
        filter_circles = [
            c for c in get_circles(friend["id"]) if c.get("is_circle_admin")
        ]
    else:
        filter_circles = []
    return render_template(
        "loans.html",
        friend=friend,
        available_tools=available_tools,
        friend_tools=get_friend_tools(friend["id"]),
        transactions=get_friend_transactions(friend["id"]),
        combi_suggestions=get_combi_suggestions(friend["id"]),
        loans_list=loans_list,
        combi_options=combi_options,
        status_filter=status_filter,
        circle_filter=circle_filter,
        filter_circles=filter_circles,
        sort=sort,
        direction=direction,
    )


@app.cli.command("init-db")
def init_db_command():
    init_db()
    print("Database geïnitialiseerd.")


@app.cli.command("ensure-admin")
def ensure_admin_command():
    """Controleert de beheerder en maakt deze indien nodig aan."""
    from db.db import get_friend_by_name

    name = os.environ.get("ADMIN_NAME", "admin")
    email = os.environ.get("ADMIN_EMAIL", "admin@localhost")
    try:
        ensure_schema()
        ensure_admin()
    except Exception as exc:
        print(f"FOUT: schema of beheerder kon niet worden gecontroleerd: {exc}")
        print(
            "Controleer of de database bestaat en of de databasegegevens in de "
            ".env kloppen (DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME)."
        )
        return 1
    admin = get_friend_by_email(email)
    if admin and admin["is_admin"]:
        state = (
            "moet nog een wachtwoord kiezen bij de eerste login"
            if admin["must_change_password"]
            else "wachtwoord al ingesteld"
        )
        print(
            f"Beheerder '{name}' ({email}) aanwezig (id={admin['id']}); {state}."
        )
        print(
            "Bestaande beheerders worden nooit automatisch gewijzigd; "
            "wijzig het admin-wachtwoord via de app of de database."
        )
    else:
        print(f"Geen beheerder gevonden met e-mailadres '{email}'.")
        print(
            "Bestaat er al een beheerder met een ander e-mailadres? "
            "Dan worden ADMIN_NAME/ADMIN_EMAIL genegeerd; pas de gegevens in "
            "de database aan of verwijder die beheerder en draai dit "
            "commando opnieuw."
        )


if __name__ == "__main__":
    try:
        init_db()
        ensure_schema()
        ensure_admin()
    except Exception as exc:
        print(
            f"Waarschuwing: database-initialisatie is overgeslagen ({exc}). "
            "Maak de tabellen handmatig aan met: "
            "sudo mariadb gereedschap_leensysteem < db/schema.sql"
        )
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    if host not in ("127.0.0.1", "localhost") and debug:
        print(
            "Waarschuwing: debug-mode staat aan terwijl de app op een niet-lokaal "
            "adres luistert; zet FLASK_DEBUG=0 voor productiegebruik."
        )
    app.run(host=host, port=port, debug=debug)
