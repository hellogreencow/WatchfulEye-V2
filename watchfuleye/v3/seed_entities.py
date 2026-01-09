"""WS0.5 seed runner (ISO-3166 + OFAC SDN).

This is an explicit operator tool: run it manually (or via controlled jobs),
never implicitly at request time.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from watchfuleye.v3.entity_seeds import (
    download_ofac_sdn_csv,
    seed_iso3166_all_from_json,
    seed_ofac_sdn_from_csv_path,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pg-dsn", default=os.environ.get("PG_DSN", ""), help="Postgres DSN (or set PG_DSN).")
    ap.add_argument(
        "--iso-json",
        default=str(Path(__file__).parent / "data" / "iso3166_all.json"),
        help="Path to ISO-3166 JSON dataset (checked into repo).",
    )
    ap.add_argument(
        "--ofac-cache-dir",
        default="/var/lib/watchfuleye/seeds",
        help="Cache directory for OFAC downloads (csv stored by sha256).",
    )
    ap.add_argument(
        "--ofac-url",
        default="https://www.treasury.gov/ofac/downloads/sdn.csv",
        help="OFAC SDN CSV URL (redirects allowed).",
    )
    ap.add_argument("--no-iso", action="store_true", help="Skip ISO seeding.")
    ap.add_argument("--no-ofac", action="store_true", help="Skip OFAC seeding.")
    args = ap.parse_args()

    if not args.pg_dsn:
        raise SystemExit("ERROR: missing --pg-dsn (or PG_DSN env var)")

    failures: list[str] = []

    if not args.no_iso:
        try:
            iso_path = Path(args.iso_json)
            n = seed_iso3166_all_from_json(args.pg_dsn, json_path=iso_path)
            print(f"seed_iso3166_all_from_json={n}")
        except Exception as e:
            failures.append(f"iso: {e}")
            print(f"ERROR: ISO seed failed: {e}", file=sys.stderr)

    if not args.no_ofac:
        try:
            cache_dir = Path(args.ofac_cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)
            # Writability check (avoid downloading then failing to cache).
            test_path = cache_dir / ".write_test"
            test_path.write_text("ok", encoding="utf-8")
            test_path.unlink(missing_ok=True)

            csv_path, final_url, digest = download_ofac_sdn_csv(cache_dir=cache_dir, url=args.ofac_url)
            n = seed_ofac_sdn_from_csv_path(args.pg_dsn, csv_path=csv_path, source_url=final_url, sha256_hex=digest)
            print(f"seed_ofac_sdn_from_csv_path={n} (source={final_url}, sha256={digest})")
        except Exception as e:
            failures.append(f"ofac: {e}")
            print(f"ERROR: OFAC seed failed: {e}", file=sys.stderr)

    if failures:
        print(f"FAILED: {', '.join(failures)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


