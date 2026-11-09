# hebjijvoormij

Gereedschap-uitleensysteem voor vriendenkringen: registreer je
gereedschap, deel het met je kringgenoten en houd uitleningen bij met
meldingen en berichten.

> ## ⚠️ Disclaimer
>
> **Dit project is met behulp van AI ontwikkeld.** De code is **nog niet
> door mensen gecontroleerd of gereviewed** en is **totaal niet voor
> productiedoeleinden bedoeld**. Gebruik is volledig op eigen risico:
> er zijn geen garanties voor juistheid, veiligheid of continuïteit.
> Zet deze software niet in op systemen of netwerken waar
> gevoelige gegevens of kritieke processen op staan.

## Functies

### Accounts en rollen
- Zelfregistratie; de beheerder keurt nieuwe accounts goed of wijst ze af.
- De beheerder kan accounts aanmaken, aanpassen, op non-actief zetten
  (met reden, zichtbaar bij het inloggen), verwijderen en extra
  beheerders aanwijzen.
- Gebruikers beheren hun eigen account via het profiel: gegevens,
  wachtwoord, account verwijderen.
- Rate limiting op het inloggen: na 5 mislukte pogingen binnen
  15 minuten is het account een kwartier geblokkeerd.
- Datumnotatie per gebruiker te kiezen (Nederlands 31-12-2026,
  ISO 2026-12-31, Amerikaans 12/31/2026); de beheerder stelt de
  standaard voor nieuwe gebruikers in.

### Gereedschapscatalogus
- Registratie verplicht met soort, merk en type, plus optioneel
  omschrijving en categorie (vrij te typen of kiezen uit eerder
  gebruikte waardes).
- **Kaart- en lijstweergave**, sorteerbaar (Soort, Merk, Categorie,
  Eigenaar, Status), doorzoekbaar (naam, merk, type, omschrijving)
  en filterbaar op categorie; de lijst toont thumbnails. De
  voorkeur wordt per gebruiker onthouden.
- Plaatjes: uploaden (jpg, png, webp of gif, max. 5 MB) of een
  directe afbeeldings-URL; de app downloadt en bewaart de
  afbeelding op de server (met validatie op type en afmetingen).
- Beheerknoppen (aanpassen, verwijderen, plaatje) zijn alleen
  zichtbaar voor de eigenaar en de beheerder; verwijderen is
  geblokkeerd zolang gereedschap is uitgeleend of aangevraagd.
- **Combi-gereedschap**: koppel bijbehorend gereedschap (bv. boren
  bij een boormachine); bij een leenverzoek zijn combi-tools
  direct aanvinkbaar en krijgen ze hetzelfde datumbereik en dezelfde
  notitie.

### Uitleningen
- Leenverzoeken met **verplichte vanaf- en tot-datum** en een
  optionele notitie; de statuscyclus is `aangevraagd` →
  `uitgeleend` → `teruggekeerd` (of `geweigerd`).
- Aanvragen kan vanaf de gereedschapskaart (het gereedschap is dan
  al ingevuld) of via het formulier op de uitleningenpagina.
- De eigenaar keurt goed of weigert — vanaf de detailpagina of de
  uitleningenpagina; terugkeer registreert hij met "Teruggekeerd".
- Rolgebaseerd overzicht: iedereen ziet zijn eigen uitleningen, een
  kringbeheerder ook die van zijn kringen, de beheerder alles — met
  filters op status en kring en sorteerbare kolommen (periode en
  notitie inbegrepen).

### Meldingen en e-mail
- Meldingenbel met ongelezen-teller: leenverzoeken, goedkeuringen,
  weigeringen, terugkeer, nieuwe berichten en **dagelijkse
  herinneringen** voor uitleningen die over de afgesproken
  einddatum heen zijn.
- Bij elke melding wordt (indien SMTP geconfigureerd) ook een
  e-mail gestuurd; mislukte verzending breekt de app nooit.

### Berichten
- Gebruikers sturen berichten naar kringgenoten (de beheerder naar
  iedereen), met inbox, verzonden items en gelezen-markeren.

### Vriendenkringen
- Iedereen kan een kring aanmaken en wordt automatisch
  kringbeheerder; die beheert de leden. De beheerder kan kringen
  hernoemen, verwijderen en bij aanmaak een andere kringbeheerder
  kiezen.
- Gereedschap is alleen zichtbaar en leenbaar binnen gedeelde
  kringen.
- **Kring-gereedschap**: alle gereedschap van een kring in één
  overzicht, met dezelfde kaart-/lijstweergave, sortering, zoek- en
  filteropties als de catalogus.

### Overzichten en statistieken
- Openstaande uitleningen en verzoeken op de hoofdpagina, met
  klikbare gereedschapsnamen.
- Statistieken: algemene totalen, cijfers per kring en voor de
  beheerder de totalen van alle kringen; per-vriend statistieken en
  een persoonlijk transactieoverzicht op het profiel.

## Beveiliging

- **CSRF**: elk formulier bevat een sessie-gebonden token; elke POST
  zonder geldig token wordt geweigerd (HTTP 400).
- **Toegangscontrole**: leningen goedkeuren/weigeren/teruggeven kan
  alleen de eigenaar van het gereedschap (of de beheerder);
  gereedschapbeheer, plaatjes en accountgegevens zijn eveneens
  eigenaar-gebonden.
- **SQL**: alle queries zijn geparametriseerd (geen SQL-injectie).
- **XSS**: alle uitvoer wordt door Jinja2 automatisch geëscapet.
- **SSRF**: de plaatjes-URL-functie weigert interne, lokale en
  gereserveerde adressen en volgt geen redirects.
- **Uploads**: bestanden worden met Pillow gevalideerd op echt
  afbeeldingsformaat en minimale afmetingen.
- **Sessies**: `SECRET_KEY` is verplicht (de app start zonder niet);
  cookies zijn HttpOnly en SameSite=Lax.
- **Inloggen**: rate limiting (5 pogingen per kwartier per account),
  gehashte wachtwoorden (scrypt) en generieke foutmeldingen (geen
  gebruikersnaam-enumeratie).

## Schaalbaarheid

De app is gebouwd voor kleine kringen (tientallen gebruikers) maar
blijft tot enkele honderden gebruikers bruikbaar:

- **E-mail en herinneringen** worden in een achtergronddraad verstuurd;
  een trage of onbereikbare SMTP-server blokkeert geen requests meer.
- **Grote lijsten** (catalogus, kring-gereedschap, uitleningen) zijn
  gepagineerd op 50 items per pagina.
- **gunicorn** draait met 5 workers (vuistregel 2×CPU+1; pas aan op
  je eigen server). Statische bestanden serveert nginx direct.
- De databasepool staat op 10 verbindingen per worker; verhoog
  MariaDB's `max_connections` als je veel workers draait.

## Technologie

- Python 3.10+ / Flask, server-side templates (Jinja2), één CSS-bestand
- MySQL / MariaDB (mysql-connector-python, connection pooling,
  self-healing migraties)
- gunicorn als productie-webserver; Pillow voor afbeeldingsvalidatie
- Sessies met ondertekende cookies (SECRET_KEY)

## Snelle start (ontwikkeling)

Vereisten: Python 3.10+ en een draaiende MySQL- of MariaDB-server.

```bash
pip install -r requirements.txt
export DB_HOST=127.0.0.1 DB_PORT=3306 DB_USER=gereedschap \
       DB_PASSWORD=gereedschap DB_NAME=gereedschap_leensysteem \
       SECRET_KEY=ontwikkelsleutel ADMIN_EMAIL=admin@localhost \
       ADMIN_PASSWORD=beheer123
python app.py
```

De app maakt de database, tabellen en het beheerdersaccount
automatisch aan (root-toegang via `DB_USER_ROOT`/`DB_PASSWORD_ROOT`,
of maak de database vooraf handmatig aan — zie stap 3 en 5 hieronder).
Bereikbaar op <http://127.0.0.1:5000>. Log in als beheerder
(`admin@localhost` / `beheer123`) en kies direct een nieuw wachtwoord.

## Installatie op Ubuntu Server (volledige handleiding)

Deze handleiding gaat uit van Ubuntu Server 22.04 of 24.04 en doorloopt
de stappen in deze volgorde: pakketten → app-code → database →
configuratie → tabellen en test → service → bereikbaarheid.

### 1. Systeempakketten

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git mariadb-server nginx
```

Beveilig MariaDB (root-wachtwoord instellen, anonieme gebruikers weg):

```bash
sudo mysql_secure_installation
```

### 2. App-code ophalen

Maak een eigen systeemgebruiker en zet de code in `/opt/hebjijvoormij/app`:

```bash
sudo adduser --system --group --home /opt/hebjijvoormij hebjijvoormij
sudo -u hebjijvoormij git clone https://github.com/HELDeuS/hebjijvoormij.git /opt/hebjijvoormij/app
```

Bestaat de map al (herinstallatie of update vóór de eerste start), werk de
code dan bij in plaats van opnieuw te klonen:

```bash
sudo -u hebjijvoormij git -C /opt/hebjijvoormij/app pull
```

Maak de Python-omgeving en installeer de dependencies:

```bash
cd /opt/hebjijvoormij/app
sudo -u hebjijvoormij python3 -m venv venv
sudo -u hebjijvoormij venv/bin/pip install -r requirements.txt
```

### 3. Database en databasegebruiker aanmaken

```bash
sudo mariadb
```

```sql
CREATE DATABASE gereedschap_leensysteem
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'gereedschap'@'localhost' IDENTIFIED BY 'kies-een-goed-wachtwoord';
GRANT ALL PRIVILEGES ON gereedschap_leensysteem.* TO 'gereedschap'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 4. Configuratie

Maak een omgevingsbestand `/opt/hebjijvoormij/app/.env` (niet in git);
zie `.env.example` voor alle variabelen. Genereer een veilige
`SECRET_KEY` met `openssl rand -hex 32`.

```bash
cat > /opt/hebjijvoormij/app/.env <<'ENV'
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=gereedschap
DB_PASSWORD=kies-een-goed-wachtwoord
DB_NAME=gereedschap_leensysteem
SECRET_KEY=hier-je-gegenereerde-sleutel
ADMIN_NAME=admin
ADMIN_EMAIL=admin@localhost
ADMIN_PASSWORD=kies-eigen-startwachtwoord
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=0
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
SMTP_TLS=1
ENV
```

**Belangrijk bij de beheerder**: `ADMIN_EMAIL` en `ADMIN_PASSWORD` zijn
de startgegevens waarmee de beheerder wordt aangemaakt (het e-mailadres
is de inlognaam). Kies een eigen startwachtwoord (niet de standaard
`beheer123`) — de app maakt de beheerder bij de eerste start aan en
dwingt bij de eerste login tot het kiezen van een nieuw wachtwoord.
Bestaande beheerders worden bij latere starts nooit gewijzigd.

Zet de juiste rechten:

```bash
sudo chown hebjijvoormij:hebjijvoormij /opt/hebjijvoormij/app/.env
sudo chmod 600 /opt/hebjijvoormij/app/.env
```

### 5. Tabellen aanmaken en app testen

De tabellen worden als eenmalige actie aangemaakt met het schema uit de
repo (MariaDB-root werkt op Ubuntu via `sudo`, dus dit hoeft niet via
de app):

```bash
sudo mariadb gereedschap_leensysteem < /opt/hebjijvoormij/app/db/schema.sql
```

Test de app handmatig:

```bash
cd /opt/hebjijvoormij/app
sudo -u hebjijvoormij bash -c 'set -a; source .env; set +a; venv/bin/python app.py'
```

De app is nu bereikbaar op `http://127.0.0.1:5000`. Log in met de
beheerdersgegevens en kies direct een nieuw wachtwoord. Stop daarna met
Ctrl-C en ga verder met de service-installatie.

### 6. Systemd-service (gunicorn)

Maak `/etc/systemd/system/hebjijvoormij.service`:

```ini
[Unit]
Description=hebjijvoormij gereedschap-uitleensysteem
After=network.target mariadb.service
Wants=mariadb.service

[Service]
Type=simple
User=hebjijvoormij
Group=hebjijvoormij
WorkingDirectory=/opt/hebjijvoormij/app
EnvironmentFile=/opt/hebjijvoormij/app/.env
ExecStart=/opt/hebjijvoormij/app/venv/bin/gunicorn --workers 5 --bind 127.0.0.1:5000 app:app
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

De app luistert standaard alleen op `127.0.0.1`. Wil je de app
rechtstreeks op het netwerk bereikbaar maken (zonder nginx), zet dan
`FLASK_HOST=0.0.0.0` in de `.env` en open poort 5000 in de firewall
(bij voorkeur alleen voor vertrouwde netwerken):

```bash
sudo ufw allow from 192.168.1.0/24 to any port 5000 tcp
```

Zet `FLASK_DEBUG` nooit op 1 als de app buiten localhost bereikbaar is.

Activeer en start de service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now hebjijvoormij
sudo systemctl status hebjijvoormij
```

Logbestanden bekijken:

```bash
journalctl -u hebjijvoormij -f
```

### 7. Bereikbaar maken via nginx met HTTPS

Maak de site-configuratie (pas `gereedschap.voorbeeld.nl` aan naar je
eigen domein):

```bash
sudo tee /etc/nginx/sites-available/hebjijvoormij > /dev/null <<'NGINX'
server {
    listen 80;
    server_name gereedschap.voorbeeld.nl;

    # statische bestanden (css, plaatjes) serveert nginx zelf
    location /static/ {
        alias /opt/hebjijvoormij/app/static/;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
NGINX
```

Activeer de site en herlaad nginx:

```bash
sudo ln -s /etc/nginx/sites-available/hebjijvoormij /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Zet de firewall aan (SSH eerst openhouden, anders sluit je jezelf uit):

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

Voeg HTTPS toe met certbot:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d gereedschap.voorbeeld.nl
```

De app is nu bereikbaar via `https://gereedschap.voorbeeld.nl`.

### 8. Updates

```bash
sudo systemctl stop hebjijvoormij
sudo -u hebjijvoormij git -C /opt/hebjijvoormij/app pull
sudo -u hebjijvoormij /opt/hebjijvoormij/app/venv/bin/pip install -r /opt/hebjijvoormij/app/requirements.txt
sudo systemctl start hebjijvoormij
```

Nieuwe kolommen en tabellen voegt de app bij de eerste request na de
update automatisch toe (self-healing migratie).

### 9. Problemen met de beheerder

Wordt de beheerder niet herkend, controleer dan in deze volgorde:

1. **Service herstarten** — systemd leest de `.env` alleen bij het
   starten: `sudo systemctl restart hebjijvoormij`.
2. **Diagnose draaien**:
   ```bash
   cd /opt/hebjijvoormij/app
   sudo -u hebjijvoormij bash -c 'set -a; source .env; set +a; venv/bin/flask --app app ensure-admin'
   ```
3. **Bestaande beheerder wordt niet gewijzigd** — heeft de app ooit
   eerder gedraaid, dan bestaat de beheerder al; een latere wijziging
   van `ADMIN_EMAIL`/`ADMIN_PASSWORD` in de `.env` heeft dan geen
   effect. Zet het wachtwoord opnieuw via de app, of verwijder de
   beheerder en draai `ensure-admin` opnieuw:
   ```sql
   DELETE FROM friends WHERE is_admin = 1;
   ```
4. **Kolommen of tabellen ontbreken** — de app herstelt dit zelf bij
   de eerste request (schema + ontbrekende kolommen); handmatig kan
   ook: `sudo mariadb gereedschap_leensysteem < /opt/hebjijvoormij/app/db/schema.sql`.
5. **Logs bekijken**: `journalctl -u hebjijvoormij -f`.

### 10. Back-up

```bash
sudo mariadb-dump gereedschap_leensysteem | gzip > backup-$(date +%F).sql.gz
sudo tar czf tool-images-$(date +%F).tar.gz /opt/hebjijvoormij/app/static/tool_images
```

Plan dit bv. dagelijks via een cron-job.

## Omgevingsvariabelen

| Variabele | Standaard | Betekenis |
|---|---|---|
| `DB_HOST` | `127.0.0.1` | MariaDB-host |
| `DB_PORT` | `3306` | MariaDB-poort |
| `DB_USER` | `gereedschap` | databasegebruiker van de app |
| `DB_PASSWORD` | `gereedschap` | wachtwoord van de databasegebruiker |
| `DB_NAME` | `gereedschap_leensysteem` | databasenaam |
| `DB_USER_ROOT` | `root` | root-gebruiker voor automatische aanmaak (optioneel) |
| `DB_PASSWORD_ROOT` | – | root-wachtwoord voor automatische aanmaak (optioneel) |
| `SECRET_KEY` | – | ondertekening van sessies (vereist, geheim houden) |
| `ADMIN_NAME` | `admin` | naam van de beheerder bij eerste aanmaak |
| `ADMIN_EMAIL` | `admin@localhost` | e-mailadres (inlognaam) van de beheerder |
| `ADMIN_PASSWORD` | `beheer123` | startwachtwoord van de beheerder |
| `FLASK_HOST` | `127.0.0.1` | luisteradres van de app |
| `FLASK_PORT` | `5000` | luisterpoort van de app |
| `FLASK_DEBUG` | `0` | debug-mode; nooit aanzetten buiten localhost |
| `SMTP_HOST` | – | SMTP-server voor e-mailnotificaties (leeg = geen e-mail) |
| `SMTP_PORT` | `587` | SMTP-poort |
| `SMTP_USER` | – | SMTP-gebruikersnaam |
| `SMTP_PASSWORD` | – | SMTP-wachtwoord |
| `SMTP_FROM` | – | afzender van de e-mails |
| `SMTP_TLS` | `1` | STARTTLS gebruiken |

Zie `.env.example` voor een compleet voorbeeldbestand.

## Gebruik

1. **Eerste keer**: log in als beheerder (`ADMIN_EMAIL` /
   `ADMIN_PASSWORD`) en kies direct een nieuw wachtwoord.
2. **Gebruikers**: nieuwe gebruikers registreren zichzelf via de
   loginpagina; de beheerder keurt ze goed onder **Vrienden**.
3. **Kringen**: maak onder **Kringen** een vriendenkring aan (je wordt
   automatisch kringbeheerder) en voeg je vrienden toe; alleen
   kringgenoten zien elkaars gereedschap en kunnen van elkaar lenen.
4. **Gereedschap**: registreer gereedschap onder **Gereedschap** met
   soort, merk en type; voeg een plaatje toe via upload of URL.
5. **Lenen**: vraag een uitlening aan vanaf de gereedschapskaart of de
   uitleningenpagina (vanaf- en tot-datum verplicht, notitie
   optioneel, combi-gereedschap direct aanvinkbaar). De eigenaar
   keurt goed of wijst af; daarna registreert hij de terugkeer.
6. **Meldingen en berichten**: de bel rechtsboven toont meldingen
   (met e-mail indien SMTP is ingesteld); onder **Berichten** stuur
   je kringgenoten een bericht.
7. **Profiel**: klik rechtsboven op je naam voor je eigen gegevens,
   gereedschap, uitleningen en je datumnotatie.

## Database-schema

Zie `db/schema.sql`. Belangrijk:

- de tabel `loans` heeft een unieke sleutel op `(tool_id, active_flag)`
  via een virtuele kolom, zodat gereedschap nooit tegelijk aan twee
  mensen uitgeleend kan zijn, en bevat de leenperiode
  (`date_from`, `date_until`) en notitie;
- `tool_links` bevat de symmetrische combi-koppelingen;
- `circles` en `circle_members` vormen de vriendenkringen;
- `notifications` en `messages` bevatten de meldingen en berichten;
- `settings` bevat systeeminstellingen (bv. de standaard-datumnotatie);
- de app voert het schema bij de eerste request uit met de gewone
  databasegebruiker en voegt ontbrekende kolommen automatisch toe
  (self-healing migratie).
