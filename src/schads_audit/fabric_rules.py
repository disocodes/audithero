from __future__ import annotations
import json
import tempfile
from pathlib import Path

from .rules import RuleLibrary


def bundled_rule_library() -> RuleLibrary:
    """Load the rule library embedded into the Fabric deployment wheel.

    `fabric/scripts/build_fabric_wheel.py` generates `_embedded_rules.py` immediately
    before building the wheel. The generated module is not source-controlled; the
    canonical rule packs remain under `rules/MA000100`.
    """
    try:
        from ._embedded_rules import RULE_FILES
    except ImportError as exc:
        raise RuntimeError(
            "This AuditHero wheel does not contain embedded rule packs. Build it with "
            "fabric/scripts/build_fabric_wheel.py."
        ) from exc

    temp = tempfile.TemporaryDirectory(prefix="audithero_rules_")
    root = Path(temp.name) / "MA000100"
    root.mkdir(parents=True, exist_ok=True)
    for rel_path, text in RULE_FILES.items():
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    lib = RuleLibrary(root)
    # RuleLibrary eagerly loads every JSON object, so the temporary files can go.
    temp.cleanup()
    return lib
