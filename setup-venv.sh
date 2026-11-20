#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

uv venv .venv
# --python: HA core sets UV_SYSTEM_PYTHON, which would otherwise install into the system interpreter
uv pip install --python .venv/bin/python -r requirements-dev.txt

# Seed config/ from config.example/ without overwriting existing files
mkdir -p config
for f in config.example/*; do
    target="config/$(basename "$f")"
    if [ ! -e "$target" ]; then
        cp "$f" "$target"
        echo "Created $target"
    fi
done
