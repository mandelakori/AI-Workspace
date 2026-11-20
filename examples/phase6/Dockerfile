FROM aiwork-engineering:phase3
COPY wheels /wheels
RUN python -m pip install --no-index --find-links=/wheels pytest==8.3.5 flit_core==3.12.0 click==8.3.2
ENV PYTHONPATH=/work/src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
