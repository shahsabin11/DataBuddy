# Image baked into every E2B sandbox. No secrets. No network at runtime
# (FastAPI sets allow_internet_access=False on create).
FROM e2bdev/code-interpreter:latest

USER root

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY databuddy_sandbox /opt/databuddy_sandbox
ENV PYTHONPATH="/opt:${PYTHONPATH}" \
    MPLBACKEND=Agg \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1

RUN mkdir -p /input /output \
    && chmod 555 /input \
    && chmod 777 /output

WORKDIR /home/user
