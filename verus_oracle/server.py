"""FastAPI surface for the web tool. Optional install: `pip install -e .[server]`."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .llm import LLMClient
from .pipeline import score_source

app = FastAPI(title="verus-oracle")

_INDEX_HTML = (Path(__file__).parent / "web" / "index.html").read_text()
_FETCH_MAX_BYTES = 200_000
_FETCH_TIMEOUT_S = 10.0


class ScoreRequest(BaseModel):
    source: str
    offline: bool = False


class FetchRequest(BaseModel):
    url: str


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return _INDEX_HTML


@app.post("/score")
async def score(payload: ScoreRequest) -> dict:
    client = None if payload.offline else LLMClient()
    verdict = score_source(payload.source, client=client, offline=payload.offline)
    return verdict.to_dict()


@app.post("/score/upload")
async def score_upload(file: UploadFile, offline: bool = False) -> dict:
    if not file.filename or not file.filename.endswith(".rs"):
        raise HTTPException(status_code=400, detail="expected a .rs file")
    source = (await file.read()).decode("utf-8", errors="replace")
    client = None if offline else LLMClient()
    verdict = score_source(source, path=file.filename, client=client, offline=offline)
    return verdict.to_dict()


def _to_raw_github(url: str) -> tuple[str, str]:
    """Validate a GitHub URL and return (raw_url, display_filename).

    Accepts:
      https://github.com/<owner>/<repo>/blob/<ref>/<path>
      https://raw.githubusercontent.com/<owner>/<repo>/<ref>/<path>
    """
    p = urlparse(url)
    if p.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="url must be http(s)")
    host = p.netloc.lower()
    parts = [seg for seg in p.path.split("/") if seg]

    if host == "github.com":
        # /<owner>/<repo>/blob/<ref>/<path...>
        if len(parts) < 5 or parts[2] != "blob":
            raise HTTPException(
                status_code=400,
                detail="expected github.com/<owner>/<repo>/blob/<ref>/<path>",
            )
        owner, repo, _, ref, *path = parts
        raw = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{'/'.join(path)}"
        return raw, path[-1]

    if host == "raw.githubusercontent.com":
        if len(parts) < 4:
            raise HTTPException(status_code=400, detail="raw URL is missing path")
        return url, parts[-1]

    raise HTTPException(
        status_code=400,
        detail="only github.com and raw.githubusercontent.com are allowed",
    )


@app.post("/fetch")
async def fetch(payload: FetchRequest) -> dict:
    raw_url, filename = _to_raw_github(payload.url)
    if not filename.endswith(".rs"):
        raise HTTPException(status_code=400, detail="expected a .rs file path")
    try:
        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT_S, follow_redirects=True) as c:
            r = await c.get(raw_url)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"fetch failed: {e}") from e
    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=f"github returned {r.status_code}")
    body = r.content[: _FETCH_MAX_BYTES + 1]
    if len(body) > _FETCH_MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"file exceeds {_FETCH_MAX_BYTES} byte cap")
    return {"source": body.decode("utf-8", errors="replace"), "filename": filename, "url": raw_url}
