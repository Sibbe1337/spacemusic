from services.offers.models import Creator, Offer


def test_database_integer_id_is_serialized_as_string_at_event_boundary():
    creator = Creator(
        id=7,
        platform_id="synthetic-platform-id",
        platform_name="distributor",
        username="synthetic-catalog",
    )
    offer = Offer(creator_id=creator.id, title="Synthetic catalog")
    event_payload = {
        "offer_id": str(offer.id),
        "creator_id": str(offer.creator_id),
        "status": offer.status.value,
    }

    assert isinstance(creator.id, int)
    assert event_payload["creator_id"] == "7"
    assert event_payload["status"] == "PENDING_VALUATION"
