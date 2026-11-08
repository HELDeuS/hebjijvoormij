# hebjijvoormij

gereedschap uitleensysteem

## Functies

- **Vrienden** – de beheerder registreert vrienden met naam, e-mail en
  telefoonnummer; elke vriend logt in met een eigen wachtwoord.
- **Gereedschapscatalogus** – registreer gereedschap per eigenaar, met
  omschrijving en categorie. De catalogus is te bekijken als kaarten
  of als sorteerbare lijst (Soort, Categorie, Merk, Eigenaar, Status);
  de voorkeur wordt per gebruiker onthouden. Bij Categorie en Merk
  kun je vrij typen of eerder gebruikte waardes kiezen.
  Gereedschap is achteraf aan te passen of te verwijderen via
  'Aanpassen' en 'Verwijderen' - alleen door de eigenaar of de
  beheerder. Verwijderen is geblokkeerd zolang het gereedschap is
  uitgeleend of aangevraagd.
  Zijn merk en type bekend, dan wordt er automatisch een plaatje
  opgezocht en op de gereedschapskaart getoond. Werkt het automatisch
  zoeken niet, upload dan zelf een foto (jpg, png, webp of gif,
  max. 5 MB).
- **Combi-gereedschap** – koppel bijbehorend gereedschap aan elkaar
  (bv. speciale boren bij een boormachine); op de kaart terug te
  vinden onder "Goed te combineren met". Koppelen kan alleen met
  gereedschap van dezelfde eigenaar, door de eigenaar of de
  beheerder. Bij een leenverzoek
  verschijnt er bovendien een tip en een paneel met combi-suggesties om
  bijbehorend gereedschap direct mee te lenen.
- **Uitleningen met status** – leenverzoeken doorlopen de statuscyclus
  `aangevraagd` → `uitgeleend` → `teruggekeerd` (of `geweigerd`).
- **Overzichten** – openstaande uitleningen en verzoeken, per-vriend statistieken,
  en een persoonlijk transactieoverzicht.

## Technologie

- Python 3.12, Flask
- MySQL / MariaDB (mysql-connector-python, connection pooling)
- Server-side templates (Jinja2) en één CSS-bestand

## Omgevingsvariabelen

| Variabele | Standaard | Betekenis |
|---|---|---|
| `DB_HOST` | `127.0.0.1` | MariaDB-host |
| `DB_PORT` | `3306` | MariaDB-poort |
| `DB_USER` | `gereedschap` | databasegebruiker van de app |
| `DB_PASSWORD` | `gereedschap` | wachtwoord van de databasegebruiker |
| `DB_NAME` | `gereedschap_leensysteem` | databasenaam |
| `SECRET_KEY` | – | ondertekening van sessies (vereist, geheim houden) |
| `ADMIN_NAME` | `admin` | naam van de beheerder bij eerste aanmaak |
| `ADMIN_EMAIL` | `admin@localhost` | e-mailadres (inlognaam) van de beheerder |
| `ADMIN_PASSWORD` | `beheer123` | startwachtwoord van de beheerder |
| `FLASK_HOST` | `127.0.0.1` | luisteradres van de app |
| `FLASK_PORT` | `5000` | luisterpoort van de app |
| `FLASK_DEBUG` | `0` | debug-mode; nooit aanzetten buiten localhost |

Zie `.env.example` voor een compleet voorbeeldbestand.

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
   export FLASK_HOST=127.0.0.1
   export FLASK_PORT=5000
   export FLASK_DEBUG=0
   export ADMIN_NAME=admin
   export ADMIN_EMAIL=admin@localhost
   export ADMIN_PASSWORD=beheer123
   ```

4. **Installeren en starten**:

   ```bash
   pip install -r requirements.txt
   python app.py
   ```

   Werkt je MariaDB-root met wachtwoord-login (bv. lokaal op een
   ontwikkelmachine), dan maakt de app de database en tabellen automatisch
   aan. Gebruikt je root unix-socket-authenticatie (standaard op Ubuntu),
   maak de database en tabellen dan handmatig vooraf:

   ```bash
   sudo mariadb -e "CREATE DATABASE IF NOT EXISTS gereedschap_leensysteem CHARACTER SET utf8mb4"
   sudo mariadb gereedschap_leensysteem < db/schema.sql
   ```

   Daarna start de app op <http://127.0.0.1:5000>.

## Gebruik

1. De app maakt automatisch een **beheerder** aan met vooraf bekende
   inloggegevens: e-mail `admin@localhost`, wachtwoord `beheer123`
   (aanpasbaar via `ADMIN_EMAIL` en `ADMIN_PASSWORD` in de omgeving).
   Bij de eerste login is de beheerder verplicht een nieuw wachtwoord
   te kiezen.
2. De beheerder registreert vrienden onder **Vrienden** met naam,
   e-mailadres en startwachtwoord; elke nieuwe vriend kiest bij de
   eerste login een eigen wachtwoord. Gewone vrienden kunnen zelf geen
   nieuwe vrienden aanmaken.
3. De beheerder kan bestaande accounts aanpassen (naam, e-mail,
   telefoon) en een nieuw startwachtwoord instellen via **Aanpassen**
   in de vriendenlijst - ook het eigen account van de beheerder,
   inclusief het eigen e-mailadres (de inlognaam).
4. Log in met je e-mailadres en wachtwoord; alles wat je doet, gebeurt
   onder je eigen account.
5. Registreer gereedschap onder **Gereedschap** (kies de eigenaar).
6. Onder **Uitleningen** maak je een leenverzoek aan; de eigenaar keurt het
   goed of wijst het af, en het gereedschap wordt teruggegeven via
   "Terugontvangen".
7. Het **Overzicht** toont alle openstaande leningen en statistieken per vriend.

### Inloggen en beveiliging

- Elke vriend logt in met e-mailadres en wachtwoord (e-mailadressen zijn
  uniek); wachtwoorden worden gehasht opgeslagen (werkzeug/scrypt) en
  nooit in platte tekst.
- Alle pagina's zijn alleen bereikbaar na inloggen.
- Zet een sterk `SECRET_KEY`-geheim in de omgevingsvariabelen, want daarmee
  worden de sessies ondertekend.

## Installatie op Ubuntu Server

Deze handleiding gaat uit van Ubuntu Server 22.04 of 24.04 en doorloopt de
stappen in deze volgorde: pakketten → app-code → database → configuratie →
tabellen en test → service → bereikbaarheid.

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

Maak een omgevingsbestand `/opt/hebjijvoormij/app/.env` (niet in git); zie
`.env.example` voor alle variabelen. Genereer een veilige `SECRET_KEY` met
`openssl rand -hex 32`.

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
ENV
```

**Belangrijk bij de beheerder**: `ADMIN_EMAIL` en `ADMIN_PASSWORD` zijn de
startgegevens waarmee de beheerder wordt aangemaakt (het e-mailadres is
de inlognaam). Kies een eigen
startwachtwoord (niet de standaard `beheer123`) — de app maakt de
beheerder bij de eerste start aan met deze gegevens en dwingt bij de
eerste login tot het kiezen van een eigen nieuw wachtwoord. Bestaande
beheerders worden bij latere starts nooit gewijzigd.

Zet de juiste rechten:

```bash
sudo chown hebjijvoormij:hebjijvoormij /opt/hebjijvoormij/app/.env
sudo chmod 600 /opt/hebjijvoormij/app/.env
```

### 5. Tabellen aanmaken en app testen

De tabellen worden als éénmalige actie aangemaakt met het schema uit de repo
(MariaDB-root werkt op Ubuntu via `sudo`, dus dit hoeft niet via de app):

```bash
sudo mariadb gereedschap_leensysteem < /opt/hebjijvoormij/app/db/schema.sql
```

Test de app handmatig:

```bash
cd /opt/hebjijvoormij/app
sudo -u hebjijvoormij bash -c 'set -a; source .env; set +a; venv/bin/python app.py'
```

De app is nu bereikbaar op `http://127.0.0.1:5000`. Log in met de
beheerdersgegevens (standaard `admin@localhost` / `beheer123`,
instelbaar via `ADMIN_EMAIL` en `ADMIN_PASSWORD` in de `.env`) en kies
direct een nieuw wachtwoord. Stop daarna met Ctrl-C en ga verder met de service-installatie.

### 6. Systemd-service

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
ExecStart=/opt/hebjijvoormij/app/venv/bin/python app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

De app luistert standaard alleen op `127.0.0.1`; de systemd-service draait
de app dus uitsluitend lokaal. Wil je de app rechtstreeks op het netwerk
bereikbaar maken (zonder nginx), zet dan in de `.env`:

```
FLASK_HOST=0.0.0.0
FLASK_DEBUG=0
```

en open poort 5000 in de firewall (bij voorkeur alleen voor vertrouwde
netwerken): `sudo ufw allow from 192.168.1.0/24 to any port 5000 tcp`.
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

Maak de site-configuratie `/etc/nginx/sites-available/hebjijvoormij` (pas
`gereedschap.voorbeeld.nl` aan naar je eigen domein):

```bash
sudo tee /etc/nginx/sites-available/hebjijvoormij > /dev/null <<'NGINX'
server {
    listen 80;
    server_name gereedschap.voorbeeld.nl;

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
```

Nieuwe kolommen en tabellen worden door de app bij het opstarten
automatisch toegevoegd aan de database (migraties).

```bash
sudo systemctl start hebjijvoormij
```

### 9. Problemen met de beheerder

Wordt de beheerder niet herkend, controleer dan in deze volgorde:

1. **Service herstarten** — systemd leest de `.env` alleen bij het starten:
   `sudo systemctl restart hebjijvoormij`.
2. **Diagnose draaien**:
   ```bash
   cd /opt/hebjijvoormij/app
   sudo -u hebjijvoormij bash -c 'set -a; source .env; set +a; venv/bin/flask --app app ensure-admin'
   ```
   Het commando meldt of de beheerder bestaat, of het wachtwoord al is
   ingesteld, en wat er mis is met de database.
3. **Bestaande beheerder wordt niet gewijzigd** — heeft de app ooit eerder
   gedraaid, dan bestaat de beheerder al met de toen geldige gegevens;
   een latere wijziging van `ADMIN_EMAIL`/`ADMIN_PASSWORD` in de `.env`
   heeft dan geen effect. Zet het wachtwoord opnieuw via de app, of
   verwijder de beheerder en draai `ensure-admin` opnieuw:
   ```sql
   DELETE FROM friends WHERE is_admin = 1;
   ```
4. **Kolommen of het admin-account ontbreken** — de app herstelt dit
   tegenwoordig zelf: bij elke start (en bij een bezoek aan de
   loginpagina) voert ze het schema uit met de gewone databasegebruiker,
   voegt ze ontbrekende kolommen toe aan bestaande tabellen en zet ze
   het standaard admin-account in de database (`INSERT IGNORE`, dus
   nooit duplicaten). Handmatig kan dit ook:
   ```bash
   sudo mariadb gereedschap_leensysteem < /opt/hebjijvoormij/app/db/schema.sql
   ```
   Het schema bevat het standaard admin-account (`admin@localhost` / `beheer123`,
   met verplichte wachtwoordwijziging bij de eerste login).
5. **Logs bekijken**: `journalctl -u hebjijvoormij -f` — fouten bij het
   aanmaken van de beheerder worden hier gelogd.

### 10. Back-up

```bash
sudo mariadb-dump gereedschap_leensysteem | gzip > backup-$(date +%F).sql.gz
sudo tar czf tool-images-$(date +%F).tar.gz /opt/hebjijvoormij/app/static/tool_images
```

Plan dit bv. dagelijks via een cron-job.

## Database-schema

Zie `db/schema.sql`. Belangrijk:

- de tabel `loans` heeft een unieke sleutel op `(tool_id, active_flag)`
  via een virtuele kolom, zodat gereedschap nooit tegelijk aan twee
  mensen uitgeleerd kan zijn;
- `tool_links` bevat de symmetrische koppelingen tussen gereedschappen
  ("goed te combineren met");
- het schema zet direct het standaard beheerdersaccount neer
  (`admin`, met verplichte wachtwoordwijziging bij de eerste login);
- de app voert het schema bij elke start uit met de gewone
  databasegebruiker en voegt ontbrekende kolommen automatisch toe
  (self-healing migratie).
