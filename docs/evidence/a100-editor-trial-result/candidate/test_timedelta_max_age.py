"""Tests for datetime.timedelta support in max_age arguments."""

from __future__ import annotations

import datetime
import time

import pytest

from itsdangerous import TimestampSigner
from itsdangerous import TimedSerializer
from itsdangerous.exc import SignatureExpired
from itsdangerous.url_safe import URLSafeTimedSerializer


class TestTimestampSignerTimedelta:
    """Tests for TimestampSigner with timedelta max_age."""

    def test_timedelta_valid_signature(self) -> None:
        signer = TimestampSigner(secret_key="test-key")
        signed = signer.sign(b"hello")
        result = signer.unsign(signed, max_age=datetime.timedelta(seconds=10))
        assert result == b"hello"

    def test_timedelta_expired(self) -> None:
        signer = TimestampSigner(secret_key="test-key")
        signed = signer.sign(b"hello")
        time.sleep(1.1)
        with pytest.raises(SignatureExpired):
            signer.unsign(signed, max_age=datetime.timedelta(seconds=1))

    def test_timedelta_zero_duration(self) -> None:
        signer = TimestampSigner(secret_key="test-key")
        signed = signer.sign(b"hello")
        with pytest.raises(SignatureExpired):
            signer.unsign(signed, max_age=datetime.timedelta(seconds=0))

    def test_timedelta_negative_duration(self) -> None:
        signer = TimestampSigner(secret_key="test-key")
        signed = signer.sign(b"hello")
        with pytest.raises(SignatureExpired):
            signer.unsign(signed, max_age=datetime.timedelta(seconds=-1))

    def test_timedelta_fractional_seconds(self) -> None:
        signer = TimestampSigner(secret_key="test-key")
        signed = signer.sign(b"hello")
        result = signer.unsign(signed, max_age=datetime.timedelta(milliseconds=500))
        assert result == b"hello"

    def test_timedelta_exact_boundary(self) -> None:
        signer = TimestampSigner(secret_key="test-key")
        signed = signer.sign(b"hello")
        result = signer.unsign(signed, max_age=datetime.timedelta(seconds=3600))
        assert result == b"hello"
    def test_timedelta_future_timestamp_invalid(self) -> None:
        signer = TimestampSigner(secret_key="test-key")
        future_ts = int(time.time()) + 10000
        from itsdangerous.encoding import base64_encode, int_to_bytes

        ts_bytes = base64_encode(int_to_bytes(future_ts))
        sep = signer.sep.encode()
        value = b"hello"
        to_sign = value + sep + ts_bytes
        sig = signer.get_signature(to_sign)
        signed = to_sign + sep + sig

        with pytest.raises(SignatureExpired):
            signer.unsign(signed, max_age=datetime.timedelta(seconds=10))

    def test_timedelta_return_timestamp(self) -> None:
        signer = TimestampSigner(secret_key="test-key")
        signed = signer.sign(b"hello")
        result, ts = signer.unsign(
            signed, max_age=datetime.timedelta(seconds=10), return_timestamp=True
        )
        assert result == b"hello"
        assert ts.tzinfo is not None

    def test_timedelta_validate_true(self) -> None:
        signer = TimestampSigner(secret_key="test-key")
        signed = signer.sign(b"hello")
        assert signer.validate(signed, max_age=datetime.timedelta(seconds=10)) is True

    def test_timedelta_validate_expired(self) -> None:
        signer = TimestampSigner(secret_key="test-key")
        signed = signer.sign(b"hello")
        time.sleep(1.1)
        assert signer.validate(signed, max_age=datetime.timedelta(seconds=1)) is False

    def test_timedelta_preserves_int_behavior(self) -> None:
        signer = TimestampSigner(secret_key="test-key")
        signed = signer.sign(b"hello")
        result = signer.unsign(signed, max_age=10)
        assert result == b"hello"

    def test_timedelta_preserves_none_behavior(self) -> None:
        signer = TimestampSigner(secret_key="test-key")
        signed = signer.sign(b"hello")
        result = signer.unsign(signed, max_age=None)
        assert result == b"hello"

    def test_timedelta_float_seconds(self) -> None:
        signer = TimestampSigner(secret_key="test-key")
        signed = signer.sign(b"hello")
        result = signer.unsign(signed, max_age=10.5)
        assert result == b"hello"

class TestTimedSerializerTimedelta:
    """Tests for TimedSerializer with timedelta max_age."""

    def test_timedelta_valid(self) -> None:
        ser = TimedSerializer(secret_key="test-key")
        signed = ser.dumps("hello")
        result = ser.loads(signed, max_age=datetime.timedelta(seconds=10))
        assert result == "hello"

    def test_timedelta_expired(self) -> None:
        ser = TimedSerializer(secret_key="test-key")
        signed = ser.dumps("hello")
        time.sleep(1.1)
        with pytest.raises(SignatureExpired):
            ser.loads(signed, max_age=datetime.timedelta(seconds=1))

    def test_timedelta_loads_unsafe_valid(self) -> None:
        ser = TimedSerializer(secret_key="test-key")
        signed = ser.dumps("hello")
        valid, payload = ser.loads_unsafe(
            signed, max_age=datetime.timedelta(seconds=10)
        )
        assert valid is True
        assert payload == "hello"

    def test_timedelta_loads_unsafe_expired(self) -> None:
        ser = TimedSerializer(secret_key="test-key")
        signed = ser.dumps("hello")
        time.sleep(1.1)
        valid, payload = ser.loads_unsafe(
            signed, max_age=datetime.timedelta(seconds=1)
        )
        assert valid is False

    def test_timedelta_loads_unsafe_bad_signature(self) -> None:
        ser = TimedSerializer(secret_key="test-key")
        valid, payload = ser.loads_unsafe(
            "invalid-signature", max_age=datetime.timedelta(seconds=10)
        )
        assert valid is False

    def test_timedelta_fractional(self) -> None:
        ser = TimedSerializer(secret_key="test-key")
        signed = ser.dumps("hello")
        result = ser.loads(signed, max_age=datetime.timedelta(milliseconds=500))
        assert result == "hello"

    def test_timedelta_zero(self) -> None:
        ser = TimedSerializer(secret_key="test-key")
        signed = ser.dumps("hello")
        with pytest.raises(SignatureExpired):
            ser.loads(signed, max_age=datetime.timedelta(seconds=0))

class TestURLSafeTimedSerializerTimedelta:
    """Tests for URLSafeTimedSerializer with timedelta max_age."""

    def test_timedelta_valid(self) -> None:
        ser = URLSafeTimedSerializer(secret_key="test-key")
        signed = ser.dumps("hello")
        result = ser.loads(signed, max_age=datetime.timedelta(seconds=10))
        assert result == "hello"

    def test_timedelta_expired(self) -> None:
        ser = URLSafeTimedSerializer(secret_key="test-key")
        signed = ser.dumps("hello")
        time.sleep(1.1)
        with pytest.raises(SignatureExpired):
            ser.loads(signed, max_age=datetime.timedelta(seconds=1))

    def test_timedelta_loads_unsafe_valid(self) -> None:
        ser = URLSafeTimedSerializer(secret_key="test-key")
        signed = ser.dumps("hello")
        valid, payload = ser.loads_unsafe(
            signed, max_age=datetime.timedelta(seconds=10)
        )
        assert valid is True
        assert payload == "hello"

    def test_timedelta_loads_unsafe_expired(self) -> None:
        ser = URLSafeTimedSerializer(secret_key="test-key")
        signed = ser.dumps("hello")
        time.sleep(1.1)
        valid, payload = ser.loads_unsafe(
            signed, max_age=datetime.timedelta(seconds=1)
        )
        assert valid is False

    def test_timedelta_fractional(self) -> None:
        ser = URLSafeTimedSerializer(secret_key="test-key")
        signed = ser.dumps("hello")
        result = ser.loads(signed, max_age=datetime.timedelta(milliseconds=500))
        assert result == "hello"

    def test_timedelta_negative(self) -> None:
        ser = URLSafeTimedSerializer(secret_key="test-key")
        signed = ser.dumps("hello")
        with pytest.raises(SignatureExpired):
            ser.loads(signed, max_age=datetime.timedelta(seconds=-1))

    def test_timedelta_key_rotation(self) -> None:
        """Key rotation should work with timedelta max_age."""
        ser = TimedSerializer(secret_key=["key1", "key2"])
        signed = ser.dumps("hello")
        result = ser.loads(signed, max_age=datetime.timedelta(seconds=10))
        assert result == "hello"

    def test_timedelta_key_rotation_second_key(self) -> None:
        """Key rotation with second key should work with timedelta."""
        ser = TimedSerializer(secret_key=["key1", "key2"])
        signer = TimestampSigner(secret_key="key2")
        from itsdangerous.encoding import base64_encode, int_to_bytes

        ts = signer.get_timestamp()
        ts_bytes = base64_encode(int_to_bytes(ts))
        sep = signer.sep.encode()
        value = ser.dumps("hello").encode()
        to_sign = value + sep + ts_bytes
        sig = signer.get_signature(to_sign)
        signed = (to_sign + sep + sig).decode()

        result = ser.loads(signed, max_age=datetime.timedelta(seconds=10))
        assert result == "hello"