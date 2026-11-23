.. module:: itsdangerous.timed

Signing With Timestamps
=======================

If you want to expire signatures you can use the
:class:`TimestampSigner` class which adds timestamp information and
signs it. On unsigning you can validate that the timestamp is not older
than a given age.

.. code-block:: python

    from itsdangerous import TimestampSigner
    s = TimestampSigner('secret-key')
    string = s.sign('foo')

.. code-block:: python

    s.unsign(string, max_age=5)
    Traceback (most recent call last):
      ...
    itsdangerous.exc.SignatureExpired: Signature age 15 > 5 seconds

The ``max_age`` argument accepts an integer or float number of seconds,
or a :class:`datetime.timedelta` object. When a
:class:`datetime.timedelta` is provided, it is converted to seconds via
:meth:`~datetime.timedelta.total_seconds`, preserving fractional seconds.
An age equal to the limit is considered valid; an older age is expired.
A ``max_age`` of ``0`` means the signature must not have any age (age
must be exactly zero). A negative ``max_age`` causes immediate expiry
since any non-negative age exceeds the negative limit.

.. code-block:: python

    from datetime import timedelta
    s.unsign(string, max_age=timedelta(seconds=5))
    s.unsign(string, max_age=timedelta(minutes=1))

.. autoclass:: TimestampSigner
    :members:

.. autoclass:: TimedSerializer
    :members:
