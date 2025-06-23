from flask import Flask, render_template, request, jsonify, send_from_directory
import folium
import os
import tempfile
from datetime import datetime, timedelta
from folium.features import CustomIcon
import re
from geopy.distance import geodesic
import openrouteservice
from openrouteservice import convert
from io import BytesIO
from dateutil.parser import isoparse
import json
from zoneinfo import ZoneInfo  # gestione dei fusi orari con IANA TZ database

# API key for OpenRouteService
ORS_API_KEY = "5b3ce3597851110001cf6248c4ad10ed72764199ae869622c54bb23b"
client = openrouteservice.Client(key=ORS_API_KEY)

# Impostazioni Flask e fuso locale
app = Flask(__name__)
download_folder = os.path.join(os.getcwd(), 'downloads')
os.makedirs(download_folder, exist_ok=True)
app.config['DOWNLOAD_FOLDER'] = download_folder

# Fuso orario locale (Europe/Rome, CET/CEST)
LOCAL_TZ = ZoneInfo("Europe/Rome")


def aggiungi_offset(start_time_str, offset_minuti):
    try:
        dt = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        dt += timedelta(minutes=int(offset_minuti))
        return dt.isoformat()
    except:
        return start_time_str  # fallback


def estrai_coordinate(data):
    risultati = []
    for entry in data:
        if 'timelinePath' in entry:
            start_time = entry.get('startTime', '')
            for path_point in entry['timelinePath']:
                geo = path_point.get('point', '')
                if geo.startswith('geo:'):
                    lat, lon = map(float, geo.replace('geo:', '').split(','))
                    offset = path_point.get('durationMinutesOffsetFromStartTime')
                    time = aggiungi_offset(start_time, offset) if offset else start_time
                    risultati.append((time, lat, lon))
    # ordinamento per timestamp
    risultati.sort(key=lambda x: x[0])
    # filtro per rumore: ignora movimenti <30m in <60s
    filtrati = []
    last_time = None
    last_pos = None
    for t, lat, lon in risultati:
        if last_time and last_pos:
            delta_t = abs((datetime.fromisoformat(t) - datetime.fromisoformat(last_time)).total_seconds())
            delta_d = geodesic((lat, lon), last_pos).meters
            if delta_t < 60 and delta_d < 30:
                continue
        filtrati.append((t, lat, lon))
        last_time = t
        last_pos = (lat, lon)
    return filtrati


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/mappa_default')
def mappa_default():
    mappa = folium.Map(location=[41.9, 12.5], zoom_start=6)
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
    mappa.save(tmp_file.name)
    with open(tmp_file.name, 'r', encoding='utf-8') as f:
        html_content = f.read()
    os.unlink(tmp_file.name)
    return html_content


@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file:
        return "Nessun file selezionato", 400
    data = json.load(file)
    # Estrai i punti timelinePath
    risultati = estrai_coordinate(data)

    # Organizza per data
    per_date = {}
    for timestamp, lat, lon in risultati:
        giorno = timestamp.split('T')[0]
        per_date.setdefault(giorno, []).append((timestamp, lat, lon))

    # Estrai visite e attività raw
    visits_by_date = {}
    activities_by_date = {}
    for entry in data:
        date_key = entry.get('startTime', '').split('T')[0]
        if 'visit' in entry:
            visits_by_date.setdefault(date_key, []).append(entry)
        if 'activity' in entry:
            activities_by_date.setdefault(date_key, []).append(entry)

    # Memorizza in config per utilizzo successivo
    app.config['DATA'] = per_date
    app.config['VISITS'] = visits_by_date
    app.config['ACTIVITIES'] = activities_by_date

    # Restituisci elenco date disponibili
    return jsonify(sorted(per_date.keys()))


@app.route('/mappa', methods=['POST'])
def mappa():
    contenuto       = request.json
    giorno          = contenuto['data']
    orario_inizio   = contenuto.get('startTime') or f"{giorno}T00:00:00"
    orario_fine     = contenuto.get('endTime')   or f"{giorno}T23:59:59"
    usa_percorso_ors = contenuto.get('usaPercorsoORS', True)
    tipo_mappa       = contenuto.get('tipoMappa', 'osm')

    per_date = app.config.get('DATA', {})

    # Definizione intervallo temporale (aware datetimes, Europe/Rome)
    dt_start = isoparse(orario_inizio).replace(tzinfo=LOCAL_TZ)
    dt_end   = isoparse(orario_fine).replace(tzinfo=LOCAL_TZ)

    # Estrai punti filtrati da timelinePath, convertendo UTC -> locale
    punti = []
    for t_str, lat, lon in per_date.get(giorno, []):
        dt_utc   = isoparse(t_str)
        dt_local = dt_utc.astimezone(LOCAL_TZ)
        if dt_start <= dt_local <= dt_end:
            punti.append((dt_local.isoformat(), lat, lon))

    # Se non ci sono punti
    if not punti:
        mappa = folium.Map(location=[0, 0], zoom_start=2)
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
        mappa.save(tmp_file.name)
        with open(tmp_file.name, 'r', encoding='utf-8') as f:
            html_content = f.read()
        os.unlink(tmp_file.name)
        return jsonify({
            "mappa": html_content,
            "dettagli": [],
            "visits": [],
            "activities": []
        })

    # Ordina per timestamp
    punti.sort(key=lambda x: x[0])

    # Estrai visite e attività per la data e intervallo
    visits_raw = app.config.get('VISITS', {}).get(giorno, [])
    visits_filtered = []
    for v in visits_raw:
        try:
            dtv = isoparse(v['startTime']).astimezone(LOCAL_TZ)
            if dt_start <= dtv <= dt_end:
                visits_filtered.append(v)
        except:
            continue

    activities_raw = app.config.get('ACTIVITIES', {}).get(giorno, [])
    activities_filtered = []
    for a in activities_raw:
        try:
            dta = isoparse(a['startTime']).astimezone(LOCAL_TZ)
            if dt_start <= dta <= dt_end:
                activities_filtered.append(a)
        except:
            continue

    # Creazione mappa base
    first_lat, first_lon = punti[0][1], punti[0][2]
    if tipo_mappa == 'satellite':
        tiles_url = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
        attr = 'Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community'
    else:
        tiles_url = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
        attr = '© OpenStreetMap contributors'

    mappa = folium.Map(location=[first_lat, first_lon], zoom_start=16, max_zoom=50, tiles=tiles_url, attr=attr)
    tabella_dettagli = []

    # Aggiunge marker per timelinePath
    for i, (timestamp, lat, lon) in enumerate(punti):
        dt_local = isoparse(timestamp)
        data_str = dt_local.strftime('%d/%m/%Y')
        ora_str  = dt_local.strftime('%H:%M')
        colore   = 'green' if i == 0 else ('red' if i == len(punti) - 1 else 'blue')

        html = f'''
                <div style="position: relative; width: 30px; height: 30px; background: {colore};
                            border-radius: 50% 50% 50% 0; transform: rotate(-45deg);
                            border: 2px solid #000;">
                    <div style="position: absolute; top: 7px; left: 5px; transform: rotate(45deg);
                                color: white; font-weight: bold; font-size: 14px;">{i+1}</div>
                </div>
                '''        
        folium.Marker(
            location=[lat, lon],
            tooltip=f"{i+1})<br>Data: {data_str}<br>Ora: {ora_str}<br>Lat: {lat}<br>Lon: {lon}<br>Fonte: timelinePath",
            icon=folium.DivIcon(html=html)
        ).add_to(mappa)
        tabella_dettagli.append({"numero": i+1, "data": data_str, "ora": ora_str, "lat": lat, "lon": lon})

    # Percorso ORS o semplice polilinea
    if usa_percorso_ors and len(punti) >= 2:
        coords = [[lon, lat] for (_, lat, lon) in punti]
        route = client.directions(coordinates=coords, profile='driving-car', format='geojson')
        folium.GeoJson(route, name="Percorso ORS").add_to(mappa)
    else:
        for j in range(1, len(punti)):
            prev_lat, prev_lon = punti[j-1][1], punti[j-1][2]
            lat, lon = punti[j][1], punti[j][2]
            folium.PolyLine([(prev_lat, prev_lon), (lat, lon)], color='blue').add_to(mappa)

    # Salva HTML temporaneo
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
    mappa.save(tmp_file.name)
    with open(tmp_file.name, 'r', encoding='utf-8') as f:
        html_content = f.read()
    os.unlink(tmp_file.name)

    return jsonify({
        "mappa": html_content,
        "dettagli": tabella_dettagli,
        "visits": visits_filtered,
        "activities": activities_filtered
    })


@app.route('/salva_mappa', methods=['POST'])
def salva_mappa():
    dati = request.json
    mappa_html = dati.get('mappa_html')
    lista_html = dati.get('lista_html')
    nome_file = dati.get('nome_file', 'mappa_e_lista').strip()
    if not mappa_html or not lista_html or not nome_file:
        return jsonify({"error": "Dati mancanti"}), 400

    nome_file = re.sub(r'[^a-zA-Z0-9_\-]', '_', nome_file) + '.html'

    file_path = os.path.join(app.config['DOWNLOAD_FOLDER'], nome_file)

    html_completo = f"""
    <!DOCTYPE html>
    <html lang="it">
    <head><meta charset="UTF-8" /><title>Mappa Salvata</title></head>
    <body style="display:flex; margin:0; height:100vh; font-family:sans-serif;">
      <div style="flex:2; overflow:auto;">{mappa_html}</div>
      <div style="flex:1; border-left:1px solid #ddd; padding:10px; overflow:auto;">
        <h2>Elenco Tratti</h2>
        {lista_html}
      </div>
    </body>
    </html>
    """

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(html_completo)

    return jsonify({"download_url": f"/download/{nome_file}"})


@app.route('/download/<path:filename>')
def download_file(filename):
    return send_from_directory(app.config['DOWNLOAD_FOLDER'], filename, as_attachment=True)


if __name__ == '__main__':
    app.run(debug=False)
