import json
import os
from pathlib import Path
import pytest

# Assuming the script is run from the project root or tests/ directory
# Adjust the path to infra/helm/grafana/dashboards if necessary
GRAFANA_DASHBOARDS_DIR = Path(__file__).parent.parent.parent / "infra" / "helm" / "grafana" / "dashboards"

EXPECTED_MIN_PANELS = 4

@pytest.mark.parametrize(
    "dashboard_file",
    [f for f in os.listdir(GRAFANA_DASHBOARDS_DIR) if f.endswith("_metrics.json")]
)
def test_grafana_dashboard_structure(dashboard_file):
    dashboard_path = GRAFANA_DASHBOARDS_DIR / dashboard_file
    assert dashboard_path.exists(), f"Dashboard file {dashboard_file} should exist."

    with open(dashboard_path, 'r') as f:
        try:
            dashboard_json = json.load(f)
        except json.JSONDecodeError as e:
            pytest.fail(f"Failed to parse JSON for {dashboard_file}: {e}")

    assert "title" in dashboard_json, f"Dashboard {dashboard_file} must have a title."
    assert "uid" in dashboard_json, f"Dashboard {dashboard_file} must have a UID."
    assert "panels" in dashboard_json, f"Dashboard {dashboard_file} must have a panels array."
    
    panels = dashboard_json.get("panels", [])
    assert isinstance(panels, list), f"Dashboard {dashboard_file} 'panels' should be a list."
    
    # Check for minimum number of panels as per the prompt
    assert len(panels) >= EXPECTED_MIN_PANELS, \
        f"Dashboard {dashboard_file} should have at least {EXPECTED_MIN_PANELS} panels, found {len(panels)}."

    for i, panel in enumerate(panels):
        assert "title" in panel, f"Panel {i+1} in {dashboard_file} must have a title."
        assert "type" in panel, f"Panel {i+1} in {dashboard_file} must have a type."
        if panel["type"] != "row": # Rows don't need targets
            assert "targets" in panel, f"Panel {i+1} ('{panel.get('title')}') in {dashboard_file} must have targets."
            assert isinstance(panel["targets"], list), f"Panel {i+1} targets in {dashboard_file} should be a list."
            if panel["targets"]:
                 assert "expr" in panel["targets"][0], f"First target in Panel {i+1} ('{panel.get('title')}') in {dashboard_file} should have an expr."

        assert "gridPos" in panel, f"Panel {i+1} in {dashboard_file} must have gridPos."

# Add more specific tests if needed, e.g., checking for specific panel types or queries. 