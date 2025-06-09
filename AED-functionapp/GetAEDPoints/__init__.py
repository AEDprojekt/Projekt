import azure.functions as func
import logging
import pymongo
import os
import json
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from pymongo.errors import PyMongoError

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    try:
        # Autoryzacja i pobieranie sekretów
        credential = DefaultAzureCredential()
        key_vault_uri = os.environ["KEYVAULT_URI"]
        secret_client = SecretClient(vault_url=key_vault_uri, credential=credential)
        
        cosmos_conn_str = secret_client.get_secret("cosmosdb-conn-string").value
        logging.info("Successfully retrieved Cosmos DB connection string")

        # Połączenie z Cosmos DB
        client = pymongo.MongoClient(cosmos_conn_str)
        db = client["AEDdb"]
        collection = db["AEDpoints"]
        logging.info("Connected to Cosmos DB")

        # Pobieranie danych i budowanie GeoJSON
        features = []
        for doc in collection.find():
            if "geometry" not in doc or "coordinates" not in doc["geometry"]:
                logging.warning("Invalid document structure: %s", doc.get("_id"))
                continue
                
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": doc["geometry"].get("type", "Point"),
                    "coordinates": doc["geometry"]["coordinates"]
                },
                "properties": {
                    "id": str(doc.get("_id")),
                    "address": doc.get("properties", {}).get("address"),
                    "added_by": doc.get("properties", {}).get("added_by"),
                    "timestamp": doc.get("properties", {}).get("timestamp")
                }
            })

        return func.HttpResponse(
            json.dumps({
                "type": "FeatureCollection",
                "features": features
            }),
            mimetype="application/json",
            status_code=200
        )

    except KeyError as ke:
        logging.error("Missing environment variable: %s", str(ke))
        return func.HttpResponse(
            f"Configuration error: {str(ke)}",
            status_code=500
        )
    except PyMongoError as mongo_err:
        logging.error("MongoDB error: %s", str(mongo_err))
        return func.HttpResponse(
            f"Database error: {str(mongo_err)}",
            status_code=500
        )
    except Exception as e:
        logging.error("Unexpected error: %s", str(e), exc_info=True)
        return func.HttpResponse(
            f"Internal server error: {str(e)}",
            status_code=500
        )
