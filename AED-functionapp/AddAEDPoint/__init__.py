# Walidacja pól w strukturze zagnieżdżonej
        if not ("location" in data and "coordinates" in data["location"] and 
                "properties" in data and "user" in data["properties"] and 
                "address" in data["properties"]):
            logging.error(f"Missing required nested fields in data: {data}")
            return func.HttpResponse("Missing required fields in JSON structure", status_code=400)

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
            # Zmieniono status na 201, który oznacza "Created"
            return func.HttpResponse("Dodano punkt AED", status_code=201)
