"""
Ruft das Datenprodukt order_component über die Dremio REST API v3 ab
und schreibt das Ergebnis als CSV nach output/order_component.csv.

Benötigte Umgebungsvariablen (siehe GitHub Secrets/Variables):
- DREMIO_BASE_URL   z.B. https://dremio.weg.net  (ohne trailing slash)
- DREMIO_PAT        Personal Access Token (Dremio -> Account Settings -> Personal Access Tokens)
- DREMIO_SQL_PATH   voll qualifizierter Pfad zur Tabelle, z.B. "PP"."order_component"
"""

import os
import sys
import time
import csv
import requests

BASE_URL = os.environ["DREMIO_BASE_URL"].rstrip("/")
PAT = os.environ["DREMIO_PAT"]
SQL_PATH = os.environ.get("DREMIO_SQL_PATH", '"order_component"')

HEADERS = {
    "Authorization": f"Bearer {PAT}",
    "Content-Type": "application/json",
}

POLL_INTERVAL_SEC = 3
POLL_TIMEOUT_SEC = 600
PAGE_SIZE = 500


def submit_query(sql: str) -> str:
    resp = requests.post(f"{BASE_URL}/api/v3/sql", headers=HEADERS, json={"sql": sql})
    resp.raise_for_status()
    return resp.json()["id"]


def wait_for_job(job_id: str) -> dict:
    elapsed = 0
    while elapsed < POLL_TIMEOUT_SEC:
        resp = requests.get(f"{BASE_URL}/api/v3/job/{job_id}", headers=HEADERS)
        resp.raise_for_status()
        job = resp.json()
        state = job["jobState"]
        if state == "COMPLETED":
            return job
        if state in ("FAILED", "CANCELED"):
            raise RuntimeError(f"Dremio Job {job_id} beendet mit Status {state}: {job.get('errorMessage')}")
        time.sleep(POLL_INTERVAL_SEC)
        elapsed += POLL_INTERVAL_SEC
    raise TimeoutError(f"Dremio Job {job_id} hat das Timeout von {POLL_TIMEOUT_SEC}s überschritten")


def fetch_all_rows(job_id: str) -> tuple[list[str], list[list]]:
    columns: list[str] = []
    rows: list[list] = []
    offset = 0
    while True:
        resp = requests.get(
            f"{BASE_URL}/api/v3/job/{job_id}/results",
            headers=HEADERS,
            params={"offset": offset, "limit": PAGE_SIZE},
        )
        resp.raise_for_status()
        data = resp.json()
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
