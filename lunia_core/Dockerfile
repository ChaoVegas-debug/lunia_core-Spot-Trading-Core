FROM python:3.12-slim

WORKDIR /opt/app

ARG WHEELHOUSE=0
ARG PIP_INDEX_URL
ARG PIP_EXTRA_INDEX_URL
ARG PIP_TRUSTED_HOST
ENV PYTHONUNBUFFERED=1 \
  PIP_NO_CACHE_DIR=1 \
  PIP_DEFAULT_TIMEOUT=60

COPY requirements/ requirements/
COPY wheelhouse ./wheelhouse

RUN python -m pip install --upgrade pip \
  && if [ "$WHEELHOUSE" = "1" ] && [ -d wheelhouse ] && [ "$(ls -A wheelhouse)" ]; then \
  pip install --no-index --find-links=wheelhouse -r requirements/base.txt; \
  else \
  pip install -r requirements/base.txt; \
  fi

COPY . lunia_core
# --- I.4 Import fix: make `lunia_core.app.*` resolvable without duplicating code ---
RUN mkdir -p lunia_core \
 && (test -f lunia_core/__init__.py || : > lunia_core/__init__.py) \
 && ln -sfn ../app lunia_core/app
ENV PYTHONPATH=/opt/app

# I.4: Use port 8000 for dev/prod consistency (not 8080)
CMD ["python", "-m", "lunia_core.app.services.api.flask_app"]

# I.4: Health check for container orchestration
HEALTHCHECK --interval=5s --timeout=2s --retries=3 --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1
