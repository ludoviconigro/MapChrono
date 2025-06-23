# MapChrono

## 📌 Descrizione

MapChrono è uno strumento di analisi e visualizzazione dei dati di localizzazione generati da dispositivi iOS tramite l'app Google Maps. A partire dal file `location-history.json` esportato localmente dall’app (post-Giugno 2024), il software consente di:

- analizzare i movimenti giornalieri su mappa interattiva;
- visualizzare in dettaglio spostamenti e permanenze (visit e activity);
- esportare i risultati in formato `.html` per fini forensi, investigativi o didattici.

Il programma può essere eseguito sia in **modalità web** (via browser) che in **modalità desktop** (app standalone), ed è progettato per funzionare in locale, senza invio di dati a terzi.

## 🧩 Requisiti

- Python ≥ 3.8
- Sistema operativo testato: macOS (compatibile anche con Windows/Linux)
- Architettura supportata: M1/M2 (Apple Silicon), Intel

## 📦 Dipendenze

Installabili tramite `pip`:

```bash
pip install -r requirements.txt
```

Contenuto del file `requirements.txt`:
- Flask
- folium
- geopy
- pywebview
- openrouteservice
- python-dateutil

## 🚀 Esecuzione

### 1. Preparazione ambiente (consigliato uso di virtualenv)

```bash
gti clone https://github.com/ludoviconigro/MapChrono
cd MapChrono
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Modalità Web (via browser)

```bash
python app.py
```

Apri il browser e vai su: [http://127.0.0.1:5000](http://127.0.0.1:5000)

### 3. Modalità Desktop (senza browser)

```bash
python app_desktop.py
```

Si aprirà una finestra nativa con l’interfaccia del programma.

## 🗂️ Utilizzo

1. **Carica il file** `location-history.json` esportato da Google Maps su iOS.
2. **Seleziona la data** e, se desiderato, un intervallo orario.
3. **Visualizza la mappa** con i tracciati degli spostamenti.
4. **Analizza la timeline** testuale generata.
5. **Esporta** la mappa + timeline in formato `.html`.

## 📁 Esportazione file JSON

Per ottenere il file da analizzare:
- Apri Google Maps su iPhone → "I tuoi spostamenti"
- Menu (⋮) → “Impostazioni posizione e privacy”
- Tocca “Esporta i dati degli Spostamenti”  
(Il file generato sarà `location-history.json`)

## 🛡️ Privacy e sicurezza

- Nessun dato viene inviato su Internet: tutto avviene in locale.
- I file `.html` esportati contengono solo dati statici e sono privi di tracciamenti.
- È responsabilità dell'utente proteggere i file generati in conformità al GDPR e alla catena di custodia forense.


## 📝 Licenza

Questo progetto è distribuito sotto licenza MIT.
