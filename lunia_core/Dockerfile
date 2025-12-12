FROM python:3.12-slim

WORKDIR /opt/app

ARG WHEELHOUSE=0
ARG PIP_INDEX_URL
ARG PIP_EXTRA_INDEX_URL
ARG PIP_TRUSTED_HOST
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=60

COPY requirements/base.txt requirements/base.txt
COPY wheelhouse ./wheelhouse

RUN python -m pip install --upgrade pip \
    && if [ "$WHEELHOUSE" = "1" ] && [ -d wheelhouse ] && [ "$(ls -A wheelhouse)" ]; then \
         pip install --no-index --find-links=wheelhouse -r requirements/base.txt; \
       else \
         pip install -r requirements/base.txt; \
       fi

COPY . .

CMD ["python", "-m", "flask", "--app", "app.services.api.flask_app", "run", "--host=0.0.0.0", "--port=8080"]
