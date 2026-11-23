
from fastapi import FastAPI

from backend.shared.database import check_database_connection
from backend.incidents.router import router as incidents_router

app = FastAPI(
    title="FixOps Backend API",
    description="Central API for incident management",
    version="1.0.0"
)


# Vérifier MongoDB au démarrage
@app.on_event("startup")
def startup_event():
    check_database_connection()


# Endpoint de santé du Backend
@app.get("/api/health", tags=["Health"])
def health_check():

    return {
        "status": "ok",
        "service": "FixOps Backend"
    }


# Enregistrer les routes Incidents
app.include_router(incidents_router)


# Page d'accueil
@app.get("/")
def root():

    return {
        "message": "Welcome to FixOps Backend"
    }
  