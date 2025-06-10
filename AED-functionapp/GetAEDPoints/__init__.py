import azure.functions as func
import logging
import pymongo
import os
import json
from bson import json_util
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('GetAEDPoints function triggered.')

    try:
        credential = DefaultAzureCredential() #Pobieramy sekrety z Key Vault ---
        key_vault_uri = os.environ["KEYVAULT_URI"]
        secret_client = SecretClient(vault_url=key_vault_uri, credential=credential)
        cosmos_conn_str = secret_client.get_secret("cosmosdb-conn-string").value

        #Połączenie z bazą
        client = pymongo.MongoClient(cosmos_conn_str)
        db = client["AEDdb"]
        collection = db["AEDpoints"]

        
        all_docs = list(collection.find({})) #Pobieramy wszystkich dokumentów
        
        #unifikowanie punktów z geometry i location
        clean_points = []
        for doc in all_docs:
            geometry = doc.get("geometry") or doc.get("location") #Ujednolicamy pole z geometrią
            
            # Dodajemy do listy tylko te punkty, które mają poprawne współrzędne
            if geometry and "coordinates" in geometry and len(geometry["coordinates"]) == 2:
                clean_point = {
                    "geometry": geometry, #Zawsze zwracamy współrzędne w polu "geometry"
                    "properties": doc.get("properties", {}) #Zawsze zwracamy współrzędne w polu "geometry"
                }
                clean_points.append(clean_point)
        
        response_body = json.dumps(clean_points, default=json_util.default) # Konwertujemy na JSON naszą czystą zunifikowaną listę punktów

        logging.info(f"Successfully retrieved and cleaned {len(clean_points)} documents.")

        return func.HttpResponse(
            body=response_body,
            status_code=200,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
    except Exception as e:
        logging.exception(f"An exception occurred in GetAEDPoints: {e}")
        return func.HttpResponse("Internal Server Error", status_code=500)
