FROM python:3.11-slim

WORKDIR /opt/app

COPY requirements/base.txt requirements/base.txt
RUN pip install --no-cache-dir -r requirements/base.txt

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "flask", "--app", "app.services.api.flask_app", "run", "--host=0.0.0.0", "--port=8080"]
