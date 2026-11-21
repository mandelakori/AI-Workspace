FROM aiwork-phase61-httpx:local
COPY wheels /opt/wheels
COPY requirements.lock /opt/requirements.lock
RUN python -m pip install --no-index --find-links=/opt/wheels --require-hashes -r /opt/requirements.lock
COPY upstream /opt/upstream
RUN python -m pip install --no-index --no-deps --no-build-isolation /opt/upstream
ENV PYTHONPATH=/work/src IPYTHONDIR=/tmp/ipython
