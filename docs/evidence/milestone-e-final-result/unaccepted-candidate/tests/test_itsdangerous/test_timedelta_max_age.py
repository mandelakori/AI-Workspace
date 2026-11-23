"""Tests for datetime.timedelta support in max_age arguments."""

from datetime import timedelta
from unittest.mock import patch

import pytest

from itsdangerous import TimestampSigner, TimedSerializer, URLSafeTimedSerializer
from itsdangerous.exc import BadSignature, SignatureExpired


def _make_signer(key="secret-key"):
    return TimestampSigner(key)


def _make_serializer(key="secret-key"):
    return TimedSerializer(key)


def _make_urlsafe_serializer(key="secret-key"):
    return URLSafeTimedSerializer(key)


class TestTimestampSignerTimedelta:
    def test_timedelta_valid(self):
        signer = _make_signer()
        with patch.object(signer, "get_timestamp", return_value=1000):
            s = signer.sign(b"hello")
        with patch.object(signer, "get_timestamp", return_value=1000):
            result = signer.unsign(s, max_age=timedelta(seconds=10))
        assert result == b"hello"

    def test_timedelta_expired(self):
        signer = _make_signer()
        with patch.object(signer, "get_timestamp", return_value=1000):
            s = signer.sign(b"hello")
        with patch.object(signer, "get_timestamp", return_value=1010):
            with pytest.raises(SignatureExpired):
                signer.unsign(s, max_age=timedelta(seconds=5))
    def test_timedelta_exact_boundary(self):
        signer = _make_signer()
        s = signer.sign(b"hello")
        with patch.object(signer, "get_timestamp", return_value=1005):
            result = signer.unsign(s, max_age=timedelta(seconds=5))
        assert result == b"hello"

    def test_timedelta_fractional_seconds(self):
        signer = _make_signer()
        s = signer.sign(b"hello")
        with patch.object(signer, "get_timestamp", return_value=1003):
            result = signer.unsign(s, max_age=timedelta(seconds=3, milliseconds=500))
        assert result == b"hello"
        with patch.object(signer, "get_timestamp", return_value=1003):
            with pytest.raises(SignatureExpired):
                signer.unsign(s, max_age=timedelta(seconds=3, milliseconds=500))

    def test_timedelta_negative(self):
        signer = _make_signer()
        s = signer.sign(b"hello")
        with patch.object(signer, "get_timestamp", return_value=1000):
            with pytest.raises(SignatureExpired):
                signer.unsign(s, max_age=timedelta(seconds=-1))

    def test_timedelta_zero(self):
        signer = _make_signer()
        s = signer.sign(b"hello")
        with patch.object(signer, "get_timestamp", return_value=1000):
            result = signer.unsign(s, max_age=timedelta(seconds=0))
        assert result == b"hello"
        with patch.object(signer, "get_timestamp", return_value=1001):
            with pytest.raises(SignatureExpired):
                signer.unsign(s, max_age=timedelta(seconds=0))
    def test_timedelta_future_timestamp(self):
        signer = _make_signer()
        s = signer.sign(b"hello")
        with patch.object(signer, "get_timestamp", return_value=999):
            with pytest.raises(SignatureExpired):
                signer.unsign(s, max_age=timedelta(seconds=10))

    def test_validate_with_timedelta(self):
        signer = _make_signer()
        s = signer.sign(b"hello")
        with patch.object(signer, "get_timestamp", return_value=1000):
            assert signer.validate(s, max_age=timedelta(seconds=10)) is True
        with patch.object(signer, "get_timestamp", return_value=1010):
            assert signer.validate(s, max_age=timedelta(seconds=5)) is False

    def test_serializer_timedelta(self):
        ser = _make_serializer()
        s = ser.dumps("hello")
        with patch.object(ser, "get_timestamp", return_value=1000):
            result = ser.loads(s, max_age=timedelta(seconds=10))
        assert result == "hello"

    def test_urlsafe_timedelta(self):
        ser = _make_urlsafe_serializer()
        s = ser.dumps("hello")
        with patch.object(ser, "get_timestamp", return_value=1000):
            result = ser.loads(s, max_age=timedelta(seconds=10))
        assert result == "hello"

    def test_urlsafe_unsafe_timedelta(self):
        ser = _make_urlsafe_serializer()
        s = ser.dumps("hello")
        with patch.object(ser, "get_timestamp", return_value=1000):
            valid, payload = ser.loads_unsafe(s, max_age=timedelta(seconds=10))
        assert valid is True
        assert payload == "hello"

    def test_integer_limit_preserved(self):
        signer = _make_signer()
        s = signer.sign(b"hello")
        with patch.object(signer, "get_timestamp", return_value=1000):
            result = signer.unsign(s, max_age=10)
        assert result == b"hello"
        with patch.object(signer, "get_timestamp", return_value=1010):
            with pytest.raises(SignatureExpired):
                signer.unsign(s, max_age=10)

    def test_none_limit_preserved(self):
        signer = _make_signer()
        s = signer.sign(b"hello")
        with patch.object(signer, "get_timestamp", return_value=1000000):
            result = signer.unsign(s, max_age=None)
        assert result == b"hello"

    def test_unsupported_type_rejected(self):
        signer = _make_signer()
        s = signer.sign(b"hello")
        with pytest.raises(TypeError):
            signer.unsign(s, max_age="10")

    def test_large_integer_limit(self):
        signer = _make_signer()
        s = signer.sign(b"hello")
        with patch.object(signer, "get_timestamp", return_value=1000):
            result = signer.unsign(s, max_age=2**53 + 1)
        assert result == b"hello"