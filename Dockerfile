FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV POETRY_CACHE_DIR /usr/local/.cache/pypoetry

RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev

WORKDIR /code
COPY . .

RUN pip install poetry &&  \
    poetry install

CMD poetry run python3 wallet_server.py
