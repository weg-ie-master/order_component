"""
Ruft das Datenprodukt order_component über die Dremio CLOUD REST API (v0) ab
und schreibt das Ergebnis als CSV nach output/order_component.csv.

Hinweis: Dremio Cloud (app.dremio.cloud) hat eine andere API-Struktur als
selbst-gehostetes Dremio Software. Die API läuft über eine eigene Domain
(api.dremio.cloud) und jede Anfrage braucht die Project ID im Pfad.

Benötigte Umgebungsvariablen (siehe GitHub Secrets/Variables):
- DREMIO_BASE_URL     API-Control-Plane-URL, NICHT die Web-UI-URL.
                      US: https://api.dremio.cloud
                      EU: https://api.eu.dremio.cloud
- DREMIO_PAT          Personal Access Token (Dremio Cloud -> User Settings -> Personal Access Tokens)
- DREMIO_PROJECT_ID   Project ID aus Dremio Cloud -> Project Settings -> General
- DREMIO_SQL_PATH     voll qualifizierter Pfad zur Tabelle, z.B. "Athena"."pp_dev"."pp"."order_component"
                      (jede Ebene einzeln in doppelten Anführungszeichen)
- DREMIO_SQL_WHERE    optional, WHERE-Bedingung ohne das Wort "WHERE",
                      z.B. plant = '4103'  (Anführungszeichen nur, falls Spalte Text ist)
- DREMIO_SQL_LIMIT    optional, z.B. "100" - für Testläufe, um Engine-Start
                      von echtem Datenvolumen als Ursache für lange Laufzeit zu trennen
- DREMIO_POLL_TIMEOUT_SEC  optional, Default 900 (15 Min)
"""

import os
import sys
import time
import csv
import requests

BASE_URL = os.environ["DREMIO_BASE_URL"].rstrip("/")
PAT = os.environ["DREMIO_PAT"]
PROJECT_ID = os.environ["DREMIO_PROJECT_ID"]
SQL_PATH = os.environ.get("DREMIO_SQL_PATH", '"order_component"')
SQL_WHERE = os.environ.get("DREMIO_SQL_WHERE", "").strip()
SQL_LIMIT = os.environ.get("DREMIO_SQL_LIMIT", "").strip()

API_ROOT = f"{BASE_URL}/v0/projects/{PROJECT_ID}"

HEADERS = {
    "Authorization": f"Bearer {PAT}",
    "Content-Type": "application/json",
}

POLL_INTERVAL_SEC = 5
POLL_TIMEOUT_SEC = int(os.environ.get("DREMIO_POLL_TIMEOUT_SEC", "900"))
PAGE_SIZE = 500


def _parse_json(resp: requests.Response):
    """Gibt eine klare Fehlermeldung aus, falls die Antwort kein JSON ist
    (z.B. HTML-Loginseite bei falscher URL/Project ID)."""
    try:
        return resp.json()
    except ValueError:
        preview = resp.text[:200].replace("\n", " ")
        raise RuntimeError(
            f"Keine JSON-Antwort von {resp.url} (Status {resp.status_code}). "
            f"Prüfe DREMIO_BASE_URL und DREMIO_PROJECT_ID. Antwort-Vorschau: {preview}"
        )


def submit_query(sql: str) -> str:
    resp = requests.post(f"{API_ROOT}/sql", headers=HEADERS, json={"sql": sql})
    resp.raise_for_status()
    return _parse_json(resp)["id"]


def wait_for_job(job_id: str) -> dict:
    elapsed = 0
    last_state = None
    while elapsed < POLL_TIMEOUT_SEC:
        resp = requests.get(f"{API_ROOT}/job/{job_id}", headers=HEADERS)
        resp.raise_for_status()
        job = _parse_json(resp)
        state = job["jobState"]
        if state != last_state:
            print(f"  Status nach {elapsed}s: {state}")
            last_state = state
        if state == "COMPLETED":
            return job
        if state in ("FAILED", "CANCELED"):
            raise RuntimeError(f"Dremio Job {job_id} beendet mit Status {state}: {job.get('errorMessage')}")
        time.sleep(POLL_INTERVAL_SEC)
        elapsed += POLL_INTERVAL_SEC
    raise TimeoutError(
        f"Dremio Job {job_id} hat das Timeout von {POLL_TIMEOUT_SEC}s überschritten "
        f"(letzter bekannter Status: {last_state}). Falls der Status lange bei STARTING/"
        f"ENQUEUED hing, ist das ein Engine-Cold-Start-Problem, keine Query-Ursache."
    )


def fetch_all_rows(job_id: str) -> tuple[list[str], list[list]]:
    columns: list[str] = []
    rows: list[list] = []
    offset = 0
    while True:
        resp = requests.get(
            f"{API_ROOT}/job/{job_id}/results",
            headers=HEADERS,
            params={"offset": offset, "limit": PAGE_SIZE},
        )
        resp.raise_for_status()
        data = _parse_json(resp)
        if not columns:
            columns = [c["name"] for c in data.get("schema", [])]
        batch = data.get("rows", [])
        if not batch:
            break
        rows.extend(batch)
        offset += len(batch)
        if len(batch) < PAGE_SIZE:
            break
    return columns, rows


def write_csv(columns: list[str], rows: list[list], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([row.get(col) for col in columns])


def main() -> None:
    sql = f"SELECT * FROM {SQL_PATH}"
    if SQL_WHERE:
        sql += f" WHERE {SQL_WHERE}"
    if SQL_LIMIT:
        sql += f" LIMIT {SQL_LIMIT}"
    print(f"Starte Dremio Query: {sql}")

    job_id = submit_query(sql)
    print(f"Job gestartet: {job_id}")

    job = wait_for_job(job_id)
    print(f"Job abgeschlossen, {job.get('rowCount', '?')} Zeilen")

    columns, rows = fetch_all_rows(job_id)
    write_csv(columns, rows, "output/order_component.csv")
    print(f"Export geschrieben: output/order_component.csv ({len(rows)} Zeilen, {len(columns)} Spalten)")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Fehler beim Abruf: {exc}", file=sys.stderr)
        sys.exit(1)
