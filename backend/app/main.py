from fastapi import FastAPI

from app.api import router
from app.pipeline.store import AnalysisStore

app = FastAPI()
app.state.analysis_store = AnalysisStore()
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
