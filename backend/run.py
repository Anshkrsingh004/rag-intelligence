"""
Dev entry point for the RAG Intelligence backend.

    python run.py            # start on http://localhost:8000
    WARM_UP_MODELS=1 python run.py   # preload ML models at startup (slower boot, fast first query)
"""

from __future__ import annotations

import uvicorn

from app.config import settings


def main() -> None:
    print("=" * 60)
    print("  RAG Intelligence — Backend")
    print(f"  Version       : {settings.version}")
    print(f"  Fast model    : {settings.model_fast}")
    print(f"  Quality model : {settings.model_quality}")
    print("  API base      : http://localhost:8000/api")
    print("  Health        : http://localhost:8000/api/health")
    print(f"  Parallelism   : ThreadPoolExecutor ({settings.max_workers} workers)")
    print("=" * 60)
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
