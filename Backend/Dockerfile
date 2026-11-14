# One image for every program. The default command runs the API; the same image runs the poller
# (python poller.py) and the migrations (alembic upgrade head), so they can never drift apart.
#
# Two stages: the builder has uv and installs everything, the final stage starts from a clean base and
# copies in only /app (the code plus its .venv). uv itself and its download cache never reach the image.

# --- build stage ---
# pinned exactly: a bare "python:3.14" tag moves under you, and a rebuild months later would differ
FROM python:3.14.6-slim-bookworm AS builder

# the uv binary, copied out of its official image rather than installed with pip
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /uvx /bin/

WORKDIR /app

# compile .pyc files now so containers start faster; copy files out of the cache instead of hardlinking
# (the cache is a separate mount, below); use the image's python, never download another one
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

# dependencies first, on their own: this layer only rebuilds when pyproject.toml or uv.lock change,
# so editing a router reuses the cached install. the cache mount keeps uv's downloads outside every layer
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

# then the code. --no-dev leaves pytest out; --locked fails the build if uv.lock is out of date
COPY . ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# --- final stage ---
# the same base as the builder: the .venv's python links point at this image's /usr/local/bin/python
FROM python:3.14.6-slim-bookworm

WORKDIR /app

# never run as root: a bug in the app then can't touch the rest of the container
RUN useradd --create-home appuser

COPY --from=builder --chown=appuser:appuser /app /app

USER appuser

# no DATABASE_URL here: the container holds no data. it's given the postgres to use when it starts
# (--env-file, docker compose, ecs), which is what lets the same image run anywhere
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PORT=8000

EXPOSE 8000

# one server process per container: on ECS you scale by running more containers, not more workers in one.
# exec replaces the shell so fastapi receives SIGTERM directly and shuts down cleanly.
# --proxy-headers: behind a load balancer, trust its X-Forwarded-* headers so the app sees https and the real client
CMD ["/bin/sh", "-c", "exec fastapi run main.py --host 0.0.0.0 --port \"$PORT\" --proxy-headers --forwarded-allow-ips '*'"]
