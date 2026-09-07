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
        return targets
    if widget.get("dataset") and widget.get("field"):
        return [{
            "dataset": str(widget["dataset"]),
            "field": str(widget["field"]),
            "display_name": str(widget.get("title") or widget["field"]),
        }]
    return []


def _parameter_targets(widget: dict[str, Any]) -> list[dict[str, str]]:
    targets = []
    seen = set()
    for item in widget.get("parameters", []) or []:
        dataset = str(item["dataset"])
        keyword = str(item.get("keyword") or item.get("parameter"))
        key = (dataset, keyword)
        if key in seen:
            continue
        seen.add(key)
        targets.append(
            {
                "dataset": dataset,
                "keyword": keyword,
                "display_name": str(item.get("display_name") or widget.get("title") or keyword),
            }
        )
    return targets


def _filter(widget: dict[str, Any], index: int) -> dict[str, Any]:
    field_targets = _filter_targets(widget)
    parameter_targets = _parameter_targets(widget)
    if not field_targets and not parameter_targets:
        raise ValueError("A filter must bind at least one dataset field or parameter")

    filter_type = widget.get("filter_type", "categorical")
    queries = []
    encodings = []

    for target_index, target in enumerate(field_targets):
        dataset = target["dataset"]
        field = target["field"]
        query_name = f"filter_{_slug(widget.get('name', field))}_{index}_f{target_index}_q"
        if filter_type == "range-slider":
            fields = [
                {"name": f"min({field})", "expression": f"MIN(`{field}`)"},
                {"name": f"max({field})", "expression": f"MAX(`{field}`)"},
            ]
        else:
            fields = [{"name": field, "expression": f"`{field}`"}]
        queries.append(
            {
                "name": query_name,
                "query": {
                    "datasetName": dataset,
                    "fields": fields,
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

    for target_index, target in enumerate(parameter_targets):
        dataset = target["dataset"]
        keyword = target["keyword"]
        query_name = f"filter_{_slug(widget.get('name', keyword))}_{index}_p{target_index}_q"
        queries.append(
            {
                "name": query_name,
                "query": {
                    "datasetName": dataset,
                    "parameters": [{"name": keyword, "keyword": keyword}],
                    "disaggregated": False,
                },
            }
        )
        encodings.append(
            {
                "parameterName": keyword,
                "displayName": target["display_name"],
                "queryName": query_name,
            }
        )

    if filter_type == "date-range":
        widget_type = "filter-date-range-picker"
    elif filter_type == "range-slider":
        widget_type = "range-slider"
    else:
        multiple = widget.get("selection", "multi") == "multi"
        widget_type = "filter-multi-select" if multiple else "filter-single-select"

    spec: dict[str, Any] = {
        "version": 2,
        "widgetType": widget_type,
        "encodings": {"fields": encodings},
        "frame": {
            "showTitle": True,
            "title": widget.get("title", (field_targets or parameter_targets)[0].get("field") or (field_targets or parameter_targets)[0].get("keyword")),
            **(
                {"showDescription": True, "description": widget["description"]}
                if widget.get("description")
                else {}
            ),
        },
    }
    if widget.get("default_selection") is not None:
        spec["selection"] = {"defaultSelection": widget["default_selection"]}

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
        item: dict[str, Any] = {
            "name": dataset["name"],
            "displayName": dataset.get("display_name", dataset["name"]),
            "queryLines": [query],
        }
        if dataset.get("parameters"):
            item["parameters"] = dataset["parameters"]
        datasets.append(item)

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
