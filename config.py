"""
config.py — Merkezi Ayarlar
=============================
Projedeki tüm sabit değerler buradan okunur.
Herhangi bir parametreyi değiştirmek için yalnızca bu dosyayı düzenlemek yeterlidir.

Bölümler:
  [1] Phase 1 sabitleri  — eski server-authoritative mimari (server.py / protocol.py)
  [2] Phase 2 sabitleri  — aktif P2P mimari (client.py, physics.py, ...)
"""

# ══════════════════════════════════════════════════════════════════════════════
# [1] PHASE 1 — Merkezi Sunucu Mimarisi
#     server.py ve protocol.py bu değerleri kullanır.
#     Aktif P2P oyununda (client.py) bu sabitler KULLANILMAZ.
# ══════════════════════════════════════════════════════════════════════════════

SERVER_HOST = "localhost"   # Sunucu IP adresi (test için)
SERVER_PORT = 5000          # Sunucunun dinlediği port
PROTOCOL    = "TCP"         # TCP veya UDP
BUFFER_SIZE = 1024          # Ağdan alınan paket boyutu (byte)

# ══════════════════════════════════════════════════════════════════════════════
# [2] PHASE 2 — P2P Mimarisi  (aktif)
# ══════════════════════════════════════════════════════════════════════════════

# ── Pencere ──────────────────────────────────────────────────────────────────
WINDOW_WIDTH     = 1000   # Toplam pencere genişliği (px)
WINDOW_HEIGHT    = 700    # Toplam pencere yüksekliği (px)
WINDOW_TITLE     = "Pong P2P"
FPS              = 60
BACKGROUND_COLOR = (0, 0, 0)

# ── Ekran düzeni (sol = oyun alanı, sağ = sohbet paneli) ─────────────────────
GAME_AREA_WIDTH = 720   # Sol bölüm: oyun sahası genişliği
CHAT_AREA_WIDTH = 280   # Sağ bölüm: sohbet paneli genişliği

# ── Saha sınırları ────────────────────────────────────────────────────────────
FIELD_TOP           = 70    # Sahanın üst sınırı; skor kutusunun altı
FIELD_BOTTOM_MARGIN = 24    # Sahanın alt boşluğu; pencere altından px

# ── Raket ────────────────────────────────────────────────────────────────────
PADDLE_WIDTH  = 15    # Raket genişliği (px)
PADDLE_HEIGHT = 100   # Raket yüksekliği (px)
PADDLE_MARGIN = 20    # Raketin saha kenarından uzaklığı (px)

# ── Top ───────────────────────────────────────────────────────────────────────
# Başlangıç konumu GameData.__init__() içinde GAME_AREA_WIDTH ve
# FIELD_TOP/FIELD_BOTTOM_MARGIN kullanılarak dinamik hesaplanır.
BALL_RADIUS = 5   # Top yarıçapı (px) — GameData.ball_radius ile aynı değer

# ── Renkler (genel) ───────────────────────────────────────────────────────────
# client.py kendi renk paletini (C_ACCENT, C_GREEN vb.) tanımlar;
# bu renkler ortak yardımcı amaçlı.
WHITE = (255, 255, 255)
BLACK = (0,   0,   0)
GREEN = (0,   255, 0)
RED   = (255, 0,   0)

# ── Ağ portları ───────────────────────────────────────────────────────────────
TCP_PORT        = 5000   # Sohbet, game_over ve rematch_accept sinyalleri
UDP_PORT        = 5001   # Host'un dinlediği UDP portu
UDP_PORT_JOINER = 5002   # Joiner'ın dinlediği UDP portu
#
# Neden iki farklı UDP portu?
#   Windows SO_REUSEADDR'da iki soket aynı porta bağlanınca gelen paketler
#   karışabilir.  Joiner kendi "paddle_update" paketini görür, top hiç
#   hareket etmez.  Ayrı portlarla bu sorun kesin olarak önlenir.

# ── Oyun kuralları ────────────────────────────────────────────────────────────
GAME_MAX_SCORE = 5    # Bu skora ulaşan oyuncu kazanır
GAME_FPS       = 60   # Oyun döngüsü frame hızı

# ── Sohbet ────────────────────────────────────────────────────────────────────
CHAT_MAX_MESSAGES = 20   # Geçmişte tutulan maksimum mesaj sayısı
CHAT_MAX_INPUT    = 50   # Giriş alanı maksimum karakter sayısı

# ── Hata ayıklama ─────────────────────────────────────────────────────────────
DEBUG              = True   # Genel debug modu
SHOW_FPS           = True   # FPS sayacı ekranda göster
SHOW_NETWORK_DEBUG = True   # Ağ mesajlarını konsola yaz
