# order_component Dremio Sync

Automatisierter täglicher Export des Datenprodukts `order_component` (Domäne PP, Owner alexw@weg.net) aus Dremio via GitHub Actions.

## Setup (einmalig)

1. **Personal Access Token in Dremio erstellen**
   Dremio UI → Account Settings → Personal Access Tokens → neuen Token erstellen.
   Der zugehörige User muss Mitglied der read group von `order_component` sein.

2. **GitHub Secrets anlegen** (Repo → Settings → Secrets and variables → Actions → Secrets)
   - `DREMIO_BASE_URL` — z.B. `https://dremio.weg.net`
   - `DREMIO_PAT` — der PAT aus Schritt 1

3. **GitHub Variable anlegen** (gleicher Ort, Tab "Variables")
   - `DREMIO_SQL_PATH` — voll qualifizierter Pfad zur Tabelle in Dremio,
     z.B. `"PP"."order_component"` (Space/Folder-Struktur wie im Dremio-Katalog sichtbar).
     Ohne diese Variable wird `"order_component"` als Default verwendet — das
     funktioniert nur, wenn kein eindeutiger Pfad nötig ist.

4. **Dateien committen**
   - `.github/workflows/order_component_sync.yml`
   - `scripts/fetch_order_component.py`
   - `scripts/requirements.txt`

## Testen

Repo → Actions → "order_component Dremio Sync" → "Run workflow" (manueller Trigger).
Ergebnis liegt danach als Artefakt `order_component-<run_id>` mit der Datei
`order_component.csv` am Workflow-Run.

## Zeitplan

Läuft täglich um 06:30 UTC (08:30 CEST), also nach der Datenaktualisierung
um 06:00 laut Datenkatalog. Bei Bedarf in `order_component_sync.yml` unter
`on.schedule.cron` anpassen.

## Nächste Ausbaustufe (optional)

Aktuell landet der Export nur als GitHub Actions Artefakt (14 Tage
Aufbewahrung). Für einen dauerhaften Ablagepunkt zusätzlich einen Upload-Schritt
ergänzen, z.B.:
- Azure Blob Storage (`azure/CLI@v2` + `az storage blob upload`)
- SharePoint/OneDrive via Microsoft Graph API
- Commit der CSV zurück ins Repo (`git add && git commit && git push`)

Sag Bescheid, welches Ziel du willst, dann bau ich den Schritt dazu.

## Wartung

- Ampelfarbe von `order_component` im Datenkatalog im Blick behalten (aktuell Grün).
- PAT läuft je nach Dremio-Konfiguration ab — rechtzeitig erneuern.
- Bei Schemaänderungen an `order_component` ggf. SQL-Statement in
  `fetch_order_component.py` anpassen (z.B. Spaltenauswahl statt `SELECT *`).
