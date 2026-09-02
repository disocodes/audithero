from __future__ import annotations

import json
import re
from typing import Any


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", value.lower())[:48] or "field"


def _position(values: list[int]) -> dict[str, int]:
    return {"x": values[0], "y": values[1], "width": values[2], "height": values[3]}


def _query(dataset: str, fields: list[tuple[str, str]], *, disaggregated: bool = False, name: str = "main_query") -> dict[str, Any]:
    return {
        "name": name,
        "query": {
            "datasetName": dataset,
            "fields": [{"name": field_name, "expression": expression} for field_name, expression in fields],
            "disaggregated": disaggregated,
        },
    }


def _text(widget: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "widget": {"name": widget.get("name", f"text_{index}"), "textbox_spec": widget["text"]},
        "position": _position(widget["position"]),
    }


def _filter(widget: dict[str, Any], index: int) -> dict[str, Any]:
    field = widget["field"]
    query_name = f"filter_{_slug(field)}_{index}_q"
    query = {
        "name": query_name,
        "query": {
            "datasetName": widget["dataset"],
            "fields": [
                {"name": field, "expression": f"`{field}`"},
                {
                    "name": f"{field}_associativity",
                    "expression": "COUNT_IF(`associative_filter_predicate_group`)",
                },
            ],
            "disaggregated": False,
        },
    }
    multiple = widget.get("selection", "multi") == "multi"
    spec = {
        "version": 2,
        "widgetType": "filter-multi-select" if multiple else "filter-single-select",
        "encodings": {
            "fields": [
                {
                    "fieldName": field,
                    "displayName": widget.get("title", field),
                    "queryName": query_name,
                }
            ]
        },
        "frame": {"showTitle": True, "title": widget.get("title", field)},
        "disallowAll": False,
    }
    return {
        "widget": {"name": widget.get("name", f"filter_{index}"), "queries": [query], "spec": spec},
        "position": _position(widget["position"]),
    }


def _counter(widget: dict[str, Any], index: int) -> dict[str, Any]:
    field_name = _slug(widget["title"])
    value = {"fieldName": field_name, "displayName": widget["title"]}
    if widget.get("format") == "currency":
        value["format"] = {
            "type": "number-currency",
            "currencyCode": "AUD",
            "abbreviation": "none",
            "decimalPlaces": {"type": "exact", "places": int(widget.get("decimals", 2))},
        }
    else:
        value["format"] = {
            "type": "number-plain",
            "abbreviation": "none",
            "decimalPlaces": {"type": "exact", "places": int(widget.get("decimals", 0))},
        }
    spec = {
        "version": 2,
        "widgetType": "counter",
        "encodings": {"value": value},
        "frame": {"showTitle": True, "title": widget["title"]},
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
    fields = [(x_name, f"`{x_name}`"), (y_name, widget["y_expression"])]
    encodings = {
        "x": {"fieldName": x_name, "scale": {"type": "categorical"}, "displayName": widget.get("x_title", x_name)},
        "y": {"fieldName": y_name, "scale": {"type": "quantitative"}, "displayName": widget.get("y_title", y_name)},
    }
    if widget["type"] == "bar":
        encodings["label"] = {"show": True}
        if widget.get("orientation") == "horizontal":
            encodings["x"], encodings["y"] = (
                {"fieldName": y_name, "scale": {"type": "quantitative"}, "displayName": widget.get("y_title", y_name)},
                {"fieldName": x_name, "scale": {"type": "categorical"}, "displayName": widget.get("x_title", x_name)},
            )
    color = widget.get("color")
    if color:
        fields.append((color, f"`{color}`"))
        encodings["color"] = {"fieldName": color, "scale": {"type": "categorical"}, "displayName": color}
    spec = {
        "version": 3,
        "widgetType": widget["type"],
        "encodings": encodings,
        "frame": {"showTitle": True, "title": widget["title"]},
    }
    return {
        "widget": {
            "name": widget.get("name", f"{widget['type']}_{index}"),
            "queries": [_query(widget["dataset"], fields)],
            "spec": spec,
        },
        "position": _position(widget["position"]),
    }


def _table_column(column: dict[str, Any], order: int) -> dict[str, Any]:
    kind = column.get("kind", "string")
    type_map = {"string": "string", "number": "float", "integer": "integer", "boolean": "boolean", "date": "date", "datetime": "datetime"}
    result = {
        "fieldName": column["field"],
        "displayName": column.get("title", column["field"]),
        "title": column.get("title", column["field"]),
        "type": type_map.get(kind, "string"),
        "displayAs": "number" if kind in {"number", "integer"} else kind,
        "visible": True,
        "order": order,
        "allowSearch": bool(column.get("search", kind == "string")),
        "alignContent": "right" if kind in {"number", "integer"} else "left",
        "linkUrlTemplate": "{{ @ }}",
        "linkTextTemplate": "{{ @ }}",
        "linkTitleTemplate": "{{ @ }}",
        "linkOpenInNewTab": True,
        "highlightLinks": False,
        "allowHTML": False,
        "useMonospaceFont": False,
        "preserveWhitespace": False,
        "imageUrlTemplate": "{{ @ }}",
        "imageTitleTemplate": "{{ @ }}",
        "imageWidth": "",
        "imageHeight": "",
        "booleanValues": ["false", "true"],
    }
    if kind == "number":
        result["numberFormat"] = column.get("number_format", "0.00")
    elif kind == "integer":
        result["numberFormat"] = column.get("number_format", "0,0")
    return result


def _table(widget: dict[str, Any], index: int) -> dict[str, Any]:
    columns = widget["columns"]
    fields = [(column["field"], f"`{column['field']}`") for column in columns]
    spec = {
        "version": 1,
        "widgetType": "table",
        "allowHTMLByDefault": False,
        "condensed": True,
        "withRowNumber": False,
        "itemsPerPage": int(widget.get("page_size", 25)),
        "paginationSize": "default",
        "invisibleColumns": [],
        "encodings": {"columns": [_table_column(column, order) for order, column in enumerate(columns)]},
        "frame": {"showTitle": True, "title": widget["title"]},
    }
    return {
        "widget": {
            "name": widget.get("name", f"table_{index}"),
            "queries": [_query(widget["dataset"], fields, disaggregated=True)],
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
        datasets.append({
            "name": dataset["name"],
            "displayName": dataset.get("display_name", dataset["name"]),
            "queryLines": [query],
        })

    pages = []
    for page in spec["pages"]:
        layout = []
        for index, widget in enumerate(page["widgets"]):
            builder = _BUILDERS.get(widget["type"])
            if builder is None:
                raise ValueError(f"Unsupported dashboard widget type: {widget['type']}")
            layout.append(builder(widget, index))
        pages.append({
            "name": page["name"],
            "displayName": page["display_name"],
            "pageType": "PAGE_TYPE_CANVAS",
            "layout": layout,
        })
    return {"datasets": datasets, "pages": pages}


def build_dashboard_text(spec: dict[str, Any]) -> str:
    return json.dumps(build_dashboard(spec), separators=(",", ":"))
