# Build context: repo-rot (mappen som inneholder togpuls/-pakken).
# Bygg lokalt fra repo-rot:  docker build -f togpuls/Dockerfile -t togpuls .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY togpuls/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY togpuls ./togpuls

EXPOSE 8000
ENV TOGPULS_HOST=0.0.0.0 TOGPULS_PORT=8000

CMD ["python", "-m", "togpuls.serve"]
