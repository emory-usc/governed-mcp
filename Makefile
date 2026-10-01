.PHONY: install test eval verify run

install:
	uv sync --extra mcp

test:
	uv run pytest

eval:
	uv run governed eval

verify:
	uv run governed verify

run:
	uv run governed run --transport streamable-http --host 0.0.0.0 --port 8000
