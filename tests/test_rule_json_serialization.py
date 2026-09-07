import json
from datetime import date, datetime

import pytest

from schads_audit.json_utils import json_dumps_public


def test_rule_json_serialization_converts_dates_to_iso_strings():
    payload = {
        "operative_date": date(2026, 7, 1),
        "generated_at": datetime(2026, 7, 1, 12, 30, 45),
    }

    decoded = json.loads(json_dumps_public(payload))

    assert decoded["operative_date"] == "2026-07-01"
    assert decoded["generated_at"] == "2026-07-01T12:30:45"


def test_rule_json_serialization_omits_runtime_cache_keys():
    payload = {
        "operative_date": "2026-07-01",
        "_operative_date_obj": date(2026, 7, 1),
        "nested": {"kept": 1, "_cache": object()},
    }

    decoded = json.loads(json_dumps_public(payload))

    assert decoded == {"operative_date": "2026-07-01", "nested": {"kept": 1}}


def test_rule_json_serialization_still_fails_for_unknown_objects():
    class Unsupported:
        pass

    with pytest.raises(TypeError, match="Unsupported"):
        json_dumps_public({"value": Unsupported()})
