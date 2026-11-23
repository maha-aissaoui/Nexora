
from datetime import datetime, timezone
from uuid import uuid4

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from backend.shared.database import incidents_collection
from backend.incidents.schemas import IncidentCreate


def create_or_update_incident(data: IncidentCreate):

    now = datetime.now(timezone.utc)

    # Identifier un incident ouvert identique
    query = {
        "host_id": data.host_id,
        "service": data.service,
        "type": data.type,
        "status": "OPEN"
    }

    # Chercher un incident existant
    existing = incidents_collection.find_one(query)

    if existing:

        # Actualiser l'incident
        incidents_collection.update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "last_seen_at": now,
                    "observed_status": data.observed_status
                },
                "$addToSet": {
                    "observations": {
                        "at": data.observed_at,
                        "state": data.observed_status,
                        "details": data.details
                    }
                }
            }
        )

        updated = incidents_collection.find_one(
            {"_id": existing["_id"]}
        )

        return format_incident(updated), False

    # Créer un nouvel incident
    incident = {
        "incident_id": f"INC-{uuid4().hex[:8].upper()}",
        "host_id": data.host_id,
        "service": data.service,
        "type": data.type,
        "observed_status": data.observed_status,
        "status": "OPEN",
        "observations": [
            {
                "at": data.observed_at,
                "state": data.observed_status,
                "details": data.details
            }
        ],
        "created_at": now,
        "last_seen_at": now
    }

    try:
        result = incidents_collection.insert_one(incident)

        incident["_id"] = result.inserted_id

        return format_incident(incident), True

    except DuplicateKeyError:
        # Une autre requête a créé le même incident
        existing = incidents_collection.find_one(query)

        if existing is None:
            raise

        incidents_collection.update_one(
            {"_id": existing["_id"]},
            {
                "$set": {"last_seen_at": now},
                "$addToSet": {
                    "observations": {
                        "at": data.observed_at,
                        "state": data.observed_status,
                        "details": data.details
                    }
                }
            }
        )

        updated = incidents_collection.find_one(
            {"_id": existing["_id"]}
        )

        return format_incident(updated), False


def format_incident(incident):

    incident["id"] = str(incident.pop("_id"))

    return incident


def get_incidents(service=None, type=None, status=None):

    filters = {}

    if service:
        filters["service"] = service

    if type:
        filters["type"] = type

    if status:
        filters["status"] = status

    incidents = incidents_collection.find(filters).sort(
        "created_at", -1
    )

    return [format_incident(i) for i in incidents]


def get_incident_by_id(incident_id):

    if not ObjectId.is_valid(incident_id):
        return None

    incident = incidents_collection.find_one(
        {"_id": ObjectId(incident_id)}
    )

    if incident is None:
        return None

    return format_incident(incident)
