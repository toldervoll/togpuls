"""Run togpuls's HTTP API + widget via uvicorn."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "togpuls.api.app:app",
        host=os.environ.get("TOGPULS_HOST", "0.0.0.0"),
        port=int(os.environ.get("TOGPULS_PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    main()
