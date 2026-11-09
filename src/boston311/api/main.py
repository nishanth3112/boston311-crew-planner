from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from boston311.api.routes import router
from boston311.config import ROOT

DIST = ROOT / "web" / "dist"  # built by `npm run build`; in development Vite serves the app

app = FastAPI(title="Boston 311 Crew Planner")
app.include_router(router)


@app.get("/{path:path}", include_in_schema=False)
def web_app(path: str) -> FileResponse:
    """The built web app: its files as they are, and index.html for the app's own routes
    (/plan, /scenarios, /ask), so a page refresh works."""
    # a null byte would make resolve() raise; no real file name has one
    if path == "api" or path.startswith("api/") or "\x00" in path:
        raise HTTPException(status_code=404)
    root = DIST.resolve()
    file = (root / path).resolve()
    # resolve() follows "..", so a path that leaves web/dist is never served
    if path and file.is_file() and file.is_relative_to(root):
        return FileResponse(file)
    if not (root / "index.html").is_file():
        raise HTTPException(status_code=404)
    return FileResponse(root / "index.html")
