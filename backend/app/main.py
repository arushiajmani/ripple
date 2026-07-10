from fastapi import FastAPI

from app.api import router
from app.api.errors import register_exception_handlers
from app.pipeline.store import AnalysisStore

app = FastAPI()
app.state.analysis_store = AnalysisStore()
app.include_router(router)
register_exception_handlers(app)


@app.get("/health")
def health():
    return {"status": "ok"}
