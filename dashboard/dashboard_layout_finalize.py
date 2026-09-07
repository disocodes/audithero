from __future__ import annotations


LEGACY_GRID_COLUMNS = 6
CURRENT_GRID_COLUMNS = 12


def _scale_position(position: list[int]) -> list[int]:
    """Scale AuditHero's legacy six-column authoring grid to Databricks' 12-column canvas."""
    if not isinstance(position, list) or len(position) != 4:
        return position
    x, y, width, height = position
    # All AuditHero specifications were authored on a six-column grid. Scale only
    # positions that still fit that legacy grid so this stays safe for any future
    # widget deliberately authored directly on the 12-column canvas.
    if x >= 0 and width > 0 and x + width <= LEGACY_GRID_COLUMNS:
        return [x * 2, y, width * 2, height]
    return position


def _promote_live_simulator(page: dict) -> None:
    """Put the live simulator at the top of Employee Deep Dive instead of below old content."""
    widgets = page.get("widgets", []) or []
    simulator = [
        widget
        for widget in widgets
        if str(widget.get("name", "")).startswith("sim_")
        or str(widget.get("name", "")).startswith("live_sim")
    ]
    if not simulator:
        return

    simulator_names = {widget.get("name") for widget in simulator}
    simulator_min_y = min(widget.get("position", [0, 0, 1, 1])[1] for widget in simulator)
    simulator_max_bottom = max(
        widget.get("position", [0, 0, 1, 1])[1]
        + widget.get("position", [0, 0, 1, 1])[3]
        for widget in simulator
    )
    simulator_height = simulator_max_bottom - simulator_min_y
    gap = 2

    # Move the simulator block to y=0 while retaining the relative arrangement
    # designed in live_pay_simulator.py.
    for widget in simulator:
        position = list(widget.get("position", [0, 0, 1, 1]))
        position[1] = position[1] - simulator_min_y
        widget["position"] = position

    # Move the pre-existing Employee Deep Dive content below the simulator. This
    # makes the new interactive controls immediately visible when opening the page.
    for widget in widgets:
        if widget.get("name") in simulator_names:
            continue
        position = list(widget.get("position", [0, 0, 1, 1]))
        position[1] = position[1] + simulator_height + gap
        widget["position"] = position


def enhance_spec(spec: dict) -> dict:
    employee_page = next(
        (page for page in spec.get("pages", []) if page.get("name") == "employee_deep_dive"),
        None,
    )
    if employee_page is not None:
        _promote_live_simulator(employee_page)

    # Databricks expanded the dashboard grid from 6 to 12 columns in 2026. AuditHero
    # keeps its concise six-column source specifications, then expands them here so
    # every page uses the full modern canvas width.
    for page in spec.get("pages", []) or []:
        for widget in page.get("widgets", []) or []:
            if "position" in widget:
                widget["position"] = _scale_position(widget["position"])

    spec["layout_grid_columns"] = CURRENT_GRID_COLUMNS
    return spec
