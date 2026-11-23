
from fastapi import FastAPI
from agent.actions import router as actions_router

app = FastAPI(title="Nexora Agent", version="1.0")

app.include_router(actions_router)


@app.get("/agent/health")
def agent_health():
    return {
        "agent": "nexora-agent",
        "status": "running"
    }
