import sys
import requests
import json
import time
import threading
import webbrowser
from urllib.parse import quote
import re
import base64
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw
import pystray

# Importa a nova biblioteca para a interface e efeitos
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFrame, QGraphicsDropShadowEffect, QProgressBar, QStackedWidget
from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import Qt, Signal, QObject, QPropertyAnimation, QEasingCurve, QRect, Property

# --- Classes de Lógica de Negócio (sem alterações) ---

class SpotifyAPI:
    """Gerencia toda a comunicação com a API do Spotify."""
    BASE_URL = "https://api.spotify.com/v1"

    def __init__(self):
        import os
        self.client_id = os.environ.get("SPOTIPY_CLIENT_ID")
        self.client_secret = os.environ.get("SPOTIPY_CLIENT_SECRET")

        if not self.client_id or not self.client_secret:
            print("ERRO: As variáveis de ambiente SPOTIPY_CLIENT_ID e SPOTIPY_CLIENT_SECRET não foram definidas.")
            print("Por favor, defina-as antes de executar a aplicação.")
            # Consider exiting if secrets are missing and the app cannot function without them.
            # For example, you could call sys.exit(1) here after importing sys.
            # This example will let the app continue, but API calls will likely fail.

        self.redirect_uri = "https://example.com/callback"
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = 0

    def load_saved_token(self):
        try:
            with open('spotify_token.json', 'r', encoding='utf-8') as f:
                token_data = json.load(f)
                self.access_token = token_data.get('access_token')
                self.refresh_token = token_data.get('refresh_token')
                self.token_expires_at = token_data.get('expires_at', 0)

            if time.time() >= self.token_expires_at:
                if not self.refresh_access_token():
                    return False
                return True

            if not self._is_token_valid():
                return False

            return True
        except (FileNotFoundError, json.JSONDecodeError):
            return False

    def _is_token_valid(self):
        if not self.access_token: return False
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.get(f"{self.BASE_URL}/me", headers=headers)
        return response.status_code == 200

    def save_token(self):
        token_data = {
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'expires_at': self.token_expires_at
        }
        with open('spotify_token.json', 'w', encoding='utf-8') as f:
            json.dump(token_data, f)

    def get_auth_url(self):
        scopes = "user-read-currently-playing user-read-playback-state"
        params = {
            "client_id": self.client_id, "response_type": "code",
            "redirect_uri": self.redirect_uri, "scope": scopes
        }
        return f"https://accounts.spotify.com/authorize?{urllib.parse.urlencode(params)}"

    def exchange_code_for_token(self, auth_code):
        token_url = "https://accounts.spotify.com/api/token"
        auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        headers = {"Authorization": f"Basic {auth_header}", "Content-Type": "application/x-www-form-urlencoded"}
        data = {"grant_type": "authorization_code", "code": auth_code, "redirect_uri": self.redirect_uri}
        try:
            response = requests.post(token_url, headers=headers, data=data)
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data["access_token"]
            self.refresh_token = token_data.get("refresh_token")
            self.token_expires_at = time.time() + token_data["expires_in"]
            self.save_token()
            return True
        except requests.RequestException:
            return False

    def refresh_access_token(self):
        if not self.refresh_token: return False
        token_url = "https://accounts.spotify.com/api/token"
        auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        headers = {"Authorization": f"Basic {auth_header}"}
        data = {"grant_type": "refresh_token", "refresh_token": self.refresh_token}
        try:
            response = requests.post(token_url, headers=headers, data=data)
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data["access_token"]
            self.refresh_token = token_data.get("refresh_token", self.refresh_token)
            self.token_expires_at = time.time() + token_data["expires_in"]
            self.save_token()
            return True
        except requests.RequestException:
            return False

    def get_current_playback(self):
        if time.time() >= self.token_expires_at:
            if not self.refresh_access_token(): return None
        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            response = requests.get(f"{self.BASE_URL}/me/player/currently-playing?market=from_token", headers=headers)
            if response.status_code == 200 and response.text:
                return response.json()
            if response.status_code == 204: return None
            response.raise_for_status()
        except requests.RequestException:
            return None
        return None

class LyricsFetcher:
    def get_synced_lyrics(self, track_name, artist_name, duration_ms):
        cleaned_track_name = re.sub(r'[\(\-].*?(Remaster|Live|Acoustic|Version|Edit|Mix|Radio).*', '', track_name, flags=re.IGNORECASE).strip()
        cleaned_track_name = cleaned_track_name.split('/')[0].strip()

        lyrics = self._fetch_from_lrclib(cleaned_track_name, artist_name)
        if lyrics: return lyrics
        lyrics = self._fetch_from_megalobiz(cleaned_track_name, artist_name)
        if lyrics: return lyrics
        return None

    def _fetch_from_lrclib(self, track_name, artist_name):
        try:
            api_url = f"https://lrclib.net/api/search?track_name={quote(track_name)}&artist_name={quote(artist_name)}"
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data and data[0].get('syncedLyrics'):
                return self._parse_lrc(data[0]['syncedLyrics'])
        except Exception:
            return None

    def _fetch_from_megalobiz(self, track_name, artist_name):
        try:
            search_url = f"https://www.megalobiz.com/search/all?qry={quote(f'{track_name} {artist_name}')}"
            headers = {'User-Agent': 'Mozilla/5.0'}
            search_response = requests.get(search_url, headers=headers, timeout=10)
            search_response.raise_for_status()
            soup = BeautifulSoup(search_response.text, 'html.parser')
            lyrics_link = soup.find('a', class_='entity_name')
            if not lyrics_link: return None
            lyrics_page_url = f"https://www.megalobiz.com{lyrics_link['href']}"
            lyrics_response = requests.get(lyrics_page_url, headers=headers, timeout=10)
            lyrics_response.raise_for_status()
            page_soup = BeautifulSoup(lyrics_response.text, 'html.parser')
            lrc_text_span = page_soup.find('span', {'id': 'lrc_text'})
            if not lrc_text_span: return None
            return self._parse_lrc(lrc_text_span.get_text(separator='\n'))
        except Exception:
            return None

    def _parse_lrc(self, lrc_text):
        lyrics = []
        lrc_regex = re.compile(r'\[(\d{2}):(\d{2})\.(\d{2})\](.*)')
        for line in lrc_text.splitlines():
            match = lrc_regex.match(line)
            if match:
                minutes, seconds, hundredths, text = match.groups()
                time_ms = int(minutes) * 60000 + int(seconds) * 1000 + int(hundredths) * 10
                text = text.strip()
                if text: lyrics.append({'time': time_ms, 'text': text})
        lyrics.sort(key=lambda x: x['time'])
        return lyrics if lyrics else None

# --- Nova Classe de Interface Gráfica com PySide6 ---

class LyricsUI(QWidget):
    """Gerencia a janela de sobreposição com PySide6 para um design moderno."""

    def __init__(self, app_instance):
        super().__init__()
        self.app_instance = app_instance
        self.WINDOW_WIDTH = 900
        self.WINDOW_HEIGHT = 100
        self.BG_COLOR = "#222222"
        self.last_bg_color = self.BG_COLOR
        self.fg_color = "#FFFFFF" # Cor do texto principal

        self._setup_window()
        self._setup_ui()

        self.progress_animation = QPropertyAnimation(self.progress_bar, b"value", self)
        self.progress_animation.valueChanged.connect(self._update_time_label_from_animation)

        self.bg_animation = QPropertyAnimation(self, b"bgColor", self)
        self.bg_animation.setDuration(800)
        self.bg_animation.setEasingCurve(QEasingCurve.InOutQuad)

        self.set_theme_colors(self.BG_COLOR, self.fg_color) # Aplicar tema inicial


    def _setup_window(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_StyledBackground, True)

        screen_geometry = QApplication.primaryScreen().geometry()
        x_pos = (screen_geometry.width() - self.WINDOW_WIDTH) // 2
        self.setGeometry(x_pos, -15, self.WINDOW_WIDTH, self.WINDOW_HEIGHT)

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 15, 15, 15)

        self.background_frame = QFrame(self)
        self.background_frame.setObjectName("backgroundFrame")
        self.main_layout.addWidget(self.background_frame)

        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(20)
        self.shadow.setOffset(0, 5)
        self.background_frame.setGraphicsEffect(self.shadow)

        frame_layout = QVBoxLayout(self.background_frame)
        frame_layout.setContentsMargins(20, 10, 20, 10)

        self.view_stack = QStackedWidget(self)

        # Vista 1: Letras
        self.lyrics_widget = QWidget()
        lyrics_layout = QVBoxLayout(self.lyrics_widget)
        lyrics_layout.setContentsMargins(0, 0, 0, 0)
        lyrics_layout.setSpacing(5)
        self.current_line_label = self._create_shadowed_label()
        self.next_line_label = self._create_shadowed_label()
        lyrics_layout.addWidget(self.current_line_label)
        lyrics_layout.addWidget(self.next_line_label)
        self.view_stack.addWidget(self.lyrics_widget)

        # Vista 2: Pausa
        self.pause_label = self._create_shadowed_label()
        self.pause_label.setText("❚❚")
        self.pause_label.setObjectName("pauseLabel")
        self.view_stack.addWidget(self.pause_label)

        # Vista 3: Estado
        self.status_label = self._create_shadowed_label()
        self.view_stack.addWidget(self.status_label)

        self.progress_widget = QWidget()
        progress_layout = QHBoxLayout(self.progress_widget)
        progress_layout.setContentsMargins(0,0,0,0)

        self.current_time_label = QLabel("0:00", self)
        self.total_time_label = QLabel("0:00", self)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)

        progress_layout.addWidget(self.current_time_label)
        progress_layout.addWidget(self.progress_bar, 1)
        progress_layout.addWidget(self.total_time_label)

        frame_layout.addWidget(self.view_stack, 1)
        frame_layout.addWidget(self.progress_widget)

    def _create_shadowed_label(self):
        label = QLabel("", self)
        label.setAlignment(Qt.AlignCenter)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(0)
        shadow.setOffset(1, 1)
        label.setGraphicsEffect(shadow)
        return label

    def set_theme_colors(self, bg_hex, fg_hex):
        self.fg_color = fg_hex

        secondary_color = QColor(self.fg_color)
        secondary_color.setAlpha(180)

        shadow_color = QColor("#000000")
        shadow_color.setAlpha(120)

        progress_bg_color = QColor(shadow_color)
        progress_bg_color.setAlpha(50)

        self.shadow.setColor(shadow_color)
        self.current_line_label.graphicsEffect().setColor(shadow_color)
        self.next_line_label.graphicsEffect().setColor(shadow_color)
        self.status_label.graphicsEffect().setColor(shadow_color)
        self.pause_label.graphicsEffect().setColor(shadow_color)

        secondary_color_rgba = f"rgba({secondary_color.red()}, {secondary_color.green()}, {secondary_color.blue()}, {secondary_color.alphaF()})"
        progress_bg_color_rgba = f"rgba({progress_bg_color.red()}, {progress_bg_color.green()}, {progress_bg_color.blue()}, {progress_bg_color.alphaF()})"

        stylesheet = f"""
            #timeLabel, #statusLabel {{
                color: {secondary_color_rgba};
                font-size: 10px;
            }}
            #pauseLabel {{
                color: {self.fg_color};
                font-size: 40px;
                font-weight: bold;
                letter-spacing: -10px;
            }}
            QProgressBar {{
                background-color: {progress_bg_color_rgba};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {self.fg_color};
                border-radius: 2px;
            }}
        """
        self.progress_widget.setStyleSheet(stylesheet)
        self.status_label.setStyleSheet(stylesheet)
        self.pause_label.setStyleSheet(stylesheet)

        self.start_bg_animation(bg_hex)

    def update_display(self, current_lyric, next_lyric, progress_ms, duration_ms, is_playing, status_mode=False):
        if status_mode:
            self.progress_widget.hide()
            self.status_label.setText(current_lyric)
            self.view_stack.setCurrentWidget(self.status_label)
            self.progress_animation.stop()
        else:
            self.progress_widget.show()

            if is_playing:
                self.view_stack.setCurrentWidget(self.lyrics_widget)
            else:
                self.view_stack.setCurrentWidget(self.pause_label)

            def get_font_size(text, is_active):
                base_size = 22 if is_active else 18
                if len(text) > 85: return base_size - 9
                if len(text) > 65: return base_size - 5
                if len(text) > 50: return base_size - 2
                return base_size

            secondary_color = QColor(self.fg_color)
            secondary_color.setAlpha(180)
            secondary_color_rgba = f"rgba({secondary_color.red()}, {secondary_color.green()}, {secondary_color.blue()}, {secondary_color.alphaF()})"

            self.current_line_label.setText(current_lyric)
            self.current_line_label.setStyleSheet(f"background-color: transparent; font-size: {get_font_size(current_lyric, True)}px; font-weight: bold; color: {self.fg_color};")

            self.next_line_label.setText(next_lyric)
            self.next_line_label.setStyleSheet(f"background-color: transparent; font-size: {get_font_size(next_lyric, False)}px; color: {secondary_color_rgba};")

            self._update_progress(progress_ms, duration_ms, is_playing)

    def start_bg_animation(self, new_color_hex):
        self.bg_animation.stop()
        self.bg_animation.setStartValue(QColor(self.last_bg_color))
        self.bg_animation.setEndValue(QColor(new_color_hex))
        self.bg_animation.start()
        self.last_bg_color = new_color_hex

    @Property(QColor)
    def bgColor(self):
        return QColor(self.BG_COLOR)

    @bgColor.setter
    def bgColor(self, color):
        self.BG_COLOR = color.name()
        self.background_frame.setStyleSheet(f"#backgroundFrame {{ background-color: {self.BG_COLOR}; border-radius: 12px; }}")

    def _format_time(self, ms):
        if ms is None: return "0:00"
        seconds = int((ms / 1000) % 60)
        minutes = int((ms / (1000 * 60)) % 60)
        return f"{minutes}:{seconds:02d}"

    def _update_time_label_from_animation(self, value):
        self.current_time_label.setText(self._format_time(value))

    def _update_progress(self, progress_ms, duration_ms, is_playing):
        self.progress_animation.stop()

        self.total_time_label.setText(self._format_time(duration_ms))
        self.progress_bar.setRange(0, duration_ms if duration_ms > 0 else 100)

        if is_playing and duration_ms > 0 and progress_ms is not None:
            remaining_time = duration_ms - progress_ms
            if remaining_time > 0:
                self.progress_animation.setDuration(remaining_time)
                self.progress_animation.setStartValue(progress_ms)
                self.progress_animation.setEndValue(duration_ms)
                self.progress_animation.start()
        else:
            self.progress_bar.setValue(progress_ms if progress_ms is not None else 0)
            self.current_time_label.setText(self._format_time(progress_ms))

    def mousePressEvent(self, event):
        self.drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        self.move(self.pos() + event.globalPosition().toPoint() - self.drag_pos)
        self.drag_pos = event.globalPosition().toPoint()
        event.accept()

# --- Comunicação entre Threads ---
class WorkerSignals(QObject):
    update = Signal(dict)
    no_playback = Signal()
    theme_update = Signal(str, str) # bg_color, fg_color
    shutdown_signal = Signal()

# --- Classe Principal do Aplicativo ---

class SpotifyLyricsOverlay:
    def __init__(self, app):
        self.app = app
        self.spotify = SpotifyAPI()
        self.lyrics_fetcher = LyricsFetcher()
        self.ui = LyricsUI(self)
        self.tray_icon = None

        self.running = True
        self.stop_event = threading.Event()
        self.current_track_id = None
        self.synced_lyrics = None
        self.no_playback_counter = 0

        self.signals = WorkerSignals()
        self.signals.update.connect(self.process_playback_data)
        self.signals.no_playback.connect(self.handle_no_playback)
        self.signals.theme_update.connect(self.ui.set_theme_colors)
        self.signals.shutdown_signal.connect(self.shutdown)


    def run(self):
        if not self.spotify.load_saved_token():
            if not self.authenticate_spotify():
                return

        self.ui.show()
        self.ui.update_display("A aguardar música no Spotify...", "", 0, 0, False, status_mode=True)

        threading.Thread(target=self.setup_tray_icon, daemon=True).start()

        self.start_monitoring_thread()

    def authenticate_spotify(self):
        auth_url = self.spotify.get_auth_url()
        print(f"\n1. Copie esta URL: {auth_url}\n2. Cole no navegador, autorize e cole o URL de redirecionamento aqui.")
        webbrowser.open(auth_url)
        while True:
            try:
                redirected_url = input("🔗 Cole o URL de redirecionamento aqui: ")
                parsed_url = urllib.parse.urlparse(redirected_url)
                query_params = urllib.parse.parse_qs(parsed_url.query)
                if 'code' in query_params:
                    if self.spotify.exchange_code_for_token(query_params['code'][0]):
                        return True
                else:
                    print("❌ URL inválido.")
            except Exception:
                print("❌ Erro na autenticação. A encerrar.")
                return False

    def setup_tray_icon(self):
        width, height, color1, color2 = 64, 64, (29, 185, 84), (19, 19, 19)
        image = Image.new('RGB', (width, height), color2)
        dc = ImageDraw.Draw(image)
        dc.ellipse([(10, 10), (width - 10, height - 10)], fill=color1)
        menu = (pystray.MenuItem('Mostrar/Esconder', self.toggle_window_visibility, default=True),
                pystray.MenuItem('Sair', self.request_shutdown))
        self.tray_icon = pystray.Icon("name", image, "Spotify Lyrics Overlay", menu)
        self.tray_icon.run()

    def toggle_window_visibility(self):
        if self.ui.isVisible():
            self.ui.hide()
        else:
            self.ui.show()

    def start_monitoring_thread(self):
        threading.Thread(target=self.monitor_loop, daemon=True).start()

    def monitor_loop(self):
        while self.running:
            try:
                playback_data = self.spotify.get_current_playback()
                if not self.running:
                    break

                if playback_data and playback_data.get('item'):
                    self.no_playback_counter = 0
                    self.signals.update.emit(playback_data)
                else:
                    self.no_playback_counter += 1
                    if self.no_playback_counter >= 2:
                        self.signals.no_playback.emit()

            except Exception as e:
                print(f"ERRO no monitor_loop: {e}")

            if self.stop_event.wait(1):
                break

    def process_playback_data(self, data):
        track = data.get('item')
        if not track: return

        track_id = track['id']
        is_playing = data.get('is_playing', False)
        progress_ms = data.get('progress_ms', 0)
        duration_ms = track['duration_ms']

        album_art_url = track['album']['images'][-1]['url'] if track.get('album') and track['album'].get('images') else None

        if track_id != self.current_track_id:
            self.current_track_id = track_id
            self.synced_lyrics = None
            self.ui.update_display("A procurar letras...", "", progress_ms, duration_ms, is_playing, status_mode=True)
            self.signals.theme_update.emit("#222222", "#FFFFFF")
            threading.Thread(target=self.fetch_and_set_lyrics, args=(track_id, track['name'], track['artists'][0]['name'], duration_ms, album_art_url), daemon=True).start()

        current_line_text, next_line_text = "", ""
        if self.synced_lyrics:
            last_line_index = -1
            animated_progress = self.ui.progress_bar.value()
            for i, line in enumerate(self.synced_lyrics):
                if animated_progress >= line['time']:
                    last_line_index = i
                else:
                    break

            if last_line_index != -1:
                current_line_text = self.synced_lyrics[last_line_index]['text']
                if last_line_index + 1 < len(self.synced_lyrics):
                    next_line_text = self.synced_lyrics[last_line_index + 1]['text']
                else:
                    next_line_text = ""
            else:
                current_line_text = ""
                if self.synced_lyrics:
                    next_line_text = self.synced_lyrics[0]['text']

        self.ui.update_display(current_line_text, next_line_text, progress_ms, duration_ms, is_playing)

    def fetch_and_set_lyrics(self, track_id, track_name, artist_name, duration_ms, album_art_url):
        lyrics = self.lyrics_fetcher.get_synced_lyrics(track_name, artist_name, duration_ms)
        if self.current_track_id == track_id:
            self.synced_lyrics = lyrics if lyrics else [{'time': 0, 'text': "Letras não encontradas."}]
            if album_art_url:
                threading.Thread(target=self.set_background_from_url, args=(album_art_url,), daemon=True).start()

    def set_background_from_url(self, url):
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            img = Image.open(response.raw).convert("RGB").resize((1, 1), Image.Resampling.LANCZOS)
            r, g, b = img.getpixel((0, 0))

            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            bg_color_obj = QColor(r, g, b)

            if luminance > 0.55:
                bg_color_obj = bg_color_obj.darker(160)
            else:
                bg_color_obj = bg_color_obj.lighter(130)

            fg_color_hex = "#FFFFFF"

            self.signals.theme_update.emit(bg_color_obj.name(), fg_color_hex)
        except Exception as e:
            print(f"Erro ao processar cor da capa: {e}")
            self.signals.theme_update.emit("#222222", "#FFFFFF")

    def handle_no_playback(self):
        if self.current_track_id is not None:
            self.current_track_id = None
            self.synced_lyrics = None
            self.ui.update_display("Nenhuma música a tocar...", "", 0, 0, False, status_mode=True)
            self.signals.theme_update.emit("#222222", "#FFFFFF")
            self.no_playback_counter = 0

    def request_shutdown(self):
        if self.tray_icon:
            self.tray_icon.stop()
        self.signals.shutdown_signal.emit()

    def shutdown(self):
        self.running = False
        self.stop_event.set()
        self.app.quit()


if __name__ == "__main__":
    print("A iniciar...")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    overlay_app = SpotifyLyricsOverlay(app)
    overlay_app.run()

    sys.exit(app.exec())
