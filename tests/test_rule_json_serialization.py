import json
from datetime import date, datetime

import pytest

from schads_audit.databricks_io import _json_dumps


def test_rule_json_serialization_converts_dates_to_iso_strings():
    payload = {
        "operative_date": date(2026, 7, 1),
        "generated_at": datetime(2026, 7, 1, 12, 30, 45),
    }

    decoded = json.loads(_json_dumps(payload))

    assert decoded["operative_date"] == "2026-07-01"
    assert decoded["generated_at"] == "2026-07-01T12:30:45"


def test_rule_json_serialization_still_fails_for_unknown_objects():
    class Unsupported:
        pass

    with pytest.raises(TypeError, match="Unsupported"):
        _json_dumps({"value": Unsupported()})
