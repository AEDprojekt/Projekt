import azure.functions as func
import logging
import pymongo
import os
import json
from bson import json_util
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        logging.info('GetAEDPoints function triggered.')

        credential = DefaultAzureCredential()
        key_vault_uri = os.environ["KEYVAULT_URI"]
        secret_client = SecretClient(vault_url=key_vault_uri, credential=credential)
        cosmos_conn_str = secret_client.get_secret("cosmosdb-conn-string").value
        logging.info("Successfully retrieved secret from Key Vault.")

        client = pymongo.MongoClient(cosmos_conn_str)
        db = client["AEDdb"]
        collection = db["AEDpoints"]
        logging.info("Successfully connected to the database.")

        all_docs = list(collection.find({}))
        clean_points = []
        for doc in all_docs:
            geometry = doc.get("geometry") or doc.get("location")
            if geometry and "coordinates" in geometry:
                clean_points.append({
                    "geometry": geometry,
                    "properties": doc.get("properties", {}) 
                })

        feature_collection = {"type": "FeatureCollection", "features": clean_points}
        response_body = json.dumps(feature_collection, default=json_util.default)

        logging.info(f"Successfully processed {len(clean_points)} documents.")

        return func.HttpResponse(
            body=response_body,
            status_code=200,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
    except Exception as e:
        # Ten blok złapie każdy błąd i go zarejestruje
        logging.exception(f"CRITICAL ERROR in GetAEDPoints: {e}")
        return func.HttpResponse(f"Internal Server Error: {str(e)}", status_code=500)
