"""Whitelisted facts, not a valuation or an interpretation of provider samples."""

from .contracts import ProviderError, coverage, decimal_string, provider_id, short_text


def normalize_page(resource, response, page, *, max_records):
    rows = response.get("data")
    if not isinstance(rows, list) or len(rows) > max_records:
        raise ProviderError("provider_schema_invalid")
    facts = []
    totals = None
    terminal = True
    if resource == "releases":
        names = ("currentPage", "perPage", "totalItems", "totalPages")
        if any(type(response.get(name)) is not int for name in names):
            raise ProviderError("provider_pagination_invalid")
        current, size, count, pages = (response[name] for name in names)
        if current != page or not 1 <= size <= 100 or count < 0 or pages < 0:
            raise ProviderError("provider_pagination_invalid")
        if count == 0:
            if page != 1 or rows or pages not in (0, 1):
                raise ProviderError("provider_pagination_invalid")
        elif (
            pages != (count + size - 1) // size
            or page > pages
            or len(rows) != min(size, count - (page - 1) * size)
        ):
            raise ProviderError("provider_pagination_invalid")
        terminal = page >= pages
        totals = {"size": size, "count": count, "pages": pages}
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ProviderError("provider_schema_invalid")
            identity = provider_id(row.get("id"))
            if identity in seen:
                raise ProviderError("provider_duplicate_record")
            seen.add(identity)
            facts.append(
                {
                    "key": identity,
                    "amount": None,
                    "payload": {
                        "kind": "release",
                        "provider_release_id": identity,
                        "title": short_text(row.get("title"), nullable=True),
                        "upc": short_text(row.get("upc"), 64, nullable=True),
                    },
                }
            )
    else:
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise ProviderError("provider_schema_invalid")
            amount = (
                decimal_string(row.get("total"))
                if row.get("total") is not None
                else None
            )
            facts.append(
                {
                    "key": str(index),
                    "amount": amount,
                    "payload": {
                        "kind": "reported_amount",
                        "amount": amount,
                        "reported_date": short_text(row.get("date"), 64, nullable=True),
                        "source_resource": resource,
                        **coverage(),
                    },
                }
            )
    return facts, totals, terminal
