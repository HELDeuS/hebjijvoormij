import os
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
    add_friend,
    add_tool,
    add_tool_link,
    approve_loan,
    create_loan_request,
    get_combi_suggestions,
    get_friend,
    get_friend_by_name,
    get_friend_stats,
    get_friend_tools,
    get_friend_transactions,
    get_linked_tools_map,
    get_overview,
    get_tool,
    get_tools,
    ensure_admin,
    init_db,
    remove_tool_image,
    remove_tool_link,
    reject_loan,
    return_loan,
    set_friend_password,
    set_tool_image,
)
from images import download_image, find_and_store_image

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-key-verander-dit")

STATUS_LABELS = {
    "aangevraagd": "Aangevraagd",
    "uitgeleend": "Uitgeleend",
    "teruggekeerd": "Teruggekeerd",
    "geweigerd": "Geweigerd",
}

app.jinja_env.globals.update(STATUS_LABELS=STATUS_LABELS)


@app.context_processor
def inject_globals():
    return {
        "friends": Database().get_friends() if g.get("friend") else [],
        "friend": g.get("friend"),
    }


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.get("friend"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@app.before_request
def load_current_friend():
    friend_id = session.get("friend_id")
    g.friend = get_friend(friend_id) if friend_id else None


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.friend:
        return redirect(url_for("index"))
    try:
        ensure_admin()
    except Exception as exc:
        app.logger.warning(
            "Beheerder kon niet worden aangemaakt/controleerd: %s. "
            "Draai 'venv/bin/flask --app app ensure-admin' voor diagnostiek.",
            exc,
        )
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
        new_password = request.form.get("new_password", "")
        friend = get_friend_by_name(name)
        if not friend:
            flash("Onbekende naam. Ben je al geregistreerd als vriend?", "error")
        elif friend["password_hash"] is None:
            set_friend_password(friend["id"], generate_password_hash(password))
            session["friend_id"] = friend["id"]
            flash(
                f"Welkom {friend['name']}! Je wachtwoord is ingesteld; "
                "gebruik het voortaan om in te loggen.",
                "success",
            )
            return redirect(url_for("index"))
        elif not check_password_hash(friend["password_hash"], password):
            flash("Onjuist wachtwoord.", "error")
        elif friend["must_change_password"]:
            if len(new_password) < 6:
                flash(
                    "Dit is je eerste login: kies een nieuw wachtwoord van "
                    "minstens 6 tekens.",
                    "warning",
                )
                return render_template("login.html", show_change=True, name=name)
            set_friend_password(friend["id"], generate_password_hash(new_password))
            session["friend_id"] = friend["id"]
            flash(
                f"Welkom {friend['name']}! Je wachtwoord is gewijzigd.", "success"
            )
            return redirect(url_for("index"))
        else:
            session["friend_id"] = friend["id"]
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
    return render_template("index.html", overview=get_overview(), stats=get_friend_stats())


@app.route("/friends", methods=["GET", "POST"])
@login_required
def friends():
    if request.method == "POST":
        if not g.friend["is_admin"]:
            flash("Alleen de beheerder kan nieuwe vrienden toevoegen.", "error")
            return redirect(url_for("friends"))
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        if not name or len(password) < 6:
            flash("Naam is verplicht en het wachtwoord moet minstens 6 tekens zijn.", "error")
        else:
            friend_id = add_friend(
                name,
                email,
                phone,
                generate_password_hash(password),
                must_change_password=True,
            )
            if friend_id is None:
                flash("Deze vriend bestaat al.", "error")
            else:
                flash(
                    f"Vriend {name} is geregistreerd; "
                    f"hij/zij kiest bij de eerste login een eigen wachtwoord.",
                    "success",
                )
        return redirect(url_for("friends"))
    return render_template("friends.html", friends_list=Database().get_friends())


@app.route("/tools", methods=["GET", "POST"])
@login_required
def tools():
    if request.method == "POST":
        owner_id = request.form.get("owner_id", type=int)
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        brand = request.form.get("brand", "").strip()
        model = request.form.get("model", "").strip()
        if not owner_id or not name:
            flash("Eigenaar en naam zijn verplicht.", "error")
            return redirect(url_for("tools"))
        tool_id = add_tool(owner_id, name, description, category, brand, model)
        if tool_id is None:
            flash("Dit gereedschap bestaat al.", "error")
        else:
            flash(f"Gereedschap '{name}' is geregistreerd.", "success")
            if brand or model:
                image_path = find_and_store_image(tool_id, name, brand, model)
                if image_path:
                    set_tool_image(tool_id, image_path)
                    flash("Er is automatisch een plaatje opgezocht en toegevoegd.", "success")
                else:
                    flash(
                        "Geen bruikbaar plaatje gevonden; je kunt het handmatig "
                        "toevoegen via 'Plaatje zoeken' of een afbeeldings-URL.",
                        "warning",
                    )
        return redirect(url_for("tools"))
    tools_list = get_tools()
    return render_template(
        "tools.html",
        tools_list=tools_list,
        all_tools=tools_list,
        links=get_linked_tools_map([t["id"] for t in tools_list]),
    )


@app.route("/tools/<int:tool_id>/link", methods=["POST"])
@login_required
def tool_link(tool_id):
    tool = get_tool(tool_id)
    linked_id = request.form.get("linked_tool_id", type=int)
    if not tool:
        flash("Gereedschap niet gevonden.", "error")
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
    action = request.form.get("action")
    if action == "search":
        image_path = find_and_store_image(
            tool_id, tool["name"], tool.get("brand"), tool.get("model")
        )
        if image_path:
            set_tool_image(tool_id, image_path)
            flash("Plaatje gevonden en toegevoegd.", "success")
        else:
            flash("Geen bruikbaar plaatje gevonden.", "warning")
    elif action == "url":
        image_url = request.form.get("image_url", "").strip()
        image_path = download_image(image_url, tool_id) if image_url else None
        if image_path:
            set_tool_image(tool_id, image_path)
            flash("Plaatje toegevoegd.", "success")
        else:
            flash("Deze afbeeldings-URL kon niet worden gedownload.", "error")
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
                if tool and tool["owner_id"] == friend["id"]:
                    flash("Je kunt niet je eigen gereedschap lenen.", "error")
                elif create_loan_request(tool_id, friend["id"]):
                    flash("Leenverzoek aangemaakt.", "success")
                    suggestions = get_combi_suggestions(friend["id"])
                    relevant = [s for s in suggestions if s["primary_tool_id"] == tool_id]
                    if relevant:
                        names = ", ".join(s["name"] for s in relevant)
                        flash(
                            f"Tip: goed te combineren met {names} — "
                            "kijk bij de combi-suggesties om ze mee te lenen.",
                            "warning",
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
            else:
                flash("Actie niet mogelijk.", "error")
            return redirect(url_for("loans"))
    return render_template(
        "loans.html",
        friend=friend,
        available_tools=get_tools(available_only=True),
        friend_tools=get_friend_tools(friend["id"]),
        transactions=get_friend_transactions(friend["id"]),
        combi_suggestions=get_combi_suggestions(friend["id"]),
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
    try:
        ensure_admin()
    except Exception as exc:
        print(f"FOUT: beheerder kon niet worden aangemaakt: {exc}")
        print(
            "Controleer of de database en tabellen bestaan:\n"
            "  sudo mariadb gereedschap_leensysteem < db/schema.sql"
        )
        return 1
    admin = get_friend_by_name(name)
    if admin and admin["is_admin"]:
        state = (
            "moet nog een wachtwoord kiezen bij de eerste login"
            if admin["must_change_password"]
            else "wachtwoord al ingesteld"
        )
        print(f"Beheerder '{name}' aanwezig (id={admin['id']}); {state}.")
        print(
            "Bestaande beheerders worden nooit automatisch gewijzigd; "
            "wijzig het admin-wachtwoord via de app of de database."
        )
    else:
        print(f"Geen beheerder gevonden onder de naam '{name}'.")
        print(
            "Bestaat er al een beheerder onder een andere naam? "
            "Dan wordt ADMIN_NAME genegeerd; pas de naam in de database aan "
            "of verwijder die beheerder en draai dit commando opnieuw."
        )


if __name__ == "__main__":
    try:
        init_db()
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
