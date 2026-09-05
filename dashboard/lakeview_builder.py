from __future__ import annotations

import json
import re
from typing import Any


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", value.lower())[:48] or "field"


def _position(values: list[int]) -> dict[str, int]:
    return {"x": values[0], "y": values[1], "width": values[2], "height": values[3]}


def _query(
    dataset: str,
    fields: list[tuple[str, str]],
    *,
    disaggregated: bool = False,
    name: str = "main_query",
) -> dict[str, Any]:
    return {
        "name": name,
        "query": {
            "datasetName": dataset,
            "fields": [{"name": field_name, "expression": expression} for field_name, expression in fields],
            "disaggregated": disaggregated,
        },
    }


def _number_format(widget: dict[str, Any], *, default_decimals: int = 0) -> dict[str, Any]:
    if widget.get("format") == "currency":
        return {
            "type": "number-currency",
            "currencyCode": "AUD",
            "abbreviation": "none",
            "decimalPlaces": {"type": "exact", "places": int(widget.get("decimals", 2))},
        }
    return {
        "type": "number-plain",
        "abbreviation": "none",
        "decimalPlaces": {"type": "exact", "places": int(widget.get("decimals", default_decimals))},
    }


def _text(widget: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "widget": {
            "name": widget.get("name", f"text_{index}"),
            "multilineTextboxSpec": {"lines": [widget["text"]]},
        },
        "position": _position(widget["position"]),
    }


def _filter_targets(widget: dict[str, Any]) -> list[dict[str, str]]:
    """Return one field binding per dataset.

    Databricks field filters can target one field in each of multiple datasets.
    Legacy AuditHero specs may still use the single ``dataset``/``field`` form.
    """
    if widget.get("fields"):
        targets = []
        seen = set()
        for item in widget["fields"]:
            dataset = str(item["dataset"])
            field = str(item["field"])
            key = (dataset, field)
            if key in seen:
                continue
            seen.add(key)
            targets.append(
                {
                    "dataset": dataset,
                    "field": field,
                    "display_name": str(item.get("display_name") or widget.get("title") or field),
                }
            )
        if not targets:
            raise ValueError("Filter fields list must contain at least one dataset/field binding")
        return targets

    return [{
        "dataset": str(widget["dataset"]),
        "field": str(widget["field"]),
        "display_name": str(widget.get("title") or widget["field"]),
    }]


def _filter(widget: dict[str, Any], index: int) -> dict[str, Any]:
    targets = _filter_targets(widget)
    queries = []
    encodings = []
    for target_index, target in enumerate(targets):
        dataset = target["dataset"]
        field = target["field"]
        query_name = f"filter_{_slug(widget.get('name', field))}_{index}_{target_index}_q"
        queries.append(
            {
                "name": query_name,
                "query": {
                    "datasetName": dataset,
                    "fields": [{"name": field, "expression": f"`{field}`"}],
                    "disaggregated": False,
                },
            }
        )
        encodings.append(
            {
                "fieldName": field,
                "displayName": target["display_name"],
                "queryName": query_name,
            }
        )

    filter_type = widget.get("filter_type", "categorical")
    if filter_type == "date-range":
        widget_type = "filter-date-range-picker"
    else:
        multiple = widget.get("selection", "multi") == "multi"
        widget_type = "filter-multi-select" if multiple else "filter-single-select"

    title = widget.get("title", targets[0]["field"])
    spec = {
        "version": 2,
        "widgetType": widget_type,
        "encodings": {"fields": encodings},
        "frame": {
            "showTitle": True,
            "title": title,
            **(
                {"showDescription": True, "description": widget["description"]}
                if widget.get("description")
                else {}
            ),
        },
    }
    return {
        "widget": {
            "name": widget.get("name", f"filter_{index}"),
            "queries": queries,
            "spec": spec,
        },
        "position": _position(widget["position"]),
    }


def _counter(widget: dict[str, Any], index: int) -> dict[str, Any]:
    field_name = _slug(widget["title"])
    value = {
        "fieldName": field_name,
        "displayName": widget["title"],
        "format": _number_format(widget),
    }
    spec = {
        "version": 2,
        "widgetType": "counter",
        "encodings": {"value": value},
        "frame": {
            "showTitle": True,
            "title": widget["title"],
            **(
                {"showDescription": True, "description": widget["description"]}
                if widget.get("description")
                else {}
            ),
        },
    }
    return {
        "widget": {
            "name": widget.get("name", f"counter_{index}"),
            "queries": [_query(widget["dataset"], [(field_name, widget["expression"])])],
            "spec": spec,
        },
        "position": _position(widget["position"]),
    }


def _chart(widget: dict[str, Any], index: int) -> dict[str, Any]:
    x_name = widget["x"]
    y_name = widget.get("y_name", _slug(widget["y_expression"]))
    x_scale = widget.get("x_scale", "categorical")
    fields = [(x_name, f"`{x_name}`"), (y_name, widget["y_expression"])]
    encodings: dict[str, Any] = {
        "x": {
            "fieldName": x_name,
            "scale": {"type": x_scale},
            "displayName": widget.get("x_title", x_name),
        },
        "y": {
            "fieldName": y_name,
            "scale": {"type": "quantitative"},
            "displayName": widget.get("y_title", y_name),
        },
    }
    if widget.get("format"):
        encodings["y"]["format"] = _number_format(widget, default_decimals=2)
    if widget["type"] == "bar":
        encodings["label"] = {"show": True}
        if widget.get("orientation") == "horizontal":
            encodings["x"], encodings["y"] = (
                {
                    "fieldName": y_name,
                    "scale": {"type": "quantitative"},
                    "displayName": widget.get("y_title", y_name),
                    **(
                        {"format": _number_format(widget, default_decimals=2)}
                        if widget.get("format")
                        else {}
                    ),
                },
                {
                    "fieldName": x_name,
                    "scale": {"type": x_scale},
                    "displayName": widget.get("x_title", x_name),
                },
            )
    color = widget.get("color")
    if color:
        if color not in {x_name, y_name}:
            fields.append((color, f"`{color}`"))
        encodings["color"] = {
            "fieldName": color,
            "scale": {"type": "categorical"},
            "displayName": widget.get("color_title", color),
        }

    spec = {
        "version": 3,
        "widgetType": widget["type"],
        "encodings": encodings,
        "frame": {
            "showTitle": True,
            "title": widget["title"],
            **(
                {"showDescription": True, "description": widget["description"]}
                if widget.get("description")
                else {}
            ),
        },
    }
    return {
        "widget": {
            "name": widget.get("name", f"{widget['type']}_{index}"),
            "queries": [_query(widget["dataset"], fields)],
            "spec": spec,
        },
        "position": _position(widget["position"]),
    }


def _table_column(column: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "fieldName": column["field"],
        "displayName": column.get("title", column["field"]),
    }
    kind = column.get("kind", "string")
    if kind == "number":
        currency = str(column.get("number_format", "")).startswith("$")
        result["format"] = {
            "type": "number-currency" if currency else "number-plain",
            **({"currencyCode": "AUD"} if currency else {}),
            "abbreviation": "none",
            "decimalPlaces": {"type": "max", "places": 2},
        }
    elif kind == "integer":
        result["format"] = {
            "type": "number-plain",
            "abbreviation": "none",
            "decimalPlaces": {"type": "exact", "places": 0},
        }
    elif kind == "json":
        result["displayAs"] = "json"
    if column.get("tooltip"):
        result["tooltip"] = {"templatedText": column["tooltip"]}
    return result


def _table(widget: dict[str, Any], index: int) -> dict[str, Any]:
    columns = widget["columns"]
    fields = [(column["field"], f"`{column['field']}`") for column in columns]
    spec = {
        "version": 2,
        "widgetType": "table",
        "encodings": {"columns": [_table_column(column) for column in columns]},
        "frame": {
            "showTitle": True,
            "title": widget["title"],
            **(
                {"showDescription": True, "description": widget["description"]}
                if widget.get("description")
                else {}
            ),
        },
    }
    return {
        "widget": {
            "name": widget.get("name", f"table_{index}"),
            "queries": [
                _query(
                    widget["dataset"],
                    fields,
                    disaggregated=bool(widget.get("disaggregated", True)),
                )
            ],
            "spec": spec,
        },
        "position": _position(widget["position"]),
    }


_BUILDERS = {
    "text": _text,
    "filter": _filter,
    "counter": _counter,
    "bar": _chart,
    "line": _chart,
    "table": _table,
}


def build_dashboard(spec: dict[str, Any]) -> dict[str, Any]:
    datasets = []
    for dataset in spec["datasets"]:
        query = re.sub(r"\s+", " ", dataset["query"]).strip()
        datasets.append(
            {
                "name": dataset["name"],
                "displayName": dataset.get("display_name", dataset["name"]),
                "queryLines": [query],
            }
        )

    pages = []
    for page in spec["pages"]:
        layout = []
        for index, widget in enumerate(page["widgets"]):
            builder = _BUILDERS.get(widget["type"])
            if builder is None:
                raise ValueError(f"Unsupported dashboard widget type: {widget['type']}")
            layout.append(builder(widget, index))
        pages.append(
            {
                "name": page["name"],
                "displayName": page["display_name"],
                "pageType": page.get("page_type", "PAGE_TYPE_CANVAS"),
                "layoutVersion": "GRID_V1",
                "layout": layout,
            }
        )
    result = {"datasets": datasets, "pages": pages}
    if spec.get("uiSettings"):
        result["uiSettings"] = spec["uiSettings"]
    return result


def build_dashboard_text(spec: dict[str, Any]) -> str:
    return json.dumps(build_dashboard(spec), separators=(",", ":"))
