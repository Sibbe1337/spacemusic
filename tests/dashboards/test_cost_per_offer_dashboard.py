import json
import os
import unittest

class TestCostPerOfferDashboard(unittest.TestCase):

    def test_dashboard_loads_and_has_correct_panel_title(self):
        # Construct the path to the dashboard file relative to this test file
        # Assumes the test file is in tests/dashboards/ and dashboard is in infra/helm/grafana/dashboards/
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        dashboard_path = os.path.join(base_dir, "infra", "helm", "grafana", "dashboards", "cost_per_offer.json")

        self.assertTrue(os.path.exists(dashboard_path), f"Dashboard file not found at {dashboard_path}")

        with open(dashboard_path, 'r') as f:
            try:
                dashboard_json = json.load(f)
            except json.JSONDecodeError as e:
                self.fail(f"Failed to decode JSON from {dashboard_path}: {e}")

        self.assertIsNotNone(dashboard_json, "Dashboard JSON should not be None")
        self.assertIn("panels", dashboard_json, "Dashboard should have a 'panels' key")

        cost_per_offer_panel_found = False
        for panel in dashboard_json.get("panels", []):
            if panel.get("title") == "€ per Offer (Daily Average)":
                cost_per_offer_panel_found = True
                break
        
        self.assertTrue(cost_per_offer_panel_found, "Panel with title '€ per Offer (Daily Average)' not found.")

if __name__ == '__main__':
    unittest.main() 