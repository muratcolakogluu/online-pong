"""
game_screen.py — Oyun Ekranı Render Bileşeni
==============================================
Oyun sahasını ve sohbet panelini çizer; oyuncu klavye girişini yakalar.

  GameScreen.draw()         : Saha + skor + raketler + top + sohbet paneli.
  GameScreen._draw_game_area(): Sahaya özgü tüm çizim işlemleri.
  GameScreen.handle_input() : Klavye olayını ChatUI'ye iletir.

Bu modül yalnızca görselleştirme ve giriş yakalamadan sorumludur.
Fizik, kural ve ağ işlemleri buraya taşınmaz.
"""

import sys

try:
    import pygame
except ImportError:
    print("pygame not installed. Run: pip install pygame")
    sys.exit(1)

import config
from chat_ui import ChatUI
from game_state import GameData


class GameScreen:
    """Oyun penceresinin tüm görsel katmanını yönetir."""

    def __init__(self, width: int = config.WINDOW_WIDTH,
                 height: int = config.WINDOW_HEIGHT):
        """
        Pencere boyutlarını kaydeder; oyun sahası ve sohbet UI bileşenini oluşturur.

        Pencere = sol GAME_AREA_WIDTH px (oyun) + sağ CHAT_AREA_WIDTH px (sohbet).
        ChatUI nesnesi dışarıdan chat_handler atanana kadar boş kalır.
        """
        self.width  = width
        self.height = height

        # Oyun sahası genişliği ve sohbet paneli genişliği
        gw = config.GAME_AREA_WIDTH
        cw = config.CHAT_AREA_WIDTH
        self.game_area = pygame.Rect(0, 0, gw, height)  # Çizim sınırı referansı
        self.chat_ui   = ChatUI(gw, 0, cw, height)      # Sağ panel sohbet bileşeni

        self.font_large = pygame.font.Font(None, 56)
        self.font_small = pygame.font.Font(None, 22)
        self.font_tiny  = pygame.font.Font(None, 18)

    def draw(self, screen: pygame.Surface, game_data: GameData):
        """
        Tüm ekranı çizer: oyun sahası (sol) + ayırıcı çizgi + sohbet (sağ).

        game_data'daki anlık değerler kullanılır; bu fonksiyon her frame
        çağrılır.
        """
        self._draw_game_area(screen, game_data)

        # Saha / sohbet ayırıcı dikey çizgi
        pygame.draw.line(screen, (62, 74, 104),
                         (config.GAME_AREA_WIDTH, 0),
                         (config.GAME_AREA_WIDTH, self.height), 2)

        self.chat_ui.draw(screen)

    def _draw_game_area(self, screen: pygame.Surface, game_data: GameData):
        """
        Oyun sahasını ayrı bir Surface üzerine çizer, ardından ana ekrana yapıştırır.

        Çizim sırası (alt → üst):
          1. Gradyan arka plan
          2. Saha çerçevesi
          3. Skor kutusu ve oyuncu adları
          4. Orta kesik çizgi
          5. Sol raket (host)
          6. Sağ raket (joiner)
          7. Top (iç beyaz + dış altın hale)
        """
        gw = self.game_area.width
        gh = self.game_area.height

        # ── 1. Gradyan arka plan ─────────────────────────────────────────
        surf   = pygame.Surface((gw, gh))
        top    = (10, 16, 30)
        bottom = (18, 24, 38)
        for y in range(gh):
            t     = y / max(1, gh - 1)
            color = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
            pygame.draw.line(surf, color, (0, y), (gw, y))

        # ── 2. Saha çerçevesi ─────────────────────────────────────────────
        field_top    = config.FIELD_TOP
        field_bottom = config.WINDOW_HEIGHT - config.FIELD_BOTTOM_MARGIN
        pygame.draw.rect(surf, (35, 45, 66),
                         pygame.Rect(14, field_top, gw - 28, field_bottom - field_top),
                         2, border_radius=12)

        # ── 3. Skor kutusu ───────────────────────────────────────────────
        score_box = pygame.Rect(gw // 2 - 82, 10, 164, 46)
        pygame.draw.rect(surf, (20, 27, 43), score_box, border_radius=14)
        pygame.draw.rect(surf, (82, 96, 125), score_box, 1, border_radius=14)
        score_srf = self.font_large.render(
            f"{game_data.score1}   {game_data.score2}", True, (248, 250, 252)
        )
        surf.blit(score_srf, (gw // 2 - score_srf.get_width() // 2, 8))

        # Oyuncu adları ve rol etiketleri (HOST / JOIN)
        p1_srf = self.font_small.render(game_data.player1_name, True, game_data.player1_color)
        p2_srf = self.font_small.render(game_data.player2_name, True, game_data.player2_color)
        surf.blit(p1_srf, (24, 20))
        surf.blit(p2_srf, (gw - p2_srf.get_width() - 24, 20))
        surf.blit(self.font_tiny.render("HOST", True, (156, 163, 175)), (24, 42))
        surf.blit(self.font_tiny.render("JOIN", True, (156, 163, 175)),
                  (gw - self.font_tiny.size("JOIN")[0] - 24, 42))

        # ── 4. Orta kesik çizgi ──────────────────────────────────────────
        for y in range(field_top + 12, field_bottom - 8, 18):
            pygame.draw.line(surf, (70, 82, 110),
                             (gw // 2, y),
                             (gw // 2, min(y + 9, field_bottom - 8)), 2)

        # ── 5. Sol raket (host) ──────────────────────────────────────────
        p1 = pygame.Rect(20, int(game_data.paddle1_y), 15, game_data.paddle_height)
        pygame.draw.rect(surf, (0, 0, 0), p1.move(3, 3), border_radius=6)   # Gölge
        pygame.draw.rect(surf, game_data.player1_color, p1, border_radius=6)

        # ── 6. Sağ raket (joiner) ────────────────────────────────────────
        p2 = pygame.Rect(gw - 35, int(game_data.paddle2_y), 15, game_data.paddle_height)
        pygame.draw.rect(surf, (0, 0, 0), p2.move(3, 3), border_radius=6)   # Gölge
        pygame.draw.rect(surf, game_data.player2_color, p2, border_radius=6)

        # ── 7. Top ───────────────────────────────────────────────────────
        center = (int(game_data.ball_x), int(game_data.ball_y))
        pygame.draw.circle(surf, (250, 204, 99), center, game_data.ball_radius + 4)  # Hale
        pygame.draw.circle(surf, (255, 255, 255), center, game_data.ball_radius)     # İç

        screen.blit(surf, (0, 0))

    def handle_input(self, event: pygame.event.Event):
        """
        Pygame olayını ChatUI'ye iletir.

        Sohbet dışındaki giriş (raket hareketi, ESC vb.)
        client.py'nin _run_game() metodu tarafından doğrudan işlenir.
        """
        self.chat_ui.handle_event(event)
