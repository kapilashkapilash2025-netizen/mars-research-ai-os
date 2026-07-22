FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip wheel --wheel-dir /wheels .

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PORT=8080 \
    AREOGRAPH_API_HOST=0.0.0.0 \
    AREOGRAPH_DATA_DIR=/tmp/areograph-missions

RUN useradd --create-home --uid 10001 areograph
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels

USER areograph
EXPOSE 8080
CMD ["python", "-m", "mars_ai_os.mission.api"]
