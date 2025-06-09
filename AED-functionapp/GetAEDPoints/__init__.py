import azure.functions as func
import logging
import pymongo
import os
import json
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('GetAEDPoints function triggered.')
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

        # Pobranie wszystkich punktów AED
        features = []
        for doc in collection.find():
            # Walidacja dokumentu
            if "geometry" not in doc or "coordinates" not in doc["geometry"]:
                logging.warning(f"Invalid document structure: {doc.get('_id')}")
                continue
            features.append({
                "type": "Feature",
                "geometry": doc["geometry"],
                "properties": doc.get("properties", {})
            })

        logging.info(f"Returned {len(features)} AED points.")
        return func.HttpResponse(
            json.dumps({ "type": "FeatureCollection", "features": features }),
            mimetype="application/json",
            status_code=200
        )
    except Exception as e:
        logging.exception("Function GetAEDPoints failed with exception")
        return func.HttpResponse(f"Internal server error: {str(e)}", status_code=500)
