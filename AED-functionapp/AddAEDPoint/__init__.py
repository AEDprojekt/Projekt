import azure.functions as func
import logging
import pymongo
import os
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('AddAEDPoint function triggered.')

    # Obsługa CORS preflight (opcjonalnie, jeśli używasz CORS)
    if req.method == 'OPTIONS':
        return func.HttpResponse(
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )

    # Połączenie z bazą (przykład - dostosuj do siebie)
    # Możesz pobierać connection string z Key Vault lub z app settings
    cosmos_conn_str = os.environ.get("COSMOSDB_CONN_STRING")
    client = pymongo.MongoClient(cosmos_conn_str)
    db = client["AEDdb"]
    collection = db["AEDpoints"]

    # Parsowanie danych wejściowych
    try:
        data = req.get_json()
    except Exception as e:
        logging.error(f"Invalid JSON in request: {e}")
        return func.HttpResponse(
            "Invalid JSON body",
            status_code=400,
            headers={"Access-Control-Allow-Origin": "*"}
        )

    # Walidacja pól w strukturze zagnieżdżonej
    if not ("location" in data and "coordinates" in data["location"] and 
            "properties" in data and "user" in data["properties"] and 
            "address" in data["properties"]):
        logging.error(f"Missing required nested fields in data: {data}")
        return func.HttpResponse(
            "Missing required fields in JSON structure",
            status_code=400,
            headers={"Access-Control-Allow-Origin": "*"}
        )

    # Pobranie danych z poprawnej lokalizacji
    lon, lat = data["location"]["coordinates"]
    user = data["properties"]["user"]
    address = data["properties"]["address"]

    # Dodanie dokumentu do bazy
    try:
        collection.insert_one({
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            },
            "properties": {
                "added_by": user,
                "address": address
            }
        })
        logging.info("AED point added successfully.")
        return func.HttpResponse(
            "Dodano punkt AED",
            status_code=201,
            headers={"Access-Control-Allow-Origin": "*"}
        )
    except Exception as db_exc:
        logging.exception("Database insert failed")
        return func.HttpResponse(
            f"Database insert failed: {str(db_exc)}",
            status_code=500,
            headers={"Access-Control-Allow-Origin": "*"}
        )
