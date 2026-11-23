
from fastapi import APIRouter, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from backend.incidents.schemas import IncidentCreate
from backend.incidents.service import (
    create_or_update_incident,
    get_incidents,
    get_incident_by_id
)

router = APIRouter(
    prefix="/api/incidents",
    tags=["Incidents"]
)


# 1. Créer ou actualiser un incident
@router.post("")
def create_incident(data: IncidentCreate):

    incident, created = create_or_update_incident(data)

    response_status = (
        status.HTTP_201_CREATED
        if created
        else status.HTTP_200_OK
    )

    return JSONResponse(
        status_code=response_status,
        content=jsonable_encoder(incident)
    )


# 2. Lister et filtrer les incidents
@router.get("")
def list_incidents(
    service: str = None,
    type: str = None,
    status: str = None
):

    return get_incidents(
        service=service,
        type=type,
        status=status
    )


# 3. Récupérer un incident par son ID
@router.get("/{id}")
def read_incident(id: str):

    incident = get_incident_by_id(id)

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail="Incident not found"
        )

    return incident
