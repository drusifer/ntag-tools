# tag-validator-service image. Build context is the ntag-tools repo root (it installs the sibling
# ntag_keys package): `make pkg-tag-validator` from the root does this.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    HOST=0.0.0.0 \
    SECRET_STORE_BACKEND=k3s

WORKDIR /build
COPY ntag_keys/pyproject.toml ntag_keys/
COPY ntag_keys/src/ ntag_keys/src/
COPY tag_validator_service/pyproject.toml tag_validator_service/README.md tag_validator_service/
COPY tag_validator_service/src/ tag_validator_service/src/

RUN pip install --no-cache-dir "./ntag_keys[k3s]" "./tag_validator_service[k3s,server]" && pip check \
    && rm -rf /build

RUN useradd -u 10001 -m appuser && mkdir -p /app && chown -R appuser:appuser /app
WORKDIR /app
USER appuser

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--worker-tmp-dir", "/tmp", "--access-logfile", "-", "tag_validator.api.app:create_app()"]
