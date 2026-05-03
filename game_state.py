"""
game_state.py — Oyun Veri Modeli
==================================
Anlık oyun durumunun (top, raketler, skor, oyuncu adları) tek yetkili
kaynağıdır.  Ağ üzerinden senkronize edilen her şey bu nesnede tutulur.

  GameState : Oyun akışını tanımlayan enum  (WAITING / RUNNING / GAME_OVER)
  GameData  : Frame bazında anlık snapshot;  host her frame UDP ile gönderir,
              joiner aldığı verilerle kendi kopyasını eşler.
"""

from enum import Enum
import config


class GameState(Enum):
    """Oyun döngüsünün hangi aşamasında olduğunu gösterir."""
    WAITING   = "waiting"    # Geri sayım veya bağlantı bekleniyor
    RUNNING   = "running"    # Aktif oyun
    GAME_OVER = "game_over"  # Biri kazandı, oyun bitti


class GameData:
    """
    Anlık oyun verisi.

    Kimin neyi güncellediği:
      - Host    : top (x, y, vx, vy), skor, paddle1_y → UDP ile joiner'a gönderir
      - Joiner  : paddle2_y → UDP ile host'a gönderir; geri kalan host'tan gelir
    """

    def __init__(self, player1_name: str = "Player1", player2_name: str = "Player2"):
        # ── Oyun akışı ──────────────────────────────────────────────────────
        self.state     = GameState.WAITING
        self.score1    = 0      # Sol oyuncu (host) skoru
        self.score2    = 0      # Sağ oyuncu (joiner) skoru
        self.max_score = 5      # Bu skorla oyun biter
        self.winner    = None   # 1 = host kazandı, 2 = joiner kazandı, None = devam

        # ── Raketler ────────────────────────────────────────────────────────
        self.paddle_height: int = 100   # Raket yüksekliği (px)
        self.paddle_speed:  int = 10    # Raket hızı (px/frame)

        # Başlangıç Y: sahada dikey orta
        field_bottom       = config.WINDOW_HEIGHT - config.FIELD_BOTTOM_MARGIN
        start_y            = (config.FIELD_TOP + field_bottom - self.paddle_height) / 2.0
        self.paddle1_y: float = start_y   # Host (sol) raket Y koordinatı
        self.paddle2_y: float = start_y   # Joiner (sağ) raket Y koordinatı

        # ── Top ─────────────────────────────────────────────────────────────
        self.ball_x:      float = float(config.GAME_AREA_WIDTH // 2)
        self.ball_y:      float = float((config.FIELD_TOP + field_bottom) / 2.0)
        self.ball_vx:     float = 5.0    # Yatay hız  (+→sağ, -→sol)
        self.ball_vy:     float = 3.0    # Dikey hız  (+→aşağı, -→yukarı)
        self.ball_speed:  float = 5.0    # Mevcut büyüklük; GameLogic artırır
        self.ball_radius: int   = 5      # Çizim ve çarpışma yarıçapı (px)

        # ── Oyuncu bilgileri ─────────────────────────────────────────────────
        self.player1_name  = player1_name
        self.player2_name  = player2_name
        self.player1_color = (255, 100,  50)   # Turuncu — host (sol)
        self.player2_color = (100, 200, 150)   # Yeşilimsi — joiner (sağ)
