import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agents.laia_agent import LaiaAgent
from core.safety import Safety
from core.action_executor import ActionExecutor
from core.screen_reader import ScreenReader
from core.explorer import Explorer

logger = logging.getLogger(__name__)

app = FastAPI(title="Laia API", version="1.0.0")

safety = Safety()
executor = ActionExecutor(safety)
reader = ScreenReader(use_vlm=True)
explorer = Explorer(executor, reader)
agent = LaiaAgent()


class Command(BaseModel):
    text: str


class MacroCreate(BaseModel):
    name: str
    goal: str


class MacroRun(BaseModel):
    name: str


class FrigateQuery(BaseModel):
    label: str = "person"
    after: int | None = None
    before: int | None = None
    zone: str | None = None


class PlanRequest(BaseModel):
    goal: str


@app.post("/command")
def execute_command(cmd: Command) -> dict:
    success = agent.process_command(cmd.text)
    return {"success": success, "message": "Comando ejecutado" if success else "No entendido"}


@app.post("/plan")
def plan_task(req: PlanRequest) -> dict:
    plan = agent.planner.plan(req.goal)
    return {"goal": req.goal, "plan": plan}


@app.post("/plan/execute")
def execute_plan(req: PlanRequest) -> dict:
    success = agent.execute_planned_task(req.goal)
    return {"success": success, "goal": req.goal}


@app.post("/macro/learn")
def learn_macro(m: MacroCreate) -> dict:
    success = explorer.learn_macro(m.name, m.goal)
    return {"success": success, "name": m.name}


@app.post("/macro/run")
def run_macro(m: MacroRun) -> dict:
    success = explorer.run_macro(m.name)
    return {"success": success, "name": m.name}


@app.get("/macro/list")
def list_macros() -> list[dict]:
    macros_dir = Path(explorer.macros_dir)
    if not macros_dir.exists():
        return []
    return [{"name": f.stem} for f in macros_dir.glob("*.json")]


@app.post("/frigate/query")
def frigate_query(q: FrigateQuery) -> dict:
    try:
        data = agent.query_frigate_events(
            label=q.label, after=q.after, before=q.before, zone=q.zone
        )
        return {"success": True, "events": len(data), "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "panic": safety.is_panic(),
        "governance_threshold": agent.governance.risk_threshold,
    }
