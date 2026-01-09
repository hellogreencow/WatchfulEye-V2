"""WS0.4: Seed minimal Entities/Identifiers into Postgres.

Goal: make `/api/v3/entities/resolve` useful in staging without external network calls.
This module is intentionally simple and deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Optional

import psycopg
import requests
from psycopg.types.json import Jsonb

from watchfuleye.storage.postgres_schema import ensure_postgres_schema


SEED_SOURCE_SYSTEMS_ALLOW_UPDATE = {"seed_minimal", "seed_ws0"}


def _upsert_entity(
    cur: psycopg.Cursor,
    *,
    entity_id: str,
    entity_type: str,
    label: str,
) -> None:
    cur.execute(
        """
        INSERT INTO entities (id, entity_type, label)
        VALUES (%s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
          entity_type = EXCLUDED.entity_type,
          label = EXCLUDED.label,
          updated_at = now()
        """,
        (entity_id, entity_type, label),
    )


def _upsert_identifier(
    cur: psycopg.Cursor,
    *,
    entity_id: str,
    identifier_type: str,
    identifier_value: str,
    confidence: float,
    provenance: dict[str, Any],
) -> None:
    cur.execute(
        """
        INSERT INTO entity_identifiers (entity_id, identifier_type, identifier_value, confidence, provenance)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (identifier_type, identifier_value) DO UPDATE SET
          entity_id = EXCLUDED.entity_id,
          confidence = EXCLUDED.confidence,
          provenance = EXCLUDED.provenance
        WHERE
          entity_identifiers.entity_id = EXCLUDED.entity_id
          OR (entity_identifiers.provenance->>'source_system') = ANY(%s)
        """,
        (entity_id, identifier_type, identifier_value, confidence, Jsonb(provenance), list(SEED_SOURCE_SYSTEMS_ALLOW_UPDATE)),
    )


def seed_minimal_countries(pg_dsn: str) -> int:
    """Seed a minimal set of countries.

    Returns: number of country entities processed (not DB rows).
    """
    ensure_postgres_schema(pg_dsn)
    rows: list[tuple[str, str, str]] = [
        ("USA", "United States", "US"),
        ("GBR", "United Kingdom", "GB"),
        ("IRN", "Iran", "IR"),
        ("RUS", "Russia", "RU"),
        ("CHN", "China", "CN"),
    ]
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            for (iso3, name, iso2) in rows:
                entity_id = f"country_{iso3}"
                _upsert_entity(cur, entity_id=entity_id, entity_type="country", label=name)
                _upsert_identifier(
                    cur,
                    entity_id=entity_id,
                    identifier_type="iso3166",
                    identifier_value=iso2,
                    confidence=1.0,
                    provenance={"source_system": "seed_minimal", "kind": "iso3166"},
                )
                _upsert_identifier(
                    cur,
                    entity_id=entity_id,
                    identifier_type="iso3166",
                    identifier_value=iso3,
                    confidence=1.0,
                    provenance={"source_system": "seed_minimal", "kind": "iso3166"},
                )
                _upsert_identifier(
                    cur,
                    entity_id=entity_id,
                    identifier_type="name",
                    identifier_value=name,
                    confidence=0.9,
                    provenance={"source_system": "seed_minimal", "kind": "name"},
                )
    return len(rows)


def seed_minimal_sanctions_targets(pg_dsn: str) -> int:
    """Seed a minimal set of sanctions targets.

    Returns: number of sanctions_target entities processed (not DB rows).
    """
    ensure_postgres_schema(pg_dsn)
    targets: list[tuple[str, str]] = [
        ("OFAC_TEST_0001", "Example Sanctions Target"),
    ]
    processed = 0
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            for (ofac_id, label) in targets:
                entity_id = f"sanctions_{ofac_id}"
                _upsert_entity(cur, entity_id=entity_id, entity_type="sanctions_target", label=label)
                _upsert_identifier(
                    cur,
                    entity_id=entity_id,
                    identifier_type="ofac_id",
                    identifier_value=ofac_id,
                    confidence=1.0,
                    provenance={"source_system": "seed_minimal", "kind": "ofac_id"},
                )
                _upsert_identifier(
                    cur,
                    entity_id=entity_id,
                    identifier_type="name",
                    identifier_value=label,
                    confidence=0.8,
                    provenance={"source_system": "seed_minimal", "kind": "name"},
                )
                processed += 1
    return processed


def seed_iso3166_all_from_json(pg_dsn: str, *, json_path: Path) -> int:
    """Seed ISO-3166 countries from a local JSON file (deterministic; no runtime network).

    Returns: number of country entities processed (not DB rows).
    """
    import json

    ensure_postgres_schema(pg_dsn)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("ISO dataset JSON must be a list")

    processed = 0
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            for row in payload:
                if not isinstance(row, dict):
                    continue
                iso2 = (row.get("alpha-2") or "").strip().upper()
                iso3 = (row.get("alpha-3") or "").strip().upper()
                name = (row.get("name") or "").strip()
                if not iso2 or not iso3 or not name:
                    continue
                entity_id = f"country_{iso3}"
                _upsert_entity(cur, entity_id=entity_id, entity_type="country", label=name)
                prov_base = {
                    "source_system": "seed_ws0",
                    "dataset": "iso3166",
                    "dataset_path": str(json_path),
                }
                _upsert_identifier(
                    cur,
                    entity_id=entity_id,
                    identifier_type="iso3166",
                    identifier_value=iso2,
                    confidence=1.0,
                    provenance={**prov_base, "kind": "iso2"},
                )
                _upsert_identifier(
                    cur,
                    entity_id=entity_id,
                    identifier_type="iso3166",
                    identifier_value=iso3,
                    confidence=1.0,
                    provenance={**prov_base, "kind": "iso3"},
                )
                _upsert_identifier(
                    cur,
                    entity_id=entity_id,
                    identifier_type="name",
                    identifier_value=name,
                    confidence=0.9,
                    provenance={**prov_base, "kind": "name"},
                )
                processed += 1
    return processed


@dataclass(frozen=True)
class OfacSdnRow:
    ent_num: str
    name: str
    sdn_type: str
    program: str


def parse_ofac_sdn_csv_text(csv_text: str) -> list[OfacSdnRow]:
    """Parse OFAC SDN CSV into a minimal row structure (no network)."""
    import csv
    import io

    out: list[OfacSdnRow] = []
    reader = csv.reader(io.StringIO(csv_text))
    for row in reader:
        # Expected columns: ent_num, sdn_name, sdn_type, program, ... (rest ignored)
        if not row or len(row) < 4:
            continue
        ent_num = (row[0] or "").strip()
        name = (row[1] or "").strip()
        sdn_type = (row[2] or "").strip()
        program = (row[3] or "").strip()
        if not ent_num or not name:
            continue
        out.append(OfacSdnRow(ent_num=ent_num, name=name, sdn_type=sdn_type, program=program))
    return out


def download_ofac_sdn_csv(*, cache_dir: Path, url: str = "https://www.treasury.gov/ofac/downloads/sdn.csv") -> tuple[Path, str, str]:
    """Download OFAC SDN CSV to cache_dir and return (path, final_url, sha256_hex)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    final_url = str(r.url)
    content = r.content
    digest = sha256(content).hexdigest()
    out_path = cache_dir / f"ofac_sdn_{digest[:12]}.csv"
    if not out_path.exists():
        out_path.write_bytes(content)
    return out_path, final_url, digest


def seed_ofac_sdn_from_csv_path(
    pg_dsn: str,
    *,
    csv_path: Path,
    source_url: Optional[str] = None,
    sha256_hex: Optional[str] = None,
) -> int:
    """Seed sanctions_target entities from a local OFAC SDN CSV file.

    Returns: number of SDN entities processed (not DB rows).
    """
    ensure_postgres_schema(pg_dsn)
    text = csv_path.read_text(encoding="utf-8", errors="replace")
    rows = parse_ofac_sdn_csv_text(text)
    processed = 0
    fetched_at = datetime.now(timezone.utc).isoformat()

    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            for r in rows:
                entity_id = f"sanctions_ofac_sdn_{r.ent_num}"
                _upsert_entity(cur, entity_id=entity_id, entity_type="sanctions_target", label=r.name)
                prov_base = {
                    "source_system": "seed_ws0",
                    "dataset": "ofac_sdn",
                    "source_url": source_url,
                    "sha256": sha256_hex,
                    "fetched_at": fetched_at,
                    "sdn_type": r.sdn_type,
                    "program": r.program,
                }
                _upsert_identifier(
                    cur,
                    entity_id=entity_id,
                    identifier_type="ofac_id",
                    identifier_value=r.ent_num,
                    confidence=1.0,
                    provenance={**prov_base, "kind": "ent_num"},
                )
                _upsert_identifier(
                    cur,
                    entity_id=entity_id,
                    identifier_type="name",
                    identifier_value=r.name,
                    confidence=0.8,
                    provenance={**prov_base, "kind": "name"},
                )
                processed += 1
    return processed



