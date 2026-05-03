"""
chat_ui.py — Sohbet Arayüzü Bileşeni
=======================================
Oyun penceresinin sağ panelinde sohbet kutusunu çizer ve
klavye girişlerini yakalar.

  draw()         : Arka plan, mesaj baloncukları ve giriş kutusunu render eder.
  handle_event() : Klavye olaylarını işler; ENTER'da ChatHandler'a iletir.

Bu modül yalnızca görselleştirme ve giriş yakalamadan sorumludur.
Mesaj gönderme/alma mantığı chat_handler.py'dedir.
"""

import sys

try:
    import pygame
except ImportError:
    print("pygame not installed. Run: pip install pygame")
    sys.exit(1)

from chat_handler import ChatHandler


class ChatUI:
    """Sohbet panelinin görsel bileşeni."""

    def __init__(self, x: int, y: int, width: int, height: int):
        self.rect             = pygame.Rect(x, y, width, height)
        self.chat_handler: ChatHandler | None = None   # Dışarıdan atanır
        self.input_text       = ""      # Kullanıcının şu an yazdığı metin
        self.input_active     = False   # Giriş kutusuna tıklanmış mı?
        self.max_input_length = 50      # Maksimum giriş uzunluğu (karakter)

        self.font_title   = pygame.font.Font(None, 22)
        self.font_message = pygame.font.Font(None, 18)
        self.font_hint    = pygame.font.Font(None, 16)

        self._msg_h = 28   # Mesaj başına satır yüksekliği (px)

    def draw(self, screen: pygame.Surface):
        """Tüm sohbet panelini (arka plan, başlık, mesajlar, giriş) çizer."""

        # ── Arka plan ve çerçeve ─────────────────────────────────────────
        pygame.draw.rect(screen, (12, 17, 32), self.rect)
        pygame.draw.rect(screen, (40, 52, 82), self.rect, 1)

        # ── Başlık ───────────────────────────────────────────────────────
        title_rect = pygame.Rect(self.rect.x + 10, self.rect.y + 10,
                                 self.rect.width - 20, 30)
        pygame.draw.rect(screen, (20, 28, 50), title_rect, border_radius=8)
        pygame.draw.rect(screen, (50, 64, 100), title_rect, 1, border_radius=8)
        title_srf = self.font_title.render("SOHBET", True, (200, 210, 230))
        screen.blit(title_srf, (title_rect.x + 10, title_rect.y + 7))

        # ── Mesajlar ─────────────────────────────────────────────────────
        input_y  = self.rect.bottom - 46
        avail_h  = input_y - (self.rect.y + 52)
        max_msgs = max(1, avail_h // self._msg_h)   # Ekrana sığan maksimum mesaj

        msg_y = self.rect.y + 52
        if self.chat_handler:
            for msg in self.chat_handler.get_display_messages(max_msgs):
                # Sistem mesajı → mavi; oyuncu mesajı → sarı
                if msg["is_system"]:
                    color = (96, 165, 250)
                    raw   = f"SYS  {msg['text']}"
                else:
                    color = (250, 204, 99)
                    raw   = f"{msg['sender']}: {msg['text']}"

                # Panel genişliğine sığmayan metni kes
                max_chars = (self.rect.width - 28) // 7
                text      = raw if len(raw) <= max_chars else raw[:max_chars - 3] + "..."

                bubble = pygame.Rect(self.rect.x + 8, msg_y - 4,
                                     self.rect.width - 16, self._msg_h - 2)
                pygame.draw.rect(screen, (18, 26, 46), bubble, border_radius=6)
                rendered = self.font_message.render(text, True, color)
                screen.blit(rendered, (bubble.x + 8, msg_y + 2))
                msg_y += self._msg_h

        # ── Giriş kutusu ─────────────────────────────────────────────────
        input_rect   = pygame.Rect(self.rect.x + 8, input_y, self.rect.width - 16, 34)
        input_bg     = (24, 34, 56) if self.input_active else (16, 22, 40)
        input_border = (80, 200, 160) if self.input_active else (50, 65, 100)
        pygame.draw.rect(screen, input_bg,     input_rect, border_radius=8)
        pygame.draw.rect(screen, input_border, input_rect, 2, border_radius=8)

        # Kürsör yanıp söner (500 ms aralık)
        if self.input_text:
            display  = self.input_text
            if self.input_active and (pygame.time.get_ticks() // 500) % 2 == 0:
                display += "|"
            color_in = (215, 228, 248)
        else:
            display  = "mesaj yaz..." if not self.input_active else "|"
            color_in = (80, 96, 130)

        rendered_in = self.font_message.render(display, True, color_in)
        screen.blit(rendered_in, (input_rect.x + 10, input_rect.y + 9))

        # ── Alt ipucu ────────────────────────────────────────────────────
        hint = self.font_hint.render("ENTER: gonder  |  tikla: aktif et",
                                     True, (45, 58, 90))
        screen.blit(hint, (self.rect.x + 8, self.rect.bottom - 12))

    def handle_event(self, event: pygame.event.Event):
        """
        Pygame olaylarını işler.

          MOUSEBUTTONDOWN : Panele tıklanmışsa giriş kutusunu aktif eder.
          KEYDOWN (aktifse):
            ENTER     → mesajı ChatHandler'a gönderir, giriş kutusunu temizler.
            BACKSPACE → son karakteri siler.
            Diğer     → max_input_length'e kadar karakteri ekler.
        """
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.input_active = self.rect.collidepoint(event.pos)

        if event.type == pygame.KEYDOWN and self.input_active:
            if event.key == pygame.K_RETURN:
                if self.chat_handler and self.input_text.strip():
                    self.chat_handler.send_message(self.input_text)
                self.input_text = ""
            elif event.key == pygame.K_BACKSPACE:
                self.input_text = self.input_text[:-1]
            elif event.unicode and event.unicode.isprintable():
                if len(self.input_text) < self.max_input_length:
                    self.input_text += event.unicode
