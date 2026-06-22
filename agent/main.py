"""API HTTP de l'agent, déployée sur Cloud Run."""
from __future__ import annotations

import os

from fastapi import FastAPI
from pydantic import BaseModel

import agent

app = FastAPI(title="Agent sinistres")


class Demande(BaseModel):
    num_police: str
    id_sinistre: str


@app.get("/")
def sante() -> dict:
    return {"status": "ok"}


@app.post("/instruire")
def instruire(d: Demande) -> dict:
    decision = agent.instruire(d.num_police, d.id_sinistre)
    return {"num_police": d.num_police, "id_sinistre": d.id_sinistre, "decision": decision}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
