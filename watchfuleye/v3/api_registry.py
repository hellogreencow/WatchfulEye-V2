"""WS0: V3 API auto-registration.

Problem: `web_app.py` is a shared hot file. If every workstream has to touch it
to register a new V3 blueprint, parallel development will conflict.

Solution: auto-discover V3 API modules (convention: `watchfuleye.v3.*_api`) and
register any Flask `Blueprint` objects exported as `bp_v3_*`.

Safety:
- Import failures are caught and logged (never takes down the app).
- Only modules matching the `_api` suffix are imported (avoids heavy tooling).
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any, Callable

from flask import Blueprint, Flask


def register_v3_blueprints(app: Flask, log: Callable[[str], Any]) -> None:
    import watchfuleye.v3 as v3_pkg

    prefix = v3_pkg.__name__ + "."
    for modinfo in pkgutil.iter_modules(v3_pkg.__path__, prefix):
        mod_name = modinfo.name
        if not mod_name.endswith("_api"):
            continue
        try:
            module = importlib.import_module(mod_name)
        except Exception as e:
            log(f"V3 API module not registered (import failed): {mod_name}: {e}")
            continue

        for attr in dir(module):
            if not attr.startswith("bp_v3_"):
                continue
            bp = getattr(module, attr, None)
            if not isinstance(bp, Blueprint):
                continue
            try:
                app.register_blueprint(bp)
                log(f"V3 API blueprint registered: {mod_name}.{attr} ({bp.url_prefix})")
            except Exception as e:
                log(f"V3 API blueprint not registered: {mod_name}.{attr}: {e}")


