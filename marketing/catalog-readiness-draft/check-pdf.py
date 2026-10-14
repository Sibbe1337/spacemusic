"""Validate the generated sample's structure and public links, not legal claims."""
import json
from pathlib import Path
from pypdf import PdfReader

root = Path(__file__).resolve().parent
path = root.parent.parent / "output/pdf/space-catalog-readiness-sample.pdf"
reader = PdfReader(path)
assert len(reader.pages) == 4, f"Expected four designed pages, got {len(reader.pages)}"
assert reader.trailer["/Root"].get("/MarkInfo", {}).get("/Marked")
assert not reader.get_fields(), "The sample must not collect data"
sources = set()
headings = ["Clarify the evidence.", "12,000 in the supplied year.", "What is present.", "An assumption is useful."]
for index, page in enumerate(reader.pages):
    text = page.extract_text()
    assert headings[index] in text, f"Missing intended heading, page {index + 1}"
    assert "SYNTHETIC-001" in text
    assert "Fictional data." in text
    assert f"{index + 1}/4" in text
    assert len(text) > 1200, "Unexpected near-empty page"
    for reference in page.get("/Annots", []):
        annotation = reference.get_object()
        action = annotation.get("/A", {})
        if "/URI" in action:
            url = str(action["/URI"])
            assert url.startswith("https://"), f"Non-public link in exported PDF: {url}"
            assert "127.0.0.1" not in url and "localhost" not in url
            sources.add(url)
assert "https://spacemusic.io/apply/" in sources
print(json.dumps({"pdf": str(path), "pages": 4, "tagged": True, "public_links": sorted(sources), "synthetic_label_every_page": True, "fields": 0}))
