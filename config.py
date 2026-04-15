# ============================================================================
# config.py - Pong Oyunu Konfigürasyonu
# ============================================================================
# Bu dosya tüm sabit değerleri merkezi olarak tutar.
# İstediğimiz zaman ayarları değiştirmek kolay olur.
# ============================================================================

# --- AĞIR YAPILANDIRMALAR (Server Bağlantısı) ---
SERVER_HOST = "localhost"      # Server'ın IP adresi (test için localhost)
SERVER_PORT = 5000             # Server'ın dinlediği port
PROTOCOL = "TCP"               # TCP veya UDP (başlangıç: TCP)
BUFFER_SIZE = 1024             # Ağdan aldığımız data paketi boyutu

# --- PYGAME PENCERESI YAPILANDIRMASI ---
WINDOW_WIDTH = 800             # Oyun penceresinin genişliği (pixel)
WINDOW_HEIGHT = 600            # Oyun penceresinin yüksekliği (pixel)
WINDOW_TITLE = "Pong Oyunu - TCP/UDP"
FPS = 60                       # Hedef kare hızı (frame per second)
BACKGROUND_COLOR = (0, 0, 0)   # Siyah arka plan (RGB)

# --- OYUN NESNELERININ BOYUTLARI ---
PADDLE_WIDTH = 15
PADDLE_HEIGHT = 90
BALL_SIZE = 10                 # Top çemberinin yarıçapı

# --- PADDLE KONUMLANDIRMASI ---
PADDLE_MARGIN = 20             # Padlle'nin ekranın kenarından uzaklığı
PADDLE_LEFT_X = PADDLE_MARGIN
PADDLE_RIGHT_X = WINDOW_WIDTH - PADDLE_MARGIN - PADDLE_WIDTH
PADDLE_START_Y = (WINDOW_HEIGHT - PADDLE_HEIGHT) // 2

# --- BALL BAŞLANGIÇ KONUMU ---
BALL_START_X = WINDOW_WIDTH // 2
BALL_START_Y = WINDOW_HEIGHT // 2

# --- RENKLER (RGB) ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
PADDLE_COLOR = WHITE
BALL_COLOR = WHITE
TEXT_COLOR = WHITE

# --- YAZILIM YAPILANDIRMASI ---
FONT_SIZE = 36                 # Skor yazısının boyutu
FONT_NAME = "arial"            # Yazı tipi adı

# --- DEBUGGİNG ---
DEBUG = True                   # Debug modunu aç/kapat
SHOW_FPS = True               # FPS sayacını göster
SHOW_NETWORK_DEBUG = True     # Network mesajlarını konsola yazdır
