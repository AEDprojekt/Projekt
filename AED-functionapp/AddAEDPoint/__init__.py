def main(req: func.HttpRequest) -> func.HttpResponse:
    credential = DefaultAzureCredential()
    key_vault_uri = os.environ["KEYVAULT_URI"]
    secret_client = SecretClient(vault_url=key_vault_uri, credential=credential)
    cosmos_conn_str = secret_client.get_secret("cosmosdb-conn-string").value

    client = pymongo.MongoClient(cosmos_conn_str)
    db = client["AEDdb"]
    collection = db["AEDpoints"]

    try:
        data = req.get_json()
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
        return func.HttpResponse("Dodano punkt AED", status_code=201)
    except Exception as e:
        return func.HttpResponse(str(e), status_code=400)
