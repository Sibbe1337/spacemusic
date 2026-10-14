"""Optional private EU R2 transport; no SDK construction or upload enablement.

The caller must provision an EU-jurisdiction bucket with public access disabled,
bucket-scoped credentials and a trusted, unmodified boto3-compatible client.
This module cannot attest bucket privacy, IAM, retention or residency settings
offline. It emits no ACLs, public URLs, presigned URLs or bucket-management calls.

R2 supports conditional PutObject; IfNoneMatch='*' is an atomic create, not a
HEAD-then-PUT check. Signing regions are auto, '' or us-east-1, NOT location
hints such as weur. The EU endpoint selects the jurisdiction. Sources:
https://developers.cloudflare.com/r2/api/s3/api/
https://developers.cloudflare.com/r2/reference/data-location/
https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/put_object.html
"""

import math
import re
from contextlib import closing
from pathlib import PurePosixPath
from uuid import UUID

from .database import CommitOutcomeUnknown

MAX_DOCUMENT_BYTES = 25 * 1024 * 1024
READ_CHUNK_BYTES = 64 * 1024
_EU_ENDPOINT = re.compile(r"https://[0-9a-f]{32}\.eu\.r2\.cloudflarestorage\.com")
_BUCKET = re.compile(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]")
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_KEY = re.compile(_UUID + "/" + _UUID)
_SIGNING_REGIONS = ("auto", "", "us-east-1")


class BlobStorageError(RuntimeError):
    """Storage did not supply a complete, valid acknowledgement or object."""


class BlobWriteNotConfirmed(CommitOutcomeUnknown):
    """Never compensate by deleting: the key may belong to an earlier write.

    This includes 409/412 responses: an SDK retry after a lost acknowledgement can
    observe an existing object. Inheriting the service's no-cleanup exception keeps
    both that object and pre-existing collision objects intact. Reconcile ownership
    and durable references before any retry or deletion.
    """


def _validate_key(key):
    if not isinstance(key, str) or _KEY.fullmatch(key) is None:
        raise ValueError("Expected a canonical workspace UUID/object UUID key")


def _expect_status(response, expected):
    if not isinstance(response, dict):
        raise BlobStorageError("Invalid storage response")
    metadata = response.get("ResponseMetadata")
    if not isinstance(metadata, dict) or metadata.get("HTTPStatusCode") != expected:
        raise BlobStorageError("Unexpected storage status")


class R2BlobStore:
    """Injected S3 client exposing only put-if-absent, bounded get and delete.

    Require path-style S3v4 with finite SDK timeouts (at most 60 seconds each).
    TLS verification is checked via botocore's private _endpoint.http_session._verify
    because boto3 has no public getter. Compatible clients must expose that setting;
    unknown transports fail closed. These checks do not sandbox custom event hooks,
    proxies, concurrent client mutation or a malicious injected implementation.
    """

    def __init__(self, client, *, endpoint_url, bucket, region_name="auto"):
        if not isinstance(endpoint_url, str) or not _EU_ENDPOINT.fullmatch(
            endpoint_url
        ):
            raise ValueError("Expected an account-specific HTTPS EU R2 endpoint")
        if not isinstance(bucket, str) or not _BUCKET.fullmatch(bucket):
            raise ValueError("Expected a plain R2 bucket name")
        if region_name not in _SIGNING_REGIONS:
            raise ValueError("Unsupported R2 signing region")
        self._client = client
        self._endpoint_url = endpoint_url
        self._bucket = bucket
        self._region_name = region_name
        self._check_client()

    def _check_client(self):
        meta = getattr(self._client, "meta", None)
        endpoint = getattr(self._client, "_endpoint", None)
        if (
            getattr(meta, "endpoint_url", None) != self._endpoint_url
            or getattr(endpoint, "host", None) != self._endpoint_url
            or getattr(meta, "region_name", None) != self._region_name
        ):
            raise ValueError(
                "Injected client endpoint/region does not match configuration"
            )
        verify = getattr(getattr(endpoint, "http_session", None), "_verify", None)
        if verify is not True and not (
            isinstance(verify, str) and PurePosixPath(verify).is_absolute()
        ):
            raise ValueError("TLS certificate verification must be enabled")
        config = getattr(meta, "config", None)
        s3 = getattr(config, "s3", None)
        if (
            getattr(config, "signature_version", None) != "s3v4"
            or not isinstance(s3, dict)
            or s3.get("addressing_style") != "path"
            or s3.get("use_accelerate_endpoint", False) is not False
            or s3.get("use_dualstack_endpoint", False) is not False
            or getattr(config, "use_dualstack_endpoint", False) not in (None, False)
            or getattr(config, "use_fips_endpoint", False) not in (None, False)
        ):
            raise ValueError("Require S3v4 and unmodified path-style endpoint routing")
        for name in ("connect_timeout", "read_timeout"):
            value = getattr(config, name, None)
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or not 0 < value <= 60
            ):
                raise ValueError("Require finite SDK timeouts between 0 and 60 seconds")
        if not all(
            callable(getattr(self._client, name, None))
            for name in ("put_object", "get_object", "delete_object")
        ):
            raise ValueError("Expected a boto3-compatible S3 client")

    def put_if_absent(self, key, value):
        _validate_key(key)
        if not isinstance(value, bytes) or not 0 < len(value) <= MAX_DOCUMENT_BYTES:
            raise ValueError("Expected 1 to 25 MiB of document bytes")
        self._check_client()
        try:
            response = self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=value,
                ContentLength=len(value),
                ContentType="application/octet-stream",
                CacheControl="no-store",
                IfNoneMatch="*",
            )
            _expect_status(response, 200)
        except Exception as exc:
            # No adapter retries, unconditional fallback, or destructive cleanup.
            raise BlobWriteNotConfirmed(
                "Object creation not confirmed; reconcile first"
            ) from exc

    def get(self, key):
        _validate_key(key)
        self._check_client()
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        body = response.get("Body") if isinstance(response, dict) else None
        if not callable(getattr(body, "close", None)):
            raise BlobStorageError("Missing closable storage body")
        with closing(body):
            _expect_status(response, 200)
            length = response.get("ContentLength")
            if type(length) is not int or not 0 < length <= MAX_DOCUMENT_BYTES:
                raise BlobStorageError("Invalid object length")
            content = bytearray()
            while True:
                # One extra byte detects lying lengths without an unbounded read.
                amount = min(READ_CHUNK_BYTES, length - len(content) + 1)
                chunk = body.read(amount)
                if not isinstance(chunk, bytes) or len(chunk) > amount:
                    raise BlobStorageError("Invalid storage body chunk")
                if not chunk:
                    if len(content) != length:
                        raise BlobStorageError("Truncated storage body")
                    return bytes(content)
                if len(content) + len(chunk) > length:
                    raise BlobStorageError("Object exceeds declared length")
                content.extend(chunk)

    def delete(self, key):
        """Explicit deletion only; authorization/reconciliation belongs to caller."""
        _validate_key(key)
        self._check_client()
        response = self._client.delete_object(Bucket=self._bucket, Key=key)
        _expect_status(response, 204)

    def delete_and_verify(self, key):
        self.delete(key)
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except Exception as error:
            result = getattr(error, "response", {})
            if result.get("ResponseMetadata", {}).get(
                "HTTPStatusCode"
            ) == 404 and result.get("Error", {}).get("Code") in (
                "NoSuchKey",
                "NotFound",
            ):
                return
            raise BlobStorageError("Object absence unconfirmed") from None
        body = response.get("Body")
        if callable(getattr(body, "close", None)):
            body.close()
        raise BlobStorageError("Object still exists after deletion")

    def workspace_keys(self, workspace):
        """Inventory the bucket, not DB references: failed uploads can be orphans."""
        self._check_client()
        prefix = str(UUID(str(workspace))) + "/"
        args = {"Bucket": self._bucket, "Prefix": prefix, "MaxKeys": 1000}
        keys, tokens = set(), set()
        for _ in range(100):
            result = self._client.list_objects_v2(**args)
            _expect_status(result, 200)
            for row in result.get("Contents", []):
                key = row.get("Key")
                _validate_key(key)
                if not key.startswith(prefix) or key in keys:
                    raise BlobStorageError("Invalid live object inventory")
                keys.add(key)
            if result.get("IsTruncated") is False:
                return sorted(keys)
            token = result.get("NextContinuationToken")
            if not isinstance(token, str) or not token or token in tokens:
                raise BlobStorageError("Incomplete live object inventory")
            tokens.add(token)
            args["ContinuationToken"] = token
        raise BlobStorageError("Live object inventory exceeds review limit")

    def erase_and_verify(self, workspace):
        for key in self.workspace_keys(workspace):
            self.delete_and_verify(key)
        if self.workspace_keys(workspace):
            raise BlobStorageError("Live objects remain")
