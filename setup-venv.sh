#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

uv venv .venv
uv pip install -r requirements-dev.txt

# Seed config/ from config.example/ without overwriting existing files
mkdir -p config
for f in config.example/*; do
    target="config/$(basename "$f")"
    if [ ! -e "$target" ]; then
        cp "$f" "$target"
        echo "Created $target"
    fi
done
