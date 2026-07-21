"""
Ruft das Datenprodukt order_component über Dremio Cloud ARROW FLIGHT SQL ab
und schreibt das Ergebnis als Parquet nach output/order_component.parquet.

Warum Arrow Flight statt REST-API:
Die REST Job-Results-API (/v0/projects/{id}/job/{id}/results) ist für
UI-Paging gedacht und stößt bei großen Ergebnismengen an einen internen
Puffer (bei order_component + plant=4103 mit 6+ Mio. Zeilen z.B. bei
Offset ~842.000 mit "400 Bad Request"). Arrow Flight SQL ist der von
Dremio vorgesehene Mechanismus für Bulk-Exporte und streamt die Daten,
statt sie über Hunderte Einzel-Requests zu paginieren.

Benötigte Umgebungsvariablen:
- DREMIO_FLIGHT_ENDPOINT  optional, Default: grpc+tls://data.dremio.cloud:443
                          EU-Region: grpc+tls://data.eu.dremio.cloud:443
- DREMIO_PAT              Personal Access Token (gleicher wie bisher)
- DREMIO_PROJECT_ID       Project ID (gleicher wie bisher)
- DREMIO_SQL_PATH         voll qualifizierter Tabellenpfad,
                          z.B. "Athena"."pp_dev"."pp"."order_component"
- DREMIO_SQL_WHERE        optional, WHERE-Bedingung ohne das Wort "WHERE",
                          z.B. plant = '4103'
- DREMIO_SQL_LIMIT        optional, für Testläufe, z.B. "100"
"""

import os
import sys

from dremio_simple_query.connectv2 import DremioConnection

ENDPOINT = os.environ.get("DREMIO_FLIGHT_ENDPOINT", "grpc+tls://data.dremio.cloud:443")
PAT = os.environ["DREMIO_PAT"]
PROJECT_ID = os.environ["DREMIO_PROJECT_ID"]
SQL_PATH = os.environ.get("DREMIO_SQL_PATH", '"order_component"')
SQL_WHERE = os.environ.get("DREMIO_SQL_WHERE", "").strip()
SQL_LIMIT = os.environ.get("DREMIO_SQL_LIMIT", "").strip()


def build_sql() -> str:
    sql = f"SELECT * FROM {SQL_PATH}"
    if SQL_WHERE:
        sql += f" WHERE {SQL_WHERE}"
    if SQL_LIMIT:
        sql += f" LIMIT {SQL_LIMIT}"
    return sql


def main() -> None:
    sql = build_sql()
    print(f"Starte Dremio Flight Query: {sql}")
    print(f"Endpoint: {ENDPOINT}")

    dremio = DremioConnection(location=ENDPOINT, token=PAT, project_id=PROJECT_ID)
    df = dremio.toPandas(sql)

    os.makedirs("output", exist_ok=True)
    out_path = "output/order_component.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Export geschrieben: {out_path} ({len(df)} Zeilen, {len(df.columns)} Spalten)")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Fehler beim Abruf: {exc}", file=sys.stderr)
        sys.exit(1)
