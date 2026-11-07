import os

from flask import Flask, flash, redirect, render_template, request, url_for
from db.db import (
    Database,
    add_friend,
    add_tool,
    add_tool_link,
    approve_loan,
    create_loan_request,
    get_friend,
    get_friend_stats,
    get_combi_suggestions,
    get_friend_tools,
    get_friend_transactions,
    get_linked_tools_map,
    get_overview,
    get_tool,
    get_tools,
    init_db,
    remove_tool_image,
    remove_tool_link,
    reject_loan,
    return_loan,
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
    friend_id = request.args.get("friend_id", type=int)
    friend = get_friend(friend_id) if friend_id else None
    return {"friends": Database().get_friends(), "friend": friend}


def _selected_friend():
    friend_id = request.args.get("friend_id", type=int)
    if friend_id:
        friend = get_friend(friend_id)
        if friend:
            return friend
    return None


@app.route("/")
def index():
    friend = _selected_friend()
    return render_template(
        "index.html",
        friend=friend,
        overview=get_overview(),
        stats=get_friend_stats(),
    )


@app.route("/friends", methods=["GET", "POST"])
def friends():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        if not name:
            flash("Naam is verplicht.", "error")
        elif add_friend(name, email, phone):
            flash(f"Vriend {name} is geregistreerd.", "success")
        else:
            flash("Deze vriend bestaat al.", "error")
        return redirect(url_for("friends"))
    return render_template("friends.html", friends_list=Database().get_friends())


@app.route("/tools", methods=["GET", "POST"])
def tools():
    friend = _selected_friend()
    if request.method == "POST":
        owner_id = request.form.get("owner_id", type=int)
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        brand = request.form.get("brand", "").strip()
        model = request.form.get("model", "").strip()
        if not owner_id or not name:
            flash("Eigenaar en naam zijn verplicht.", "error")
            return redirect(url_for("tools", friend_id=owner_id))
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
        return redirect(url_for("tools", friend_id=owner_id))
    tools_list = get_tools(friend["id"] if friend else None)
    return render_template(
        "tools.html",
        friend=friend,
        tools_list=tools_list,
        all_tools=get_tools(),
        links=get_linked_tools_map([t["id"] for t in tools_list]),
    )


@app.route("/tools/<int:tool_id>/link", methods=["POST"])
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
            flash(
                f"'{tool['name']}' is gekoppeld aan '{linked['name']}'.", "success"
            )
        else:
            flash("Deze koppeling bestaat al.", "error")
    return redirect(url_for("tools", friend_id=request.form.get("friend_id", type=int)))


@app.route("/tools/<int:tool_id>/image", methods=["POST"])
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
    return redirect(url_for("tools", friend_id=request.form.get("friend_id", type=int)))


@app.route("/loans", methods=["GET", "POST"])
def loans():
    friend = _selected_friend()
    if request.method == "POST":
        action = request.form.get("action")
        tool_id = request.form.get("tool_id", type=int)
        if action == "request":
            borrower_id = request.form.get("borrower_id", type=int)
            if not tool_id or not borrower_id:
                flash("Kies een vriend en een gereedschap.", "error")
            else:
                tool = get_tool(tool_id)
                if tool and tool["owner_id"] == borrower_id:
                    flash("Je kunt niet je eigen gereedschap lenen.", "error")
                elif create_loan_request(tool_id, borrower_id):
                    flash("Leenverzoek aangemaakt.", "success")
                    suggestions = get_combi_suggestions(borrower_id)
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
            return redirect(url_for("loans", friend_id=borrower_id))
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
            return redirect(url_for("loans", friend_id=request.form.get("friend_id")))
    return render_template(
        "loans.html",
        friend=friend,
        available_tools=get_tools(available_only=True),
        friend_tools=get_friend_tools(friend["id"] if friend else None),
        transactions=get_friend_transactions(friend["id"] if friend else None),
        combi_suggestions=get_combi_suggestions(friend["id"])
        if friend
        else [],
    )


@app.cli.command("init-db")
def init_db_command():
    init_db()
    print("Database geïnitialiseerd.")


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
