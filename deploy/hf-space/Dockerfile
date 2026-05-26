# Hugging Face Space (Docker SDK) image for the hosted arcade.
# Installs Electric Sheep straight from the source repo and serves the MCP
# endpoint over streamable HTTP on the port HF expects (7860). The corpus
# lives on ephemeral disk and is mirrored to a HF Dataset (set as Space
# secrets — see deploy/hf-space/README.md). Factory-rebuild the Space to
# pull a newer commit.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# HF Spaces run containers as a non-root user (uid 1000). Mirror that.
RUN useradd -m -u 1000 user
USER user

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    ELECTRIC_SHEEP_TRANSPORT=http \
    ELECTRIC_SHEEP_HOST=0.0.0.0 \
    ELECTRIC_SHEEP_PORT=7860 \
    ELECTRIC_SHEEP_DB=/home/user/data/arcade.db \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8

WORKDIR /home/user/app

RUN pip install --no-cache-dir --user \
    "electric-sheep[hf] @ git+https://github.com/dumbspacecookie/electric-sheep@main"

EXPOSE 7860

CMD ["python", "-m", "electric_sheep.server"]
