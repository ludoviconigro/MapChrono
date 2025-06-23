import threading
import webview
from app import app  # importa il tuo Flask app dal file app.py

def start_flask():
    # Avvia il server Flask (debug disabilitato per la produzione)
    app.run(debug=False)

if __name__ == '__main__':
    # Avvia Flask in un thread separato
    flask_thread = threading.Thread(target=start_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Apri la finestra desktop con WebView che punta all'app Flask
    webview.create_window("Visualizzatore Spostamenti", "http://127.0.0.1:5000")
    webview.start()
