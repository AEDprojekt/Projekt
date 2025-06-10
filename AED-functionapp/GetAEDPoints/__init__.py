import azure.functions as func
import logging
import pymongo
import os
import json
from bson import json_util

# Importy potrzebne do obsługi Key Vault
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('GetAEDPoints function triggered to fetch all points.')

    try:
        # --- POCZĄTEK BLOKU KEY VAULT ---
        # Uwierzytelnienie za pomocą Tożsamości Zarządzanej aplikacji (Managed Identity)
        credential = DefaultAzureCredential()
        
        # Pobranie URI Twojego Key Vault ze Zmiennych Środowiskowych (Ustawień Aplikacji)
        key_vault_uri = os.environ["KEYVAULT_URI"]
        
        # Połączenie z Key Vault i pobranie sekretu
        secret_client = SecretClient(vault_url=key_vault_uri, credential=credential)
        cosmos_conn_str = secret_client.get_secret("cosmosdb-conn-string").value
        # --- KONIEC BLOKU KEY VAULT ---

        # Połączenie z bazą danych przy użyciu pobranego sekretu
        client = pymongo.MongoClient(cosmos_conn_str)
        db = client["AEDdb"]
        collection = db["AEDpoints"]

        # Pobierz wszystkie dokumenty z kolekcji
        all_points = list(collection.find({}))
        
        # Użyj json_util do poprawnego przekonwertowania danych z MongoDB (w tym ObjectId) na JSON
        response_body = json.dumps(all_points, default=json_util.default)

        logging.info(f"Successfully retrieved {len(all_points)} documents.")

        return func.HttpResponse(
            body=response_body,
            status_code=200,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*" # Zapewnienie CORS
            }
        )
    except Exception as e:
        # Zapisz szczegółowy błąd w logach Azure
        logging.exception(f"An exception occurred in GetAEDPoints: {e}")
        # Zwróć generyczny błąd do klienta
        return func.HttpResponse("Internal Server Error", status_code=500)
