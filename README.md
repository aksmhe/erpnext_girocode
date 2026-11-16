# GiroCode für ERPNext

Druckt einen **GiroCode** (EPC-QR-Code) auf Rechnungen. Der Kunde scannt den Code mit seiner Banking-App, und die **SEPA-Überweisung ist fertig ausgefüllt**: Empfänger, IBAN, BIC, Betrag und Rechnungsnummer als Verwendungszweck.
Das Abtippen der IBAN entfällt, Tippfehler auch, und Zahlungen lassen sich leichter zuordnen.

- Läuft mit **ERPNext / Frappe 15 und 16**
- Der Code entsteht **lokal auf dem eigenen Server**. Es werden **keine Rechnungsdaten** an externe Dienste gesendet, z. B. QR-Generatoren im Internet.
- IBAN, BIC und Firmenname kommen aus ERPNext (**Bankkonto** und **Firma**). Im Code steht nichts fest.
- Keine zusätzlichen Bibliotheken: Die App nutzt `pyqrcode`, das ohnehin mit Frappe installiert ist.

---

## Inhalt

1. [Was die App macht](#1-was-die-app-macht)
2. [Installation](#2-installation)
3. [Einrichtung in ERPNext](#3-einrichtung-in-erpnext)
4. [Ausprobieren](#4-ausprobieren)
5. [Für Fortgeschrittene](#5-für-fortgeschrittene)
6. [Grenzen](#6-grenzen)
7. [Fehlerbehebung](#7-fehlerbehebung)
8. [Datenschutz und Sicherheit](#8-datenschutz-und-sicherheit)

---

## 1. Was die App macht

Die App stellt im Druckformat zwei Funktionen bereit:

| Funktion | Ergebnis |
|---|---|
| `get_girocode_data(doc)` | QR-Code als Bild **und** die Zahlungsangaben (IBAN, BIC, Betrag, Verwendungszweck) zum Ausdrucken als Text |
| `get_girocode(doc)` | nur das QR-Code-Bild |

Damit der Code auf der Rechnung erscheint, fügt man einen kleinen **Baustein** in das Druckformat ein, siehe [Einrichtung](#3-einrichtung-in-erpnext).

**Was im Code steht:**

| Angabe | Woher sie kommt |
|---|---|
| Empfänger | Firmenname (*Company Name*) der Firma auf der Rechnung, höchstens 70 Zeichen |
| IBAN | **Bankkonto** (*Bank Account*) der Firma: das Standardkonto (*Is Default*) mit IBAN, sonst das erste aktive Firmenkonto mit IBAN |
| BIC | **SWIFT-Nummer** der **Bank** (*Bank*), sonst das Feld **Filialcode** (*Branch Code*) im Bankkonto, wenn dort eine BIC steht |
| Betrag | **offener Betrag** (*Outstanding Amount*); bei Entwürfen der Rechnungsbetrag |
| Verwendungszweck | Rechnungsnummer, z. B. `ACC-SINV-2026-00001` |

**Wann kein Code gedruckt wird:**

- Die Rechnung ist **nicht in Euro**. GiroCodes gibt es nur für Euro.
- Es ist eine **Gutschrift** (*Is Return*) oder die Rechnung ist **storniert**.
- Die gebuchte Rechnung ist **schon bezahlt** (offener Betrag 0).
- Für die Firma gibt es **kein Bankkonto mit gültiger IBAN**.

Ein fehlender Code verhindert nie den Druck. Die Rechnung wird dann einfach ohne Code gedruckt.

**Technik:** Der Code folgt der Richtlinie **EPC069-12** des European Payments Council: Version `002`, Zeichensatz UTF-8, Fehlerkorrektur M, Betrag im Format `EUR160.00`, Verwendungszweck höchstens 140 Zeichen, gesamt höchstens 331 Byte.

---

## 2. Installation

### Mit frappe_docker (eigenes Image)

#### Vorher: Platzhalter ermitteln

In den Befehlen unten stehen Platzhalter in spitzen Klammern, z. B. `<site>`. Diese ersetzt man durch die **eigenen** Werte, **ohne** die spitzen Klammern.
Alle Befehle in dieser Tabelle **zeigen nur etwas an und ändern nichts**. Man führt sie auf dem Server als der Benutzer aus, der Docker bedienen darf.

| Platzhalter | Bedeutung | So findet man ihn heraus | Beispiel |
|---|---|---|---|
| `<backend-container>` | Name des Containers, in dem ERPNext läuft | `docker ps --format '{{.Names}}' \| grep backend` | `erpnext-backend-1` |
| `<site>` | Name der ERPNext-Site, meist die Internetadresse ohne `https://` | `docker exec <backend-container> ls sites`: Gemeint ist der Ordnername, der wie eine Adresse aussieht. `apps.json`, `apps.txt`, `assets` und `common_site_config.json` gehören **nicht** dazu. | `erp.example.com` |
| `<image>` und alter Tag | Image, mit dem ERPNext gerade läuft | `docker ps --format '{{.Names}}  {{.Image}}' \| grep backend`: Was **vor** dem Doppelpunkt steht, ist `<image>`, dahinter steht der **alte Tag**. | `erpnext-custom:16-plz` → `<image>` = `erpnext-custom`, alter Tag = `16-plz` |
| `<neuer-tag>` | frei wählbarer Name für das neue Image. Er sollte sich vom alten unterscheiden, damit der Rückweg offen bleibt. | selbst festlegen | `16-girocode` |
| `<projekt>` | Name des Docker-Compose-Projekts | `docker inspect <backend-container> --format '{{ index .Config.Labels "com.docker.compose.project" }}'` | `erpnext` |
| `<compose-datei>` | Datei, in der steht, welches Image die Container nutzen | `docker inspect <backend-container> --format '{{ index .Config.Labels "com.docker.compose.project.config_files" }}'` | `/home/benutzer/erpnext.yaml` |
| `<frappe_docker-ordner>` | Ordner mit `apps.json` und dem Unterordner `images` | `find ~ -maxdepth 3 -name apps.json -path '*frappe_docker*'`: Gemeint ist der Ordner, in dem die gefundene Datei liegt. | `/home/benutzer/frappe_docker` |

> 💡 **Tipp:** Am besten alle Werte einmal ermitteln und in eine Notiz schreiben. Danach setzt man die Befehle unten fertig zusammen und fügt sie Schritt für Schritt ein.

#### Installation Schritt für Schritt

1. Eine **Sicherung** erstellen. Am Ende erscheint eine „Backup Summary“:
   ```bash
   docker exec <backend-container> bench --site <site> backup --with-files
   ```
2. Eine **Kopie der `apps.json`** anlegen und die Datei danach ansehen:
   ```bash
   cd <frappe_docker-ordner>
   cp apps.json apps.json.vor-girocode
   cat apps.json
   ```
   Dann diese Zeile als **letzten Eintrag** ergänzen, z. B. mit `nano apps.json`. Die vorhandenen Einträge bleiben stehen. Achtung: Zwischen den Einträgen steht ein Komma, nach dem letzten keins.
   ```json
   {"url": "https://github.com/aksmhe/erpnext_girocode", "branch": "main"}
   ```
3. Das Image **neu bauen**, im `<frappe_docker-ordner>`. Das dauert etwa 15–30 Minuten. Für ERPNext 16 muss `FRAPPE_BRANCH` auf `version-16` stehen, für ERPNext 15 auf `version-15`.
   **`--no-cache`** ist wichtig: Ohne diese Angabe erkennt Docker die geänderte `apps.json` nicht und baut das alte Image ohne die neue App.
   ```bash
   docker build --no-cache \
     --build-arg=FRAPPE_PATH=https://github.com/frappe/frappe \
     --build-arg=FRAPPE_BRANCH=version-16 \
     --secret=id=apps_json,src=apps.json \
     --tag=<image>:<neuer-tag> \
     --file=images/layered/Containerfile .
   ```
4. Das neue Image **prüfen**. Alle bisherigen Apps **und** `erpnext_girocode` müssen in der Liste stehen:
   ```bash
   docker run --rm <image>:<neuer-tag> ls apps
   ```
5. Eine **Kopie der Compose-Datei** anlegen und nachsehen, ob der alte Tag darin steht:
   ```bash
   cp <compose-datei> <compose-datei>.vor-girocode
   grep -n "<image>:<alter-tag>" <compose-datei>
   ```
   Dann auf den neuen Tag umstellen und neu starten. ERPNext ist dabei 1–2 Minuten nicht erreichbar:
   ```bash
   sed -i 's/<image>:<alter-tag>/<image>:<neuer-tag>/g' <compose-datei>
   docker compose -p <projekt> -f <compose-datei> up -d
   ```
6. Die App in die Site **installieren** und prüfen:
   ```bash
   docker exec <backend-container> bench --site <site> install-app erpnext_girocode
   docker exec <backend-container> bench --site <site> migrate
   docker exec <backend-container> bench --site <site> list-apps
   ```
   In der Liste muss jetzt `erpnext_girocode` stehen. Nach dem Neustart muss man sich im Browser neu bei ERPNext anmelden.

#### Rückweg, falls etwas nicht klappt

- **Vor Schritt 6:** einfach wieder auf das alte Image umstellen:
  ```bash
  sed -i 's/<image>:<neuer-tag>/<image>:<alter-tag>/g' <compose-datei>
  docker compose -p <projekt> -f <compose-datei> up -d
  ```
- **Nach Schritt 6:** zuerst den Baustein aus dem Druckformat entfernen (oder so lassen, er wird ohne App übersprungen), dann die App entfernen und wie oben zurückstellen:
  ```bash
  docker exec <backend-container> bench --site <site> uninstall-app erpnext_girocode --yes
  ```

#### Auf eine neue Version aktualisieren

Ist `erpnext_girocode` schon installiert, baut man das Image wie in Schritt 3 neu, mit **`--no-cache`** und einem **neuen Tag**.
Danach geht es weiter mit Schritt 4 und 5. Statt `install-app` reicht in Schritt 6 dann:
```bash
docker exec <backend-container> bench --site <site> migrate
```

### Mit bench (klassische Installation)

```bash
bench get-app https://github.com/aksmhe/erpnext_girocode --branch main
bench --site <site> install-app erpnext_girocode
bench --site <site> migrate
```

---

## 3. Einrichtung in ERPNext

### 3.1 Bankkonto prüfen

1. Suchleiste → **Bankkonto** (*Bank Account*) öffnen.
2. Das Konto der Firma öffnen. Dort müssen stehen:
   - Haken **Firmenkonto** (*Is Company Account*) und die richtige **Firma**
   - **IBAN**
   - Haken **Standard** (*Is Default*), wenn die Firma mehrere Konten hat
3. Die **BIC** steht in der verknüpften **Bank** im Feld **SWIFT-Nummer**. Alternativ trägt man sie im Bankkonto bei **Filialcode** (*Branch Code*) ein.
   Die BIC ist für Überweisungen innerhalb des SEPA-Raums freiwillig.

### 3.2 Baustein ins Druckformat einfügen

Das geht nur bei Druckformaten vom Typ **Jinja** (eigenes HTML), nicht im Drag-and-Drop-Editor.

1. Suchleiste → **Druckformat** (*Print Format*) → das Rechnungs-Druckformat öffnen, z. B. „Ausgangsrechnung“.
2. Vorher eine Sicherung machen: den Inhalt des Feldes **HTML** komplett kopieren und in einer Textdatei speichern.
3. Den Baustein aus [`examples/druckformat_baustein.html`](examples/druckformat_baustein.html) an die gewünschte Stelle kopieren, z. B. direkt **nach der Tabelle mit der Gesamtsumme**.
4. **Speichern** und eine Rechnung in der Druckvorschau öffnen.

Der Baustein sieht so aus (gekürzt):

```jinja
{% set gc = get_girocode_data(doc) if get_girocode_data is defined else None %}
{% if gc %}
    <img src="{{ gc.qr }}" style="width: 30mm; height: 30mm;">
    IBAN: {{ gc.iban_formatted }} · BIC: {{ gc.bic }}
    Verwendungszweck: {{ gc.reference }}
{% endif %}
```

> Der Code sollte gedruckt **mindestens 2 cm × 2 cm** groß sein. 3 cm lassen sich mit allen Banking-Apps gut scannen.

---

## 4. Ausprobieren

1. Eine **Ausgangsrechnung** (*Sales Invoice*) in Euro öffnen, ein Entwurf genügt.
2. Oben auf **Drucken** (Drucker-Symbol) klicken und das Druckformat wählen.
3. Unter der Summe erscheint der GiroCode mit den Zahlungsangaben.
4. Den Code am Bildschirm oder im PDF mit der **Banking-App** scannen (Funktion „Foto-Überweisung“, „QR-Code scannen“ oder „GiroCode“).
5. Prüfen: Empfänger, IBAN, Betrag und Verwendungszweck müssen stimmen. Die Überweisung **nicht ausführen**, sondern abbrechen.

---

## 5. Für Fortgeschrittene

`get_girocode_data(doc, ...)` kennt diese Angaben:

| Angabe | Standard | Bedeutung |
|---|---|---|
| `bank_account` | Standardkonto der Firma | Name eines bestimmten Bankkontos, z. B. `"Geschäftskonto - Meine Bank"` |
| `text` | Dokumentname | eigener Verwendungszweck |
| `name` | Firmenname | eigener Empfängername |
| `with_amount` | `True` | `False` = Code ohne Betrag |
| `hide_when_paid` | `True` | `False` = Code auch bei bezahlten Rechnungen |
| `scale` | `4` | Auflösung des Bildes; die Druckgröße stellt man im `style` ein |

Beispiel: `get_girocode_data(doc, bank_account="Geschäftskonto - Meine Bank", text="Rechnung " ~ doc.name)`

Das Ergebnis enthält: `qr` (Bild als `data:`-Adresse), `payload` (Inhalt des Codes), `name`, `iban`, `iban_formatted`, `bic`, `bank`, `bank_account`, `amount`, `reference`.

Die Funktionen funktionieren in jedem Druckformat, z. B. auch für Mahnungen (*Dunning*) oder Aufträge (*Sales Order*), sofern das Dokument die Felder `company`, `currency` und einen Betrag hat.

Tests ohne Frappe-Site:

```bash
python -m unittest erpnext_girocode.tests.test_epc
```

---

## 6. Grenzen

- **Nur Euro** und nur SEPA-Überweisungen. Andere Währungen und Instant Payments sind nicht vorgesehen.
- **Nur Jinja-Druckformate.** Im Drag-and-Drop-Editor kann man den Baustein nicht einfügen.
- Nicht jede Banking-App liest GiroCodes. Fast alle deutschen und österreichischen Banken tun es.
- Der Verwendungszweck wird **unstrukturiert** übertragen (Rechnungsnummer als Text). Eine strukturierte RF-Referenz wird nicht automatisch erzeugt.

---

## 7. Fehlerbehebung

| Was passiert | Ursache | Lösung |
|---|---|---|
| Kein Code auf der Rechnung | App nicht in der Site installiert | `docker exec <backend-container> bench --site <site> list-apps`: `erpnext_girocode` muss dabei sein |
| Kein Code auf der Rechnung | Rechnung nicht in Euro, Gutschrift, storniert oder bezahlt | so gewollt, siehe [Abschnitt 1](#1-was-die-app-macht) |
| Kein Code auf der Rechnung | kein Firmen-Bankkonto mit gültiger IBAN | Bankkonto prüfen, siehe [3.1](#31-bankkonto-prüfen) |
| Kein Code, aber alles scheint richtig | anderer Fehler | Suchleiste → **Fehlerprotokoll** (*Error Log*), Einträge mit dem Titel „GiroCode“ ansehen |
| BIC fehlt im Code | Weder SWIFT-Nummer in der Bank noch BIC im Filialcode | BIC eintragen; für SEPA ist sie aber freiwillig |
| Banking-App erkennt den Code nicht | Code zu klein gedruckt oder App kann keinen GiroCode | Größe auf mindestens 3 cm stellen, andere App probieren |
| Druckformat zeigt einen Fehler | Baustein unvollständig kopiert | Baustein erneut vollständig aus `examples/druckformat_baustein.html` kopieren |

---

## 8. Datenschutz und Sicherheit

- Der QR-Code wird **auf dem eigenen Server** erzeugt und direkt als Bild in die Rechnung eingebettet. **Keine** Rechnungsdaten gehen an Dienste im Internet. Damit eignet sich die App auch für DSGVO-sensible Umgebungen.
- Die App speichert **nichts** und legt keine Tabellen an. Sie liest nur Bankkonto, Bank und Firma.
- Die App hat **keine** eigene Web-Schnittstelle (API). Sie läuft nur beim Drucken.
- Im Code stehen **keine Zugangsdaten**, keine IBAN und keine Firmendaten.

---

## Lizenz

MIT, siehe [license.txt](license.txt). Das englische Original ist rechtlich verbindlich.
Die deutsche Übersetzung zum besseren Verständnis steht in [license_de.txt](license_de.txt).
