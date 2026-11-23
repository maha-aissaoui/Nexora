
import os
from pymongo import MongoClient

# URL de connexion MongoDB
MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://localhost:27017/"
)

# Création de la connexion
client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=5000
)

# Sélection de la base de données
db = client["fixops"]

# Sélection de la collection
incidents_collection = db["incidents"]
incidents_collection.create_index(
    [
        ("host_id", 1),
        ("service", 1),
        ("type", 1)
    ],
    unique=True,
    partialFilterExpression={
        "status": "OPEN"
    }
)


def check_database_connection():
    """Vérifier la connexion à MongoDB."""
    client.admin.command("ping")
    return True
