from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from inspect import signature

EXPECTED_SEMANTIC_LINK_LABS_VERSION = "0.17.0"


def validate_fabric_bi_runtime() -> dict[str, str]:
    """Fail early if the Fabric Environment no longer matches AuditHero's BI API contract."""
    try:
        installed = version("semantic-link-labs")
    except PackageNotFoundError as exc:
        raise RuntimeError(
            "semantic-link-labs is not installed in the bound Fabric Environment. "
            "Republish AuditHero_Environment before building BI."
        ) from exc

    if installed != EXPECTED_SEMANTIC_LINK_LABS_VERSION:
        raise RuntimeError(
            "AuditHero BI dependency mismatch: "
            f"expected semantic-link-labs {EXPECTED_SEMANTIC_LINK_LABS_VERSION}, "
            f"found {installed}. Republish the pinned Fabric Environment."
        )

    from sempy_labs.directlake import (
        check_fallback_reason,
        generate_direct_lake_semantic_model,
    )
    from sempy_labs.report import (
        create_report_from_reportjson,
        report_rebind,
        update_report_from_reportjson,
    )
    from sempy_labs.tom import connect_semantic_model

    required_signatures = {
        "generate_direct_lake_semantic_model": (
            generate_direct_lake_semantic_model,
            {
                "dataset",
                "tables",
                "source",
                "source_type",
                "source_workspace",
                "use_sql_endpoint",
                "workspace",
                "refresh",
                "inherit_descriptions",
                "overwrite",
            },
        ),
        "create_report_from_reportjson": (
            create_report_from_reportjson,
            {"report", "dataset", "report_json", "workspace"},
        ),
        "update_report_from_reportjson": (
            update_report_from_reportjson,
            {"report", "report_json", "workspace"},
        ),
        "report_rebind": (
            report_rebind,
            {"report", "dataset", "report_workspace", "dataset_workspace"},
        ),
        "connect_semantic_model": (
            connect_semantic_model,
            {"dataset", "workspace", "readonly"},
        ),
        "check_fallback_reason": (
            check_fallback_reason,
            {"dataset", "workspace"},
        ),
    }

    for name, (func, required) in required_signatures.items():
        actual = set(signature(func).parameters)
        missing = sorted(required - actual)
        if missing:
            raise RuntimeError(
                f"AuditHero Fabric BI API contract mismatch for {name}: "
                f"missing parameter(s) {', '.join(missing)}. "
                "Do not continue; restore the pinned Environment or update AuditHero's BI adapter."
            )

    return {
        "semantic_link_labs": installed,
        "status": "compatible",
    }
