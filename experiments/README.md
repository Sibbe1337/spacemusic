# Experiments and local demos

These are not production entry points. Keep fictional fixtures, demo role
switches and research-provider calls separate from authenticated customer flows.

| Experiment | Purpose | Guide |
| --- | --- | --- |
| `dealflow-preview/` | Current local seller/reviewer brokerage-preparation demo | [Run and boundaries](dealflow-preview/README.md) |
| `jev-catalog-review/` | Synthetic classification evaluation; offline by default | [Evaluation protocol](jev-catalog-review/README.md) |
| `reviewer-workspace-preview/` | Separate reviewer interface prototype | [Prototype guide](reviewer-workspace-preview/README.md) |

Other retained previews live under `services/` for compatibility:
[read-only cloud preview](../services/catalog_review_cloud_preview/README.md)
and [original catalog prototype](../services/catalog_review_preview/README.md).
Their locations have not been changed because code, packaging and test references
still use them. See the [project map](../docs/PROJECT-MAP.md).
