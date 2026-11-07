# hebjijvoormij

gereedschap uitleensysteem

## Functies

- **Vrienden** – registreer vrienden met naam, e-mail en telefoonnummer.
- **Gereedschapscatalogus** – registreer gereedschap per eigenaar, met
  omschrijving en categorie.
  Zijn merk en type bekend, dan wordt er automatisch een plaatje
  opgezocht en op de gereedschapskaart getoond (ook handmatig te
  zoeken of via een eigen afbeeldings-URL toe te voegen).
- **Combi-gereedschap** – koppel bijbehorend gereedschap aan elkaar
  (bv. speciale boren bij een boormachine); op de kaart terug te
  vinden onder "Goed te combineren met".
- **Uitleningen met status** – leenverzoeken doorlopen de statuscyclus
  `aangevraagd` → `uitgeleend` → `teruggekeerd` (of `geweigerd`).
- **Overzichten** – openstaande uitleningen en verzoeken, per-vriend statistieken,
  en een persoonlijk transactieoverzicht.

## Technologie

- Python 3.12, Flask
- MySQL / MariaDB (mysql-connector-python, connection pooling)
- Server-side templates (Jinja2) en één CSS-bestand

## Installatie

1. **Vereisten**: Python 3.10+ en een draaiende MySQL- of MariaDB-server.

2. **Databasegebruiker** (eenmalig, als root):

   ```sql
   CREATE USER 'gereedschap'@'localhost' IDENTIFIED BY 'gereedschap';
   GRANT ALL PRIVILEGES ON gereedschap_leensysteem.* TO 'gereedschap'@'localhost';
   ```

3. **Omgevingsvariabelen** (zie `.env.example`):

   ```bash
   export DB_HOST=127.0.0.1
   export DB_PORT=3306
   export DB_USER=gereedschap
   export DB_PASSWORD=gereedschap
   export DB_NAME=gereedschap_leensysteem
   export DB_USER_ROOT=root
   export DB_PASSWORD_ROOT=<jouw root-wachtwoord>
   export SECRET_KEY=<iets-geheims>
   ```

4. **Installeren en starten**:

   ```bash
   pip install -r requirements.txt
   python app.py
   ```

   De app maakt de database en tabellen automatisch aan (`db/schema.sql`) en
   start op <http://127.0.0.1:5000>.

## Gebruik

1. Registreer je vrienden onder **Vrienden**.
2. Kies rechtsboven een "actieve vriend" om door zijn/haar ogen te kijken.
3. Registreer gereedschap onder **Gereedschap** (kies de eigenaar).
4. Onder **Uitleningen** maak je een leenverzoek aan; de eigenaar keurt het
   goed of wijst het af, en het gereedschap wordt teruggegeven via
   "Terugontvangen".
5. Het **Overzicht** toont alle openstaande leningen en statistieken per vriend.

## Database-schema

Zie `db/schema.sql`. Belangrijk: de tabel `loans` heeft een unieke sleutel op
`(tool_id, active_flag)` via een virtuele kolom, zodat gereedschap nooit
tegelijk aan twee mensen uitgeleerd kan zijn.
