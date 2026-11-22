# Record the resolved base and final image hashes in the trial receipt.
FROM aiwork-discovery-dotenv:phase61
COPY wheels /tmp/itsdangerous-wheels
RUN python -m pip install --no-index --no-cache-dir --find-links=/tmp/itsdangerous-wheels freezegun==1.5.5 python-dateutil==2.9.0.post0 six==1.17.0
ENV PYTHONDONTWRITEBYTECODE=1
