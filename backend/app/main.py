import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import router
from .settings import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    stop = asyncio.Event()
    from .scheduler import run_scheduler
    task = asyncio.create_task(run_scheduler(stop, lambda reminder_id: asyncio.sleep(0)))
    app.state.scheduler_task = task
    yield
    stop.set()
    await task

app = FastAPI(title="BHASHALEARN Deadline Reminders", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_credentials=True,
                   allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["*"])
app.include_router(router)

@app.get("/health")
def health():
    return {"status": "ok", "feature": "deadline-reminders"}

