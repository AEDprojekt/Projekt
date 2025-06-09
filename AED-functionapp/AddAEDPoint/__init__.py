import azure.functions as func
import logging
import pymongo
import os
import json
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('AddAEDPoint function triggered.')
    try:
        # Pobranie poświadczeń i sekretów
        credential = DefaultAzureCredential()
        key_vault_uri = os.environ["KEYVAULT_URI"]
        secret_client = SecretClient(vault_url=key_vault_uri, credential=credential)
        cosmos_conn_str = secret_client.get_secret("cosmosdb-conn-string").value

        # Połączenie z bazą
        client = pymongo.MongoClient(cosmos_conn_str)
        db = client["AEDdb"]
        collection = db["AEDpoints"]

        # Parsowanie danych wejściowych
        try:
            data = req.get_json()
            logging.info(f"Received data: {data}")
        except Exception as e:
            logging.error(f"Invalid JSON in request: {e}")
            return func.HttpResponse("Invalid JSON body", status_code=400)

        # Walidacja wymaganych pól
        required_fields = ["lat", "lon", "user", "address"]
        if not all(field in data for field in required_fields):
            logging.error(f"Missing required fields in data: {data}")
            return func.HttpResponse("Missing required fields", status_code=400)

        # Dodanie dokumentu do bazy
        collection.insert_one({
            "geometry": {
                "type": "Point",
                "coordinates": [data["lon"], data["lat"]]
            },
            "properties": {
                "added_by": data["user"],
                "address": data["address"]
            }
        })
        logging.info("AED point added successfully.")
        return func.HttpResponse("Dodano punkt AED", status_code=201)

    except Exception as e:
        logging.exception("Function AddAEDPoint failed with exception")
        return func.HttpResponse(f"Internal server error: {str(e)}", status_code=500)
