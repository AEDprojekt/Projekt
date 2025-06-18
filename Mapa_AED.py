import folium
from folium.plugins import MarkerCluster
from folium.plugins import HeatMap
from branca.element import MacroElement
from jinja2 import Template
import datetime
import branca
import geopandas as gpd


try:
    wroclaw_gdf = gpd.read_file("tubylamojasciezka/wroclaw-max.geojson")
    pop_gdf = gpd.read_file("tubylamojasciezka/wroclaw_population_dzielnice_gestosc.geojson")

    #Naprawianie geometrii, inaczej nie pozwoli wczytać
    wroclaw_gdf['geometry'] = wroclaw_gdf.geometry.buffer(0)
    pop_gdf['geometry'] = pop_gdf.geometry.buffer(0)

    #Przycinanie danych gestosci zaludnienia do granic miasta i wyznaczanie centroidów gridów dla propozycji
    pop_gdf = gpd.overlay(pop_gdf, wroclaw_gdf, how='intersection', keep_geom_type=False)
    pop_gdf_meter = pop_gdf.to_crs(epsg=2180)
    pop_gdf_meter['centroid'] = pop_gdf_meter.geometry.centroid
    centroids_gdf = gpd.GeoDataFrame(
        pop_gdf_meter[['LUD_NA_KM2']],
        geometry=pop_gdf_meter['centroid'],
        crs=2180
    ).rename(columns={'LUD_NA_KM2': 'population_density'}).to_crs(epsg=4326)

    #Proponuje 48 (po jednym na osiedle) nowych AED na podstawie centroidów
    proposed_aed_gdf = centroids_gdf[centroids_gdf['population_density'] > 0].sort_values(
        'population_density', ascending=False
    ).head(48)
    liczba_propozycji = len(proposed_aed_gdf)

except Exception as e:
    print(f"Błąd podczas wczytywania lokalnych plików GeoJSON: {e}")
    print("Warstwy granic i propozycji nie zostaną dodane.")
    wroclaw_gdf = None
    proposed_aed_gdf = None
    liczba_propozycji = 0

#Konfiguruje azure maps
azure_maps_url = (
    "https://atlas.microsoft.com/map/tile?api-version=2.0"
    "&tilesetId=microsoft.base.road"
    "&zoom={z}&x={x}&y={y}"
    "&subscription-key=8z6DK9luDBh5lnICmusZfbnmj7mkJXZbLxsLTffZwyp1snLbvZBwJQQJ99BEAC5RqLJTNnCJAAAgAZMP20gS"
)

m = folium.Map(
    location=[51.1079, 17.0385],
    zoom_start=12,
    tiles=None,
    control_scale=True
)

#Dodatkowe biblioteki dla ładnych ikonek AED
m.get_root().header.add_child(folium.Element(
    "<link rel='stylesheet' href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css'>"))
m.get_root().header.add_child(folium.Element(
    "<link rel='stylesheet' href='https://cdnjs.cloudflare.com/ajax/libs/leaflet.awesome-markers/2.0.2/leaflet.awesome-markers.css'>"))
m.get_root().header.add_child(folium.Element(
    "<script src='https://cdnjs.cloudflare.com/ajax/libs/leaflet.awesome-markers/2.0.2/leaflet.awesome-markers.js'></script>"))

#Dodaje warstwy Azure Maps
folium.TileLayer(
    tiles=azure_maps_url,
    attr='Azure Maps',
    name='Azure Maps Road',
    overlay=False,
    control=True,
    max_zoom=19,
    min_zoom=10
).add_to(m)

#Klastry istniejących AED
marker_cluster_aed = MarkerCluster(
    name='Istniejące AED',
    options={'showCoverageOnHover': True, 'spiderfyDistanceMultiplier': 2, 'maxClusterRadius': 40}
).add_to(m)

#Tworzenie pustej heatmapy
heat_map_layer = HeatMap([], name='Heatmapa AED', radius=18, blur=12, min_opacity=0.3).add_to(m)

#Proponowane AED i warstwa granic
if proposed_aed_gdf is not None:
    proposed_aed_group = folium.FeatureGroup(name='Proponowane AED', show=True).add_to(m)
    for idx, row in proposed_aed_gdf.iterrows():
        if row.geometry is not None:
            folium.Marker(
                [row.geometry.y, row.geometry.x],
                icon=folium.Icon(color='red', icon='star', prefix='fa'),
                tooltip=f"Proponowana lokalizacja AED",
            ).add_to(proposed_aed_group)

if wroclaw_gdf is not None:
    folium.GeoJson(
        wroclaw_gdf.geometry,
        name='Granice Wrocławia',
        style_function=lambda x: {'fillColor': '#3388ff', 'color': '#3388ff', 'weight': 2, 'fillOpacity': 0.15}
    ).add_to(m)


#Kontrolka z tytułem mapy
class TitleControl(MacroElement):
    def __init__(self, title):
        super().__init__()
        self._name = 'TitleControl'
        self.title = title
        self._template = Template(u"""
        {% macro script(this, kwargs) %}
            var titleDiv = document.createElement('div');
            titleDiv.innerHTML = `<h3 style="margin:0; font-family: sans-serif; font-size: 22px; color: #333; text-shadow: 1px 1px 2px white;">{{this.title}}</h3>`;
            Object.assign(titleDiv.style, {
                position: 'fixed',
                top: '10px',
                left: '50%',
                transform: 'translateX(-50%)',
                zIndex: '1001',
                backgroundColor: 'rgba(255, 255, 255, 0.75)',
                padding: '5px 15px',
                borderRadius: '5px',
                pointerEvents: 'none'
            });
            document.body.appendChild(titleDiv);
        {% endmacro %}
        """)


m.add_child(TitleControl('Mapa AED we Wrocławiu'))

#Panel statystyk na górze
stats_html = (
    f"<b>Liczba AED:</b> <span id='aed_count'>Ładowanie...</span> &nbsp;|&nbsp; "
    f"<b>Proponowane lokalizacje:</b> {liczba_propozycji} &nbsp;|&nbsp; "
    f"<b>Ostatnia aktualizacja:</b> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
)


class StatsControl(MacroElement):
    def __init__(self, html, position='topright'):
        super().__init__()
        self._name = 'StatsControl'
        self.html = html
        self.position = position
        self._template = Template(u"""
        {% macro script(this, kwargs) %}
        var statsControl = L.control({position: '{{this.position}}'});
        statsControl.onAdd = function(map) {
            var div = L.DomUtil.create('div', 'leaflet-control leaflet-bar');
            div.style.background = 'rgba(255, 255, 255, 0.93)';
            div.style.padding = '6px 12px';
            div.style.fontSize = '13px';
            div.style.borderRadius = '5px';
            div.style.boxShadow = '0 2px 6px rgba(0,0,0,0.13)';
            div.style.whiteSpace = 'nowrap';
            div.innerHTML = `{{this.html|safe}}`;
            return div;
        };
        statsControl.addTo({{this._parent.get_name()}});
        {% endmacro %}
        """)


m.add_child(StatsControl(stats_html, position='topright'))


#Klasa do dynamicznego ładowania danych przez łączenie z azure
class DynamicLoader(MacroElement):
    def __init__(self, marker_cluster, heatmap):
        super().__init__()
        self._name = 'DynamicLoader'
        self.marker_cluster = marker_cluster
        self.heatmap = heatmap
        self._template = Template(u"""
        {% macro script(this, kwargs) %}
            document.addEventListener("DOMContentLoaded", function() {
                const getPointsUrl = 'https://aed-functionapp.azurewebsites.net/api/GetAEDPoints';
                const markerCluster = {{this.marker_cluster.get_name()}};
                const heatmap = {{this.heatmap.get_name()}};

                fetch(getPointsUrl)
                    .then(response => response.ok ? response.json() : Promise.reject(response))
                    .then(data => {
                        const featureCollection = typeof data === 'string' ? JSON.parse(data) : data;
                        if (featureCollection && featureCollection.type === 'FeatureCollection' && Array.isArray(featureCollection.features)) {
                            const points = featureCollection.features;
                            document.getElementById('aed_count').textContent = points.length;

                            var heatData = [];
                            points.forEach(point => {
                                const geometry = point.geometry || point.location;
                                if (geometry && geometry.coordinates && geometry.coordinates.length === 2) {
                                    const lat = geometry.coordinates[1];
                                    const lon = geometry.coordinates[0];
                                    heatData.push([lat, lon]);

                                    var popupContent = `<b>Lokalizacja:</b> ${lat.toFixed(5)}, ${lon.toFixed(5)}`;
                                    const props = point.properties || {};
                                    if (props.address) popupContent += `<br><b>Adres:</b> ${props.address}`;
                                    if (props.added_by) popupContent += `<br><b>Dodane przez:</b> ${props.added_by}`;
                                    if (props.osiedle) popupContent += `<br><b>Osiedle:</b> ${props.osiedle}`;

                                    var icon = L.AwesomeMarkers.icon({
                                        icon: 'heart', prefix: 'fa', markerColor: 'green', iconColor: 'white'
                                    });

                                    var marker = L.marker([lat, lon], { icon: icon });
                                    marker.bindPopup(popupContent);
                                    markerCluster.addLayer(marker);
                                }
                            });
                            heatmap.setLatLngs(heatData);
                        } else {
                            throw new Error('Otrzymane dane nie są poprawnym obiektem GeoJSON FeatureCollection!');
                        }
                    })
                    .catch(error => {
                        console.error('Błąd podczas ładowania punktów AED:', error);
                        document.getElementById('aed_count').textContent = "Błąd";
                    });
            });
        {% endmacro %}
        """)


m.add_child(DynamicLoader(marker_cluster_aed, heat_map_layer))


#Klasa przycisku dodawania nowego AED
class AddAEDControl(MacroElement):
    def __init__(self, position='topleft'):
        super().__init__()
        self._name = 'AddAEDControl'
        self.position = position
        self._template = Template(u"""
        {% macro script(this, kwargs) %}
        var addAEDControl = L.control({position: '{{this.position}}'});
        addAEDControl.onAdd = function(map) {
            var div = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
            div.innerHTML = '<button id="addAedButton" style="background-color: #007bff; color: white; padding: 8px 12px; border: none; border-radius: 5px; cursor: pointer; font-size: 14px;">Dodaj Nowy AED</button>';
            div.style.padding = '5px';
            div.style.backgroundColor = 'rgba(255, 255, 255, 0.9)';
            div.style.borderRadius = '5px';
            div.style.boxShadow = '0 2px 6px rgba(0,0,0,0.13)';
            return div;
        };
        addAEDControl.addTo({{this._parent.get_name()}});

        var map = {{this._parent.get_name()}};
        var addAedButton = document.getElementById('addAedButton');
        var clickHandler;
        var newMarker = null;
        var isWaitingForSecondClick = false;

        addAedButton.onclick = function() {
            if (addAedButton.innerText === 'Anuluj dodawanie') {
                map.off('click', clickHandler);
                if (newMarker) { map.removeLayer(newMarker); }
                newMarker = null;
                addAedButton.innerText = 'Dodaj Nowy AED';
                addAedButton.style.backgroundColor = '#007bff';
                isWaitingForSecondClick = false;
                showMessage('Dodawanie AED anulowane.');
                return;
            }

            showMessage('Pierwsze kliknięcie: wskaż lokalizację. Drugie: zatwierdź i otwórz formularz.');
            addAedButton.innerText = 'Anuluj dodawanie';
            addAedButton.style.backgroundColor = '#dc3545';

            clickHandler = function(e) {
                if (!isWaitingForSecondClick) {
                    var lat = e.latlng.lat;
                    var lon = e.latlng.lng;
                    if (newMarker) {
                        newMarker.setLatLng(e.latlng);
                    } else {
                        newMarker = L.marker([lat, lon], {
                            icon: L.icon({
                                iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-orange.png',
                                shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                                iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41]
                            })
                        }).addTo(map);
                    }
                    showMessage('Lokalizacja wybrana. Kliknij ponownie, aby zatwierdzić lub w inne miejsce, by poprawić.');
                    isWaitingForSecondClick = true;
                } else {
                    var lat = e.latlng.lat;
                    var lon = e.latlng.lng;
                    if (newMarker) { newMarker.setLatLng(e.latlng); }
                    const markerForForm = newMarker;
                    newMarker = null;
                    showForm(lat, lon, markerForForm);
                    map.off('click', clickHandler);
                    addAedButton.innerText = 'Dodaj Nowy AED';
                    addAedButton.style.backgroundColor = '#007bff';
                    isWaitingForSecondClick = false;
                }
            };
            map.on('click', clickHandler);
        };

        function showMessage(message) {
            var msgDiv = document.getElementById('mapMessage');
            if (!msgDiv) {
                msgDiv = document.createElement('div');
                msgDiv.id = 'mapMessage';
                // ### ZMIANA: Pozycja komunikatu na dole ekranu ###
                Object.assign(msgDiv.style, {
                    position: 'absolute', bottom: '20px', left: '50%', transform: 'translateX(-50%)',
                    backgroundColor: 'rgba(0, 0, 0, 0.7)', color: 'white', padding: '10px 15px',
                    borderRadius: '5px', zIndex: '1000', textAlign: 'center'
                });
                document.body.appendChild(msgDiv);
            }
            msgDiv.innerText = message;
            msgDiv.style.display = 'block';
            setTimeout(() => { if(msgDiv) { msgDiv.style.display = 'none'; } }, 4000);
        }

        function showForm(lat, lon, markerToRemove) {
            var formHtml = `
                <div id="aedFormContainer" style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background-color: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); z-index: 1001; max-width: 400px; width: 90%; font-family: sans-serif;">
                    <h3 style="margin-top: 0; color: #333;">Dodaj Nowy Defibrylator AED</h3>
                    <p style="font-size: 14px; color: #555;">Lokalizacja: ${lat.toFixed(5)}, ${lon.toFixed(5)}</p>
                    <div style="margin-bottom: 15px;">
                        <label for="user" style="display: block; margin-bottom: 5px; font-weight: bold; color: #444;">Twoje imię / Nazwa:</label>
                        <input type="text" id="user" placeholder="Np. Jan Kowalski" required style="width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box;">
                    </div>
                    <div style="margin-bottom: 20px;">
                        <label for="address" style="display: block; margin-bottom: 5px; font-weight: bold; color: #444;">Dokładny adres / Opis lokalizacji:</label>
                        <input type="text" id="address" placeholder="Np. ul. Ratuszowa 1, wejście od strony rynku" required style="width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box;">
                    </div>
                    <div style="display: flex; justify-content: space-between; gap: 10px;">
                        <button id="submitAed" style="background-color: #28a745; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; flex-grow: 1; font-size: 16px;">Dodaj</button>
                        <button id="cancelAed" style="background-color: #6c757d; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; flex-grow: 1; font-size: 16px;">Anuluj</button>
                    </div>
                </div>
            `;
            document.body.insertAdjacentHTML('beforeend', formHtml);

            document.getElementById('submitAed').onclick = function() {
                var user = document.getElementById('user').value;
                var address = document.getElementById('address').value;
                if (!user || !address) {
                    showMessage('Wszystkie pola są wymagane!');
                    return;
                }
                document.getElementById('aedFormContainer').remove();
                if (markerToRemove) { map.removeLayer(markerToRemove); }
                sendAedData(lat, lon, user, address);
            };

            document.getElementById('cancelAed').onclick = function() {
                document.getElementById('aedFormContainer').remove();
                if (markerToRemove) { map.removeLayer(markerToRemove); }
                showMessage('Dodawanie AED anulowane.');
            };
        }

        async function sendAedData(lat, lon, user, address) {
            const azureFunctionUrl = 'https://aed-functionapp.azurewebsites.net/api/AddAEDPoint';
            const newAedData = { "lat": lat, "lon": lon, "user": user, "address": address };

            try {
                const response = await fetch(azureFunctionUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(newAedData)
                });
                if (response.ok) {
                    showMessage('AED dodany pomyślnie! Nowy punkt pojawi się po odświeżeniu mapy.');
                } else {
                    const errorText = await response.text();
                    showMessage('Błąd podczas dodawania AED: ' + response.status + ' ' + errorText);
                }
            } catch (error) {
                showMessage('Wystąpił błąd sieci: ' + error.message);
            }
        }
        {% endmacro %}
        """)


m.add_child(AddAEDControl(position='topleft'))

#Legenda
folium.LayerControl(position='bottomright', collapsed=False).add_to(m)

#Zapisanie mapy
m.save("tubylamojasciezka/mapa_aed_wroclaw.html")
print("Mapa zapisana.")