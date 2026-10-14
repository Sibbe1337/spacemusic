"""Offline synthetic transport tests; no client construction or credentials."""

import io
import socket
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import boto3
import botocore.session
import pytest
from botocore.exceptions import ClientError
from botocore.loaders import Loader

from services.catalog_review.database import CommitOutcomeUnknown
from services.catalog_review.service import ReviewService
from services.catalog_review.storage import (
    MAX_DOCUMENT_BYTES,
    READ_CHUNK_BYTES,
    BlobStorageError,
    BlobWriteNotConfirmed,
    R2BlobStore,
)

ENDPOINT = "https://" + "a" * 32 + ".eu.r2.cloudflarestorage.com"
BUCKET = "synthetic-quarantine"
WORKSPACE = "11111111-1111-4111-8111-111111111111"
KEY = WORKSPACE + "/22222222-2222-4222-8222-222222222222"


@pytest.fixture(autouse=True)
def no_network_or_sdk_construction(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Test attempted a real socket or SDK client/session")

    for name in ("socket", "create_connection", "getaddrinfo"):
        monkeypatch.setattr(socket, name, forbidden)
    monkeypatch.setattr(boto3, "client", forbidden)
    monkeypatch.setattr(boto3, "Session", forbidden)
    monkeypatch.setattr(botocore.session.Session, "create_client", forbidden)


def response(status, **kwargs):
    return {"ResponseMetadata": {"HTTPStatusCode": status}, **kwargs}


class FakeBody(io.BytesIO):
    def __init__(self, value=b"abc", *, step=READ_CHUNK_BYTES, error=None):
        super().__init__(value)
        self.step = step
        self.error = error
        self.requests = []
        self.closes = 0

    def read(self, amount):
        assert 0 < amount <= READ_CHUNK_BYTES
        self.requests.append(amount)
        if self.error:
            raise self.error
        return super().read(min(amount, self.step))

    def close(self):
        self.closes += 1
        super().close()


class FakeClient:
    def __init__(self, *, region="auto"):
        self.meta = SimpleNamespace(
            endpoint_url=ENDPOINT,
            region_name=region,
            config=SimpleNamespace(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=5,
                read_timeout=5,
            ),
        )
        self._endpoint = SimpleNamespace(
            host=ENDPOINT, http_session=SimpleNamespace(_verify=True)
        )
        self.calls = []
        self.put_result = response(200)
        self.get_result = None
        self.delete_result = response(204)
        self.put_error = None
        self.get_error = None
        self.delete_error = None
        self.objects = {}
        self.commit_before_error = False

    def put_object(self, **kwargs):
        self.calls.append(("put", kwargs))
        if self.commit_before_error:
            self.objects[kwargs["Key"]] = kwargs["Body"]
        if self.put_error:
            raise self.put_error
        self.objects[kwargs["Key"]] = kwargs["Body"]
        return self.put_result

    def get_object(self, **kwargs):
        self.calls.append(("get", kwargs))
        if self.get_error:
            raise self.get_error
        return self.get_result

    def delete_object(self, **kwargs):
        self.calls.append(("delete", kwargs))
        if self.delete_error:
            raise self.delete_error
        self.objects.pop(kwargs["Key"], None)
        return self.delete_result


def store(client=None, **overrides):
    options = {"endpoint_url": ENDPOINT, "bucket": BUCKET, **overrides}
    return R2BlobStore(client if client is not None else FakeClient(), **options)


def test_erase_independently_inventories_and_verifies_orphan_objects():
    client = FakeClient()
    client.objects[KEY] = b"orphan"
    client.list_objects_v2 = lambda **kwargs: response(
        200,
        Contents=[
            {"Key": key} for key in client.objects if key.startswith(kwargs["Prefix"])
        ],
        IsTruncated=False,
    )
    client.get_error = ClientError(
        {"ResponseMetadata": {"HTTPStatusCode": 404}, "Error": {"Code": "NoSuchKey"}},
        "GetObject",
    )
    store(client).erase_and_verify(WORKSPACE)
    assert not client.objects


@pytest.mark.parametrize(
    "listing",
    [
        response(200, IsTruncated=True),
        response(
            200,
            Contents=[
                {
                    "Key": "33333333-3333-4333-8333-333333333333/22222222-2222-4222-8222-222222222222"
                }
            ],
            IsTruncated=False,
        ),
        response(500, IsTruncated=False),
    ],
)
def test_erase_never_claims_absence_for_incomplete_or_foreign_inventory(listing):
    client = FakeClient()
    client.list_objects_v2 = lambda **kwargs: listing
    with pytest.raises(BlobStorageError):
        store(client).erase_and_verify(WORKSPACE)


@pytest.mark.parametrize("region", ["auto", "", "us-east-1"])
def test_official_signing_regions_and_constructor_has_no_remote_calls(region):
    client = FakeClient(region=region)
    store(client, region_name=region)
    assert client.calls == []


@pytest.mark.parametrize(
    "region", ["weur", "eeur", "eu", "eu-west-1", "wnam", None, True]
)
def test_rejects_location_hints_and_arbitrary_signing_regions(region):
    client = FakeClient(region=region)
    with pytest.raises(ValueError):
        store(client, region_name=region)
    assert client.calls == []


@pytest.mark.parametrize(
    "endpoint",
    [
        ENDPOINT.replace("https:", "http:"),
        ENDPOINT.replace(".eu.", "."),
        ENDPOINT.replace(".eu.", ".weur."),
        ENDPOINT.replace(".eu.", ".us."),
        ENDPOINT + ".evil.test",
        ENDPOINT + "/",
        ENDPOINT + "/bucket",
        ENDPOINT + ":443",
        ENDPOINT + "?x=1",
        ENDPOINT + "#fragment",
        ENDPOINT + "\n",
        ENDPOINT.replace("https://", "https://user:password@"),
        "https://eu.r2.cloudflarestorage.com",
        "https://arbitrary.eu.r2.cloudflarestorage.com",
        "https://127.0.0.1",
        None,
    ],
)
def test_rejects_arbitrary_urls_and_non_eu_endpoints(endpoint):
    with pytest.raises(ValueError):
        store(endpoint_url=endpoint)


@pytest.mark.parametrize(
    "bucket", ["", "ab", "a" * 64, "Bucket", "a/b", "a.b", "-abc", "abc-", "a\nb", None]
)
def test_rejects_non_plain_buckets(bucket):
    with pytest.raises(ValueError):
        store(bucket=bucket)


@pytest.mark.parametrize("attribute", ["endpoint_url", "region_name"])
def test_checks_actual_injected_client_metadata(attribute):
    client = FakeClient()
    setattr(client.meta, attribute, "unexpected")
    with pytest.raises(ValueError):
        store(client)
    assert client.calls == []


def test_checks_actual_transport_host_not_just_meta():
    client = FakeClient()
    client._endpoint.host = "https://evil.test"
    with pytest.raises(ValueError):
        store(client)


@pytest.mark.parametrize("verify", [False, None, "", 0, 1, "relative.pem"])
def test_rejects_disabled_or_unknown_tls_verification(verify):
    client = FakeClient()
    client._endpoint.http_session._verify = verify
    with pytest.raises(ValueError):
        store(client)


def test_accepts_explicit_ca_path_without_reading_it():
    client = FakeClient()
    client._endpoint.http_session._verify = "/synthetic/trusted-ca.pem"
    store(client)
    assert client.calls == []


@pytest.mark.parametrize(
    "attribute,value",
    [
        ("signature_version", None),
        ("signature_version", "unsigned"),
        ("s3", None),
        ("s3", {"addressing_style": "virtual"}),
        ("s3", {"addressing_style": "path", "use_accelerate_endpoint": True}),
        ("s3", {"addressing_style": "path", "use_dualstack_endpoint": True}),
        ("use_dualstack_endpoint", True),
        ("use_fips_endpoint", True),
        ("connect_timeout", None),
        ("connect_timeout", 61),
        ("read_timeout", 0),
        ("read_timeout", True),
        ("read_timeout", float("inf")),
        ("read_timeout", float("nan")),
    ],
)
def test_rejects_unsafe_client_configuration(attribute, value):
    client = FakeClient()
    setattr(client.meta.config, attribute, value)
    with pytest.raises(ValueError):
        store(client)


def test_rejects_missing_client_methods_or_transport():
    with pytest.raises(ValueError):
        store(object())
    client = FakeClient()
    client.get_object = None
    with pytest.raises(ValueError):
        store(client)


@pytest.mark.parametrize("operation", ["put_if_absent", "get", "delete"])
def test_rechecks_client_before_each_operation(operation):
    client = FakeClient()
    adapter = store(client)
    client._endpoint.http_session._verify = False
    with pytest.raises(ValueError):
        getattr(adapter, operation)(
            KEY, b"abc"
        ) if operation == "put_if_absent" else getattr(adapter, operation)(KEY)
    assert client.calls == []


@pytest.mark.parametrize(
    "key",
    [
        "",
        "report.csv",
        WORKSPACE,
        "/" + KEY,
        KEY + "/more",
        KEY + ".pdf",
        KEY + "\n",
        KEY.replace("/", "%2f"),
        KEY.replace("/", "/../"),
        KEY.replace("/", "\\"),
        "https://example.com/" + KEY,
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/" + KEY.split("/")[1].replace("2", "A"),
        KEY.replace("-", ""),
        None,
        b"bytes",
    ],
)
@pytest.mark.parametrize("operation", ["put_if_absent", "get", "delete"])
def test_all_operations_reject_non_opaque_keys_without_io(key, operation):
    client = FakeClient()
    adapter = store(client)
    with pytest.raises(ValueError):
        getattr(adapter, operation)(
            key, b"abc"
        ) if operation == "put_if_absent" else getattr(adapter, operation)(key)
    assert client.calls == []


def test_installed_sdk_model_supports_conditional_put_header_offline():
    model = Loader().load_service_model("s3", "service-2")
    input_shape = model["operations"]["PutObject"]["input"]["shape"]
    field = model["shapes"][input_shape]["members"]["IfNoneMatch"]
    assert field["location"] == "header"
    assert field["locationName"] == "If-None-Match"


@pytest.mark.parametrize("size", [1, MAX_DOCUMENT_BYTES])
def test_put_is_one_conditional_private_request_with_no_head_or_acl(size):
    client = FakeClient()
    content = b"x" * size
    assert store(client).put_if_absent(KEY, content) is None
    assert client.calls == [
        (
            "put",
            {
                "Bucket": BUCKET,
                "Key": KEY,
                "Body": content,
                "ContentLength": size,
                "ContentType": "application/octet-stream",
                "CacheControl": "no-store",
                "IfNoneMatch": "*",
            },
        )
    ]


@pytest.mark.parametrize(
    "content", [b"", "text", bytearray(b"x"), None, b"x" * (MAX_DOCUMENT_BYTES + 1)]
)
def test_put_rejects_invalid_content_before_io(content):
    client = FakeClient()
    with pytest.raises(ValueError):
        store(client).put_if_absent(KEY, content)
    assert client.calls == []


@pytest.mark.parametrize(
    "code,status",
    [
        ("PreconditionFailed", 412),
        ("ConditionalRequestConflict", 409),
        ("AccessDenied", 403),
        ("InternalError", 500),
    ],
)
def test_remote_write_errors_never_retry_or_delete_existing_objects(code, status):
    client = FakeClient()
    client.objects[KEY] = b"original"
    client.put_error = ClientError(
        {"Error": {"Code": code}, "ResponseMetadata": {"HTTPStatusCode": status}},
        "PutObject",
    )
    with pytest.raises(BlobWriteNotConfirmed) as caught:
        store(client).put_if_absent(KEY, b"replacement")
    assert isinstance(caught.value, CommitOutcomeUnknown)
    assert caught.value.__cause__ is client.put_error
    assert client.objects[KEY] == b"original"
    assert [name for name, _ in client.calls] == ["put"]


@pytest.mark.parametrize(
    "result", [None, {}, response(202), response(412), {"ResponseMetadata": None}]
)
def test_bad_put_acknowledgement_is_never_success_or_cleanup(result):
    client = FakeClient()
    client.put_result = result
    with pytest.raises(BlobWriteNotConfirmed):
        store(client).put_if_absent(KEY, b"abc")
    assert client.objects[KEY] == b"abc"
    assert [name for name, _ in client.calls] == ["put"]


def test_existing_service_preserves_blob_after_remote_commit_and_lost_ack():
    client = FakeClient()
    client.commit_before_error = True
    client.put_error = TimeoutError("synthetic acknowledgement loss")
    service = object.__new__(ReviewService)
    cursor = SimpleNamespace(
        execute=Mock(), fetchone=Mock(side_effect=[None, {"count": 0}])
    )
    service.db = SimpleNamespace(transaction=lambda workspace: nullcontext(cursor))
    service._authorize = lambda *args, **kwargs: (
        WORKSPACE,
        {"principal_id": "synthetic"},
        {"revision": 0},
    )
    service._editable = Mock()
    with pytest.raises(BlobWriteNotConfirmed):
        service.quarantine(
            WORKSPACE + "." + "t" * 43, "report.csv", b"a,b", store(client)
        )
    assert list(client.objects.values()) == [b"a,b"]
    assert [name for name, _ in client.calls] == ["put"]


@pytest.mark.parametrize(
    "size,step", [(1, 1), (100, 3), (MAX_DOCUMENT_BYTES, READ_CHUNK_BYTES)]
)
def test_get_uses_bounded_reads_and_closes_on_success(size, step):
    client = FakeClient()
    body = FakeBody(b"x" * size, step=step)
    client.get_result = response(200, Body=body, ContentLength=size)
    assert store(client).get(KEY) == b"x" * size
    assert body.closed and body.closes == 1
    assert max(body.requests) <= READ_CHUNK_BYTES
    assert client.calls == [("get", {"Bucket": BUCKET, "Key": KEY})]


@pytest.mark.parametrize("length", [None, "3", True, -1, 0, MAX_DOCUMENT_BYTES + 1])
def test_get_rejects_bad_length_without_read_and_closes(length):
    client = FakeClient()
    body = FakeBody()
    client.get_result = response(200, Body=body, ContentLength=length)
    with pytest.raises(BlobStorageError):
        store(client).get(KEY)
    assert body.closed and body.closes == 1
    assert body.requests == []


@pytest.mark.parametrize("actual,declared", [(b"ab", 3), (b"abcd", 3), (b"", 1)])
def test_get_rejects_truncated_and_lying_lengths_and_closes(actual, declared):
    client = FakeClient()
    body = FakeBody(actual, step=1)
    client.get_result = response(200, Body=body, ContentLength=declared)
    with pytest.raises(BlobStorageError):
        store(client).get(KEY)
    assert body.closed and body.closes == 1


@pytest.mark.parametrize("status", [206, 301, 403, 500, None])
def test_get_closes_body_on_bad_status(status):
    client = FakeClient()
    body = FakeBody()
    client.get_result = response(status, Body=body, ContentLength=3)
    with pytest.raises(BlobStorageError):
        store(client).get(KEY)
    assert body.closed and body.closes == 1
    assert body.requests == []


@pytest.mark.parametrize("chunk", [None, "text", b"x" * 5])
def test_get_closes_on_non_bytes_or_overread_body(chunk):
    client = FakeClient()
    body = SimpleNamespace(read=lambda amount: chunk, close=Mock())
    client.get_result = response(200, Body=body, ContentLength=3)
    with pytest.raises(BlobStorageError):
        store(client).get(KEY)
    body.close.assert_called_once_with()


def test_get_closes_after_read_exception():
    client = FakeClient()
    body = FakeBody(error=TimeoutError("synthetic read timeout"))
    client.get_result = response(200, Body=body, ContentLength=3)
    with pytest.raises(TimeoutError):
        store(client).get(KEY)
    assert body.closed and body.closes == 1


@pytest.mark.parametrize("result", [None, {}, response(200, ContentLength=3)])
def test_get_rejects_missing_body(result):
    client = FakeClient()
    client.get_result = result
    with pytest.raises(BlobStorageError):
        store(client).get(KEY)


def test_get_transport_errors_propagate_without_fallback_or_deletion():
    client = FakeClient()
    client.get_error = OSError("synthetic unavailable")
    with pytest.raises(OSError):
        store(client).get(KEY)
    assert [name for name, _ in client.calls] == ["get"]


def test_delete_is_explicit_and_idempotent_for_an_absent_key():
    client = FakeClient()
    client.objects[KEY] = b"abc"
    adapter = store(client)
    assert adapter.delete(KEY) is None
    assert adapter.delete(KEY) is None
    assert client.objects == {}
    assert client.calls == [("delete", {"Bucket": BUCKET, "Key": KEY})] * 2


def test_delete_does_not_suppress_failures():
    client = FakeClient()
    client.delete_result = response(500)
    with pytest.raises(BlobStorageError):
        store(client).delete(KEY)
    client.delete_error = TimeoutError("synthetic delete timeout")
    with pytest.raises(TimeoutError):
        store(client).delete(KEY)
