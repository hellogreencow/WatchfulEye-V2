"""WS0.4: Seed minimal Entities/Identifiers into Postgres.

Goal: make `/api/v3/entities/resolve` useful in staging without external network calls.
This module is intentionally simple and deterministic.
"""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from watchfuleye.storage.postgres_schema import ensure_postgres_schema


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
          OR (entity_identifiers.provenance->>'source_system') = 'seed_minimal'
        """,
        (entity_id, identifier_type, identifier_value, confidence, Jsonb(provenance)),
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


