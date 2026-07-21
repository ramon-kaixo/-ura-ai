import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

from core.mochila._state import build_state
from core.mochila.guardian_middleware import GuardianMiddleware, init_guardian
from core.mochila.routes import create_api_router

log = logging.getLogger(__name__)


def create_app() -> FastAPI:
    load_dotenv(Path("~/URA/.env").expanduser())

    state = build_state()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_guardian()
        await state.scheduler.start_loop()
        yield
        await state.scheduler.stop_loop()
        for p in state.providers.values():
            if hasattr(p, "__aenter__"):
                await p.__aexit__(None, None, None)

    app = FastAPI(title="Mochila Middleware", version="0.7.0", lifespan=lifespan)
    app.add_middleware(GuardianMiddleware)
    app.include_router(create_api_router(state))
    return app


app = create_app()
