import azure.functions as func
import logging
import pymongo
import os
import json
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        credential = DefaultAzureCredential()
        key_vault_uri = os.environ["KEYVAULT_URI"]
        secret_client = SecretClient(vault_url=key_vault_uri, credential=credential)
        cosmos_conn_str = secret_client.get_secret("cosmosdb-conn-string").value

        client = pymongo.MongoClient(cosmos_conn_str)
        db = client["AEDdb"]
        collection = db["AEDpoints"]

        features = []
        for doc in collection.find():
            features.append({
                "type": "Feature",
                "geometry": doc["geometry"],
                "properties": doc.get("properties", {})
            })

        return func.HttpResponse(
            json.dumps({ "type": "FeatureCollection", "features": features }),
            mimetype="application/json",
            status_code=200
        )
    except Exception as e:
        logging.exception("Function failed with exception")
        return func.HttpResponse(str(e), status_code=500)
