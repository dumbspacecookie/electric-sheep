FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY electric_sheep ./electric_sheep

RUN pip install --no-cache-dir -e .

ENV ELECTRIC_SHEEP_TRANSPORT=http \
    ELECTRIC_SHEEP_HOST=0.0.0.0 \
    ELECTRIC_SHEEP_PORT=8080 \
    ELECTRIC_SHEEP_DB=/data/arcade.db \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8

EXPOSE 8080
VOLUME ["/data"]

CMD ["python", "-m", "electric_sheep.server"]
