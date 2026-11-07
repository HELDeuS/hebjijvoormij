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
  vinden onder "Goed te combineren met". Bij een leenverzoek
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

1. Registreer je vrienden onder **Vrienden** (met wachtwoord van minimaal
   6 tekens). Bestaande vrienden zonder wachtwoord kiezen hun wachtwoord
   bij de eerste keer inloggen.
2. Log in met je naam en wachtwoord; alles wat je doet, gebeurt onder je
   eigen account.
3. Registreer gereedschap onder **Gereedschap** (kies de eigenaar).
4. Onder **Uitleningen** maak je een leenverzoek aan; de eigenaar keurt het
   goed of wijst het af, en het gereedschap wordt teruggegeven via
   "Terugontvangen".
5. Het **Overzicht** toont alle openstaande leningen en statistieken per vriend.

### Inloggen en beveiliging

- Elke vriend logt in met naam en wachtwoord; wachtwoorden worden gehasht
  opgeslagen (werkzeug/scrypt) en nooit in platte tekst.
- Alle pagina's zijn alleen bereikbaar na inloggen.
- Zet een sterk `SECRET_KEY`-geheim in de omgevingsvariabelen, want daarmee
  worden de sessies ondertekend.

## Installatie op Ubuntu Server

Deze handleiding gaat uit van Ubuntu Server 22.04 of 24.04 en installeert de
app als systeemservice onder een eigen gebruiker.

### 1. Systeempakketten

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git mariadb-server
```

Beveilig MariaDB (root-wachtwoord instellen, anonieme gebruikers weg):

```bash
sudo mysql_secure_installation
```

### 2. Databasegebruiker aanmaken

Log in als root en maak de gebruiker en database voor de app:

```bash
sudo mysql
```

```sql
CREATE DATABASE gereedschap_leensysteem
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'gereedschap'@'localhost' IDENTIFIED BY 'kies-een-goed-wachtwoord';
GRANT ALL PRIVILEGES ON gereedschap_leensysteem.* TO 'gereedschap'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 3. App ophalen en Python-omgeving maken

```bash
sudo adduser --system --group --home /opt/hebjijvoormij hebjijvoormij
sudo -u hebjijvoormij git clone https://github.com/HELDeuS/hebjijvoormij.git /opt/hebjijvoormij/app
cd /opt/hebjijvoormij/app
sudo -u hebjijvoormij python3 -m venv venv
sudo -u hebjijvoormij venv/bin/pip install -r requirements.txt
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
ENV
```

Zet de juiste rechten:

```bash
sudo chown hebjijvoormij:hebjijvoormij /opt/hebjijvoormij/app/.env
sudo chmod 600 /opt/hebjijvoormij/app/.env
```

### 5. Database initialiseren en testen

```bash
cd /opt/hebjijvoormij/app
sudo -u hebjijvoormij bash -c 'set -a; source .env; set +a; venv/bin/flask --app app init-db'
sudo -u hebjijvoormij bash -c 'set -a; source .env; set +a; venv/bin/python app.py'
```

De app is nu bereikbaar op `http://127.0.0.1:5000`. Stop met Ctrl-C en ga
verder met de service-installatie.

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

De app luistert standaard alleen op `127.0.0.1`. Maak hem bereikbaar voor
je vrienden via de reverse proxy uit stap 7 (aanrader), zodat poort 5000
intern blijft.

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

### 7. Reverse proxy met HTTPS (aanrader)

Plaats de app achter nginx met HTTPS, bijvoorbeeld
`/etc/nginx/sites-available/hebjijvoormij`:

```nginx
server {
    listen 80;
    server_name gereedschap.voorbeeld.nl;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

```bash
sudo apt install -y nginx
sudo ln -s /etc/nginx/sites-available/hebjijvoormij /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d gereedschap.voorbeeld.nl
```

Open tenslotte poort 80/443 in de firewall:

```bash
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

### 8. Updates

```bash
sudo systemctl stop hebjijvoormij
sudo -u hebjijvoormij git -C /opt/hebjijvoormij/app pull
sudo -u hebjijvoormij /opt/hebjijvoormij/app/venv/bin/pip install -r /opt/hebjijvoormij/app/requirements.txt
sudo systemctl start hebjijvoormij
```

De app voert bij het opstarten automatisch databasemigraties uit, dus
nieuwe kolommen en tabellen worden zonder handmatig werk toegevoegd.

### 9. Back-up

```bash
sudo mariadb-dump gereedschap_leensysteem | gzip > backup-$(date +%F).sql.gz
sudo tar czf tool-images-$(date +%F).tar.gz /opt/hebjijvoormij/app/static/tool_images
```

Plan dit bv. dagelijks via een cron-job.

## Database-schema

Zie `db/schema.sql`. Belangrijk: de tabel `loans` heeft een unieke sleutel op
`(tool_id, active_flag)` via een virtuele kolom, zodat gereedschap nooit
tegelijk aan twee mensen uitgeleerd kan zijn.
