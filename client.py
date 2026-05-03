"""
client.py — Ana Uygulama ve Durum Makinesi
============================================
Pygame döngüsünü çalıştırır; tüm bileşenleri (ağ, fizik, UI, sohbet)
bir araya getirir.

Durum geçiş akışı:
  NAME_INPUT → LOBBY → HOSTING / JOIN_INPUT → CONNECTING → COUNTDOWN → GAME → GAME_OVER
                                                                              ↑ (rematch)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
UDP mimarisi (kritik — iki port zorunlu):
  Host  : 5001 dinler → joiner'a 5002 gönderir   │ Her frame:
  Joiner: 5002 dinler → host'a    5001 gönderir   │   Host  → top+skor+raket1
                                                   │   Joiner→ raket2
  Windows SO_REUSEADDR'da aynı porta bağlanan iki soket
  birbirinin paketlerini alabilir.  Ayrı portlar bunu önler.

TCP mimarisi (garantili iletim):
  • Oyuncu adı değişimi   (bağlantı kurulurken, tek seferlik)
  • Sohbet mesajları      (her ENTER tuşuna basışta)
  • game_over sinyali     (host → joiner: final skor + kazanan)
  • rematch_accept        (her oyuncu R'ye basınca)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Host fizik yetkisi:
  Yalnızca host BallPhysics.update() çağırır.
  Hesaplanan top konumu ve skor UDP ile joiner'a gönderilir.
  Joiner kendi raket Y'sini (paddle2_y) host'a gönderir, geri kalanı alır.

3. kişi koruması:
  host_tcp() accept() sonrası server soketini hemen kapatır.
  Yeni TCP bağlantısı imkânsız → [10061] ConnectionRefusedError.
"""

import pygame
import sys
import socket
import json
import threading
import time

import config
from game_state import GameData
from game_logic import GameLogic
from physics import BallPhysics
from chat_handler import ChatHandler
from game_screen import GameScreen
from network_handler_p2p import P2PNetworkHandler

COUNTDOWN_SEC  = 3
GOAL_PAUSE_SEC = 2

# ── Renk paleti ───────────────────────────────────────────────────────────────
C_BG_TOP = (6,   8,  20)
C_BG_BOT = (14, 19,  40)
C_CARD   = (15, 21,  42)
C_BORDER = (38, 52,  88)
C_ACCENT = (0,  210, 255)   # cyan    -- genel vurgu / aktif eleman
C_GREEN  = (65, 220, 135)   # yesil  -- basari / host butonu
C_YELLOW = (255, 195,  50)  # sari  -- IP / uyari
C_RED    = (255,  75,  75)  # kirmizi -- hata
C_WHITE  = (230, 238, 252)
C_MUTED  = (110, 128, 160)
C_DIM    = ( 55,  70, 105)


class GameClient:
    def __init__(self, default_name: str = "Player1"):
        """
        Tüm bileşenleri başlatır ve pygame penceresini açar.

        Başlatılan bileşenler:
          • P2PNetworkHandler  — TCP/UDP ağ katmanı
          • GameData           — anlık oyun durumu (top, raketler, skor)
          • GameLogic          — kazanma/hız güncelleme kuralları
          • BallPhysics        — swept-AABB çarpışma + gol tespiti (sadece host çalıştırır)
          • ChatHandler        — sohbet geçmişi ve TCP mesaj iletimi
          • GameScreen         — oyun sahası + sohbet paneli render

        Gradient arka plan bir kez Surface'e işlenir; her karede tek blit.
        """
        self.player_name = default_name
        self.running     = True
        self.state       = "NAME_INPUT"
        self.is_host     = False

        self.network = P2PNetworkHandler(
            default_name, tcp_port=config.TCP_PORT, udp_port=config.UDP_PORT
        )
        self._connection_error = ""
        self._connecting_to    = ""

        self.game_data    = GameData(default_name, "Rakip")
        self.game_logic   = GameLogic(self.game_data)
        self.physics      = BallPhysics(self.game_data)
        self.chat_handler = ChatHandler(self.network, default_name)
        self.game_screen  = GameScreen(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)

        self._countdown_start        = 0.0
        self._goal_pause_until       = 0.0
        self._i_want_rematch         = False
        self._opponent_wants_rematch = False

        self._ip_input   = ""
        self._name_input = default_name

        self.screen = pygame.display.set_mode((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
        pygame.display.set_caption("Pong P2P")
        self.clock = pygame.time.Clock()

        self.font_title  = pygame.font.Font(None, 96)
        self.font_large  = pygame.font.Font(None, 80)
        self.font_medium = pygame.font.Font(None, 52)
        self.font_small  = pygame.font.Font(None, 34)
        self.font_tiny   = pygame.font.Font(None, 24)
        self.font_label  = pygame.font.Font(None, 20)

        # Gradient arka plani bir kez olustur -- her karede cizme
        self._bg = pygame.Surface((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
        for y in range(config.WINDOW_HEIGHT):
            t = y / max(1, config.WINDOW_HEIGHT - 1)
            r = int(C_BG_TOP[0] + (C_BG_BOT[0] - C_BG_TOP[0]) * t)
            g = int(C_BG_TOP[1] + (C_BG_BOT[1] - C_BG_TOP[1]) * t)
            b = int(C_BG_TOP[2] + (C_BG_BOT[2] - C_BG_TOP[2]) * t)
            pygame.draw.line(self._bg, (r, g, b), (0, y), (config.WINDOW_WIDTH, y))

    # ── Render yardimcilari ────────────────────────────────────────────────────

    def _draw_bg(self):
        """Önceden hazırlanan gradient arka plan Surface'ini ekrana yapıştırır."""
        self.screen.blit(self._bg, (0, 0))

    def _center(self, surf: pygame.Surface, y: int):
        """Verilen Surface'i pencere genişliğine göre yatay ortalar ve y konumuna yerleştirir."""
        self.screen.blit(surf, (config.WINDOW_WIDTH // 2 - surf.get_width() // 2, y))

    def _draw_card(self, rect: pygame.Rect, border_color=None, radius: int = 16):
        """
        Yarı saydam arka plan kartı çizer (C_CARD rengi + ince çerçeve).

        border_color verilmezse C_BORDER (varsayılan gri-mavi) kullanılır.
        SRCALPHA Surface ile çizildiği için altındaki katmanları yarı şeffaf örtler.
        """
        bc = border_color or C_BORDER
        s  = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(s, (*C_CARD, 235), (0, 0, rect.w, rect.h), border_radius=radius)
        pygame.draw.rect(s, (*bc,     210), (0, 0, rect.w, rect.h), 2, border_radius=radius)
        self.screen.blit(s, rect.topleft)

    def _draw_key_button(self, key: str, label: str, rect: pygame.Rect, accent=C_GREEN):
        """[KEY] etiketi + aciklama iceren modern buton."""
        self._draw_card(rect, border_color=accent)
        key_txt = f"[{key}]"
        key_w   = self.font_small.size(key_txt)[0] + 22
        key_r   = pygame.Rect(rect.x + 16, rect.y + rect.h // 2 - 17, key_w, 34)
        pygame.draw.rect(self.screen, accent, key_r, border_radius=8)
        ks = self.font_small.render(key_txt, True, (8, 12, 26))
        self.screen.blit(ks, (key_r.x + 11, key_r.y + 7))
        ls = self.font_small.render(label, True, C_WHITE)
        self.screen.blit(ls, (key_r.right + 20, rect.y + rect.h // 2 - ls.get_height() // 2))

    def _draw_logo(self, y: int = 60):
        """
        "PONG" başlığını ve altına ince dekoratif çizgiyi çizer.

        y: başlık metninin üst kenarının piksel konumu (varsayılan 60).
        Çizgi: başlığın hemen altında, yatay ortada 320 px uzunluğunda.
        """
        pong = self.font_title.render("PONG", True, C_ACCENT)
        self._center(pong, y)
        ly = y + pong.get_height() + 6
        pygame.draw.line(self.screen, C_DIM,
                         (config.WINDOW_WIDTH // 2 - 160, ly),
                         (config.WINDOW_WIDTH // 2 + 160, ly), 1)

    # ── Yardimci fonksiyonlar ──────────────────────────────────────────────────

    @staticmethod
    def _get_local_ip() -> str:
        """
        Makinenin yerel ağ IP adresini döndürür.

        Gerçek bir bağlantı kurmadan, UDP soketi ile dış adrese (8.8.8.8:80)
        bağlanma girişimi yapılır; OS bu sırada doğru arayüzü seçer ve
        getsockname() ile IP okunur. Başarısız olursa 'Bilinmiyor' döner.
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "Bilinmiyor"

    def _fmt_error(self, e: Exception) -> str:
        """
        İstisna nesnesini Türkçe, kullanıcı dostu hata mesajına dönüştürür.

        Windows hata kodları (winerror) ve POSIX errno değerleri kontrol edilir.
        Tanınan kodlar:
          10061 / 111  → Bağlantı reddedildi (oyun dolu / host kapalı)
          10048 / 98   → Port meşgul (eski süreç hâlâ porttu tutuyor)
          10060 / 110  → Zaman aşımı (yanlış IP)
          10054 / 104  → Bağlantı kesildi (rakip çıkış yaptı)
          10051 / 113  → Host'a ulaşılamadı (farklı ağ)
        """
        code = getattr(e, 'winerror', None) or getattr(e, 'errno', None)
        msg  = str(e).lower()
        if isinstance(e, ConnectionRefusedError) or code in (111, 10061):
            return "[10061] Baglanti reddedildi -- oyun dolu veya host baslatilmadi"
        if code in (98, 10048) or "address already in use" in msg:
            return "[10048] Port mesgul -- 5-10 sn bekleyip tekrar deneyin"
        if isinstance(e, TimeoutError) or code in (110, 10060) or "timed out" in msg:
            return "[10060] Zaman asimi -- IP adresi dogru mu?"
        if "connection reset" in msg or code in (104, 10054):
            return "[10054] Baglanti kesildi -- rakip cikis yapti"
        if "no route to host" in msg or code in (113, 10051):
            return "[10051] Host'a ulasilamadi -- ayni agda misiniz?"
        return f"Hata ({type(e).__name__})"

    def _reset_network(self):
        """
        Mevcut ağ bağlantısını kapatır ve sıfır durumda yeni bir P2PNetworkHandler oluşturur.

        'Host Ol' veya 'Katıl' tekrar deneme akışlarında çağrılır;
        eski soket artıkları bir sonraki oturuma sızmaz.
        """
        self.network.close()
        self.network = P2PNetworkHandler(
            self.player_name, tcp_port=config.TCP_PORT, udp_port=config.UDP_PORT
        )

    def _start_countdown(self, opponent_name: str = "Rakip"):
        """
        Oyunu sıfırlar ve 3 saniyelik geri sayım ekranına geçer.

        Yeni bir GameData, GameLogic, BallPhysics ve ChatHandler oluşturur;
        böylece önceki oyunun skor/top/raket değerleri temizlenir.
        ChatUI'nin chat_handler referansı da burada bir kez atanır
        (oyun sırasında her karede yeniden atanmasına gerek kalmaz).

        Host sol raket (player1), joiner sağ raket (player2) olarak konumlandırılır.
        """
        # Host sol (player1), Joiner sag (player2)
        p1, p2 = (self.player_name, opponent_name) if self.is_host \
                 else (opponent_name, self.player_name)
        self.game_data    = GameData(p1, p2)
        self.game_logic   = GameLogic(self.game_data)
        self.physics      = BallPhysics(self.game_data)
        self.chat_handler = ChatHandler(self.network, self.player_name)
        self.game_screen.chat_ui.chat_handler = self.chat_handler
        self._countdown_start        = time.time()
        self._goal_pause_until       = 0.0
        self._i_want_rematch         = False
        self._opponent_wants_rematch = False
        self.state = "COUNTDOWN"

    def _send_quit(self):
        """
        Rakibe TCP üzerinden 'quit' sinyali gönderir, ardından ağı kapatır.

        Oyundan kasıtlı çıkışlarda (ESC, pencere kapatma) çağrılır.
        Küçük bir bekleme eklenir; socket.close() hemen çağrılırsa
        OS tamponu tam gönderilmeden soketi kapatabilir.
        """
        self._send_tcp({"action": "quit"})
        time.sleep(0.05)   # OS'un paketi karşıya iletmesi için kısa mühlet

    def _send_tcp(self, data: dict):
        """
        Sözlüğü JSON satırı olarak TCP kanalından karşı tarafa gönderir.

        Kullanım yerleri:
          • game_over   : host kazanan + final skoru joiner'a bildirir.
          • rematch_accept: her oyuncu tekrar oynamayı onayladığında gönderir.
        Gönderim hatası sessizce yutulur; TCP zaten keepalive ile izlenir.
        """
        try:
            msg = (json.dumps(data) + "\n").encode("utf-8")
            if self.network.p2p_tcp_socket:
                self.network.p2p_tcp_socket.sendall(msg)
        except Exception:
            pass

    def _send_host_udp(self):
        """
        Host → Joiner: top konumu, skor ve host raket Y'sini UDP ile gönderir.

        Her karede çağrılır (hedef: 60 fps).
        Joiner UDP_PORT_JOINER (5002) portunu dinler.
        Paket kaybı tolere edilir; joiner en son gelen paketi kullanır.
        """
        if not self.network.p2p_udp_socket or not self.network.opponent_data:
            return
        data = {
            "action":   "game_state",
            "paddle_y": self.game_data.paddle1_y,
            "ball_x":   self.game_data.ball_x,
            "ball_y":   self.game_data.ball_y,
            "score1":   self.game_data.score1,
            "score2":   self.game_data.score2,
        }
        try:
            opp_ip = self.network.opponent_data.get("ip", "127.0.0.1")
            # Joiner UDP_PORT_JOINER (5002) dinler
            self.network.p2p_udp_socket.sendto(
                json.dumps(data).encode(), (opp_ip, config.UDP_PORT_JOINER)
            )
        except Exception:
            pass

    def _send_joiner_udp(self):
        """
        Joiner → Host: joiner raket Y konumunu UDP ile gönderir.

        Her karede çağrılır.  Host UDP_PORT (5001) portunu dinler.
        Yalnızca paddle2_y gönderilir; top ve skor joiner'da hesaplanmaz.
        """
        if not self.network.p2p_udp_socket or not self.network.opponent_data:
            return
        data = {"action": "paddle_update", "paddle_y": self.game_data.paddle2_y}
        try:
            opp_ip = self.network.opponent_data.get("ip", "127.0.0.1")
            # Host UDP_PORT (5001) dinler
            self.network.p2p_udp_socket.sendto(
                json.dumps(data).encode(), (opp_ip, config.UDP_PORT)
            )
        except Exception:
            pass

    # ── Ana dongu ─────────────────────────────────────────────────────────────

    def run(self):
        """
        Ana pygame döngüsünü çalıştırır.

        Her iterasyonda mevcut durum (self.state) okunur ve ilgili _run_*
        metodu çağrılır.  _run_* metodları kendi event polling ve clock.tick
        işlemlerini içerir; döngü tamamen çıktığında _cleanup() çalışır.

        Durum geçişleri _run_* metodları içinde self.state atanarak yapılır.
        """
        while self.running:
            s = self.state
            if   s == "NAME_INPUT":    self._run_name_input()
            elif s == "LOBBY":         self._run_lobby()
            elif s == "HOSTING":       self._run_hosting()
            elif s == "JOIN_INPUT":    self._run_join_input()
            elif s == "CONNECTING":    self._run_connecting()
            elif s == "COUNTDOWN":     self._run_countdown()
            elif s == "GAME":          self._run_game()
            elif s == "GAME_OVER":     self._run_game_over()
            elif s == "OPPONENT_LEFT": self._run_opponent_left()
        self._cleanup()

    # ── NAME INPUT ────────────────────────────────────────────────────────────
    # Oyuncu adını girer; ENTER'la LOBBY'ye geçer.

    def _run_name_input(self):
        self._draw_bg()
        self._draw_logo(y=120)

        card = pygame.Rect(config.WINDOW_WIDTH // 2 - 280, 268, 560, 158)
        self._draw_card(card, border_color=C_ACCENT)

        lbl = self.font_label.render("OYUNCU ADI", True, C_MUTED)
        self.screen.blit(lbl, (card.x + 22, card.y + 16))

        box = pygame.Rect(card.x + 18, card.y + 44, card.w - 36, 62)
        pygame.draw.rect(self.screen, (8, 12, 28), box, border_radius=10)
        pygame.draw.rect(self.screen, C_ACCENT, box, 2, border_radius=10)
        cursor   = "|" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
        name_srf = self.font_medium.render(self._name_input + cursor, True, C_WHITE)
        self.screen.blit(name_srf, (box.x + 14, box.y + 10))

        note = self.font_label.render("Maks 16 karakter", True, C_DIM)
        self.screen.blit(note, (card.x + 22, card.y + 120))

        hint = self.font_small.render("[ENTER]  Devam", True, C_GREEN)
        self._center(hint, 440)

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    name = self._name_input.strip() or "Player1"
                    self.player_name = name[:16]
                    pygame.display.set_caption(f"Pong P2P  |  {self.player_name}")
                    self.state = "LOBBY"
                elif event.key == pygame.K_BACKSPACE:
                    self._name_input = self._name_input[:-1]
                elif event.unicode and event.unicode.isprintable():
                    if len(self._name_input) < 16:
                        self._name_input += event.unicode

        self.clock.tick(60)

    # ── LOBBY ─────────────────────────────────────────────────────────────────
    # Ana menü: H → HOSTING, J → JOIN_INPUT, ESC → çıkış.
    # IP adresi ve oyuncu adı bilgi kartında gösterilir.

    def _run_lobby(self):
        self._draw_bg()
        self._draw_logo(y=58)

        ip = self._get_local_ip()
        info_card = pygame.Rect(config.WINDOW_WIDTH // 2 - 310, 176, 620, 58)
        self._draw_card(info_card, border_color=C_DIM)
        p_lbl = self.font_label.render("OYUNCU", True, C_MUTED)
        p_val = self.font_small.render(self.player_name, True, C_WHITE)
        i_lbl = self.font_label.render("SENIN IP ADRESIN", True, C_MUTED)
        i_val = self.font_small.render(ip, True, C_YELLOW)
        self.screen.blit(p_lbl, (info_card.x + 18, info_card.y + 5))
        self.screen.blit(p_val, (info_card.x + 18, info_card.y + 22))
        self.screen.blit(i_lbl, (info_card.x + 280, info_card.y + 5))
        self.screen.blit(i_val, (info_card.x + 280, info_card.y + 22))

        if self._connection_error:
            err = self.font_label.render(self._connection_error, True, C_RED)
            self._center(err, 252)

        bw, bh = 520, 74
        cx = config.WINDOW_WIDTH // 2 - bw // 2
        btn_host = pygame.Rect(cx, 288, bw, bh)
        btn_join = pygame.Rect(cx, 380, bw, bh)
        self._draw_key_button("H", "Host Ol  (Yeni oyun kur)",      btn_host, C_GREEN)
        self._draw_key_button("J", "Katil  (Mevcut oyuna baglani)", btn_join, C_ACCENT)

        bw_esc = 300
        btn_esc_lobby = pygame.Rect(config.WINDOW_WIDTH // 2 - bw_esc // 2, 478, bw_esc, 44)
        self._draw_key_button("ESC", "Cikis", btn_esc_lobby, C_RED)

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._connection_error = ""
                if btn_host.collidepoint(event.pos):
                    self._begin_hosting()
                elif btn_join.collidepoint(event.pos):
                    self._ip_input = ""
                    self._connection_error = ""
                    self.state = "JOIN_INPUT"
                elif btn_esc_lobby.collidepoint(event.pos):
                    self.running = False
            elif event.type == pygame.KEYDOWN:
                self._connection_error = ""
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_h:
                    self._begin_hosting()
                elif event.key == pygame.K_j:
                    self._ip_input = ""
                    self._connection_error = ""
                    self.state = "JOIN_INPUT"

        self.clock.tick(60)

    # ── HOSTING ───────────────────────────────────────────────────────────────
    # Arka planda TCP bağlantısı bekler (_accept thread).
    # Joiner bağlanınca exchange_names → COUNTDOWN geçişi.

    def _begin_hosting(self):
        self.is_host = True
        self._reset_network()
        self._connection_error = ""
        self.state = "HOSTING"
        net = self.network

        def _accept():
            try:
                net.setup_udp()      # Host UDP_PORT (5001) dinler
                net.host_tcp()       # Tek baglanti kabul et, sonra server socket kapanir
                if net is not self.network:
                    return
                net.opponent_data = {
                    "ip":   net.p2p_tcp_socket.getpeername()[0],
                    "port": config.TCP_PORT,
                }
                opponent_name = net.exchange_names(self.player_name)
                self._start_countdown(opponent_name)
            except Exception as e:
                if net is self.network and self.state == "HOSTING":
                    self._connection_error = self._fmt_error(e)
                    self.state = "LOBBY"

        threading.Thread(target=_accept, daemon=True).start()

    def _run_hosting(self):
        self._draw_bg()

        title = self.font_large.render("HOST MODU", True, C_GREEN)
        self._center(title, 60)
        instr = self.font_small.render("Arkadasina su IP adresini ver:", True, C_MUTED)
        self._center(instr, 156)

        ip      = self._get_local_ip()
        ip_card = pygame.Rect(config.WINDOW_WIDTH // 2 - 250, 194, 500, 90)
        self._draw_card(ip_card, border_color=C_YELLOW, radius=20)
        ip_srf = self.font_large.render(ip, True, C_YELLOW)
        self._center(ip_srf, ip_card.y + ip_card.h // 2 - ip_srf.get_height() // 2)

        port_txt = self.font_tiny.render(
            f"TCP: {config.TCP_PORT}   |   UDP Host: {config.UDP_PORT}   |   UDP Join: {config.UDP_PORT_JOINER}",
            True, C_DIM
        )
        self._center(port_txt, 298)

        dots     = "." * ((pygame.time.get_ticks() // 400) % 4)
        wait_srf = self.font_small.render(f"Baglanti bekleniyor{dots}", True, C_MUTED)
        self._center(wait_srf, 350)

        note = self.font_label.render("Ayni Wi-Fi aginda olmalisiniz", True, C_DIM)
        self._center(note, 402)

        bw_esc = 300
        btn_esc_hosting = pygame.Rect(config.WINDOW_WIDTH // 2 - bw_esc // 2, 440, bw_esc, 48)
        self._draw_key_button("ESC", "Iptal", btn_esc_hosting, C_RED)

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if btn_esc_hosting.collidepoint(event.pos):
                    self.network.close()
                    self.state = "LOBBY"
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.network.close()
                self.state = "LOBBY"

        self.clock.tick(60)

    # ── JOIN_INPUT ────────────────────────────────────────────────────────────
    # Host'un IP adresini giriş alanından alır.
    # ENTER / Bağlan butonu → _do_join() → CONNECTING.
    # ESC / Geri butonu → LOBBY.

    def _run_join_input(self):
        self._draw_bg()

        title = self.font_large.render("OYUNA KATIL", True, C_ACCENT)
        self._center(title, 60)
        instr = self.font_small.render("Host'un IP adresini gir:", True, C_MUTED)
        self._center(instr, 162)

        card = pygame.Rect(config.WINDOW_WIDTH // 2 - 310, 206, 620, 158)
        self._draw_card(card, border_color=C_ACCENT)

        lbl = self.font_label.render("HOST IP ADRESI", True, C_MUTED)
        self.screen.blit(lbl, (card.x + 22, card.y + 16))

        box = pygame.Rect(card.x + 18, card.y + 44, card.w - 36, 62)
        pygame.draw.rect(self.screen, (8, 12, 28), box, border_radius=10)
        pygame.draw.rect(self.screen, C_ACCENT, box, 2, border_radius=10)
        cursor = "|" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
        ip_srf = self.font_medium.render(self._ip_input + cursor, True, C_WHITE)
        self.screen.blit(ip_srf, (box.x + 14, box.y + 10))

        eg = self.font_label.render("Ornek: 192.168.1.42", True, C_DIM)
        self.screen.blit(eg, (card.x + 22, card.y + 120))

        # Tiklanabilir butonlar
        bw2 = 280
        cx  = config.WINDOW_WIDTH // 2
        btn_connect = pygame.Rect(cx - bw2 - 6, 398, bw2, 54)
        btn_back    = pygame.Rect(cx + 6,        398, bw2, 54)
        self._draw_key_button("ENTER", "Baglan", btn_connect, C_GREEN)
        self._draw_key_button("ESC",   "Geri",   btn_back,    C_RED)

        if self._connection_error:
            err = self.font_tiny.render(self._connection_error, True, C_RED)
            self._center(err, 468)

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if btn_connect.collidepoint(event.pos):
                    if self._ip_input.strip():
                        self._do_join()
                    else:
                        self._connection_error = "IP adresi bos! Ornek: 192.168.1.42"
                elif btn_back.collidepoint(event.pos):
                    self._connection_error = ""
                    self.state = "LOBBY"
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self._connection_error = ""
                    self.state = "LOBBY"
                elif event.key == pygame.K_RETURN:
                    if self._ip_input.strip():
                        self._do_join()
                    else:
                        self._connection_error = "IP adresi bos! Ornek: 192.168.1.42"
                elif event.key == pygame.K_BACKSPACE:
                    self._ip_input = self._ip_input[:-1]
                elif event.unicode and event.unicode.isprintable():
                    self._ip_input += event.unicode

        self.clock.tick(60)

    def _do_join(self):
        host_ip = self._ip_input.strip()
        self.is_host           = False
        self._connection_error = ""
        self._connecting_to    = host_ip
        self.state             = "CONNECTING"  # Hemen CONNECTING'e gec

        def _connect():
            net = None
            try:
                self._reset_network()
                net = self.network
                # ── Neden joiner 5002, host 5001 dinler? ────────────────────
                # Windows'ta SO_REUSEADDR ile iki ayrı soket aynı porta bağlanınca
                # OS gelen paketleri her ikisine de verebilir (davranış garanti değil).
                # Sonuç: joiner'ın gönderdiği "paddle_update" paketi kendi
                # soketine geri dönüyor; joiner bunu action=="game_state" diye
                # ayrıştırmaya çalışıyor, başarısız oluyor → top joiner'da
                # hiç hareket etmiyor.  Çözüm: iki farklı port.
                net.udp_port = config.UDP_PORT_JOINER   # Joiner 5002'yi dinler
                net.setup_udp()
                net.connect_tcp(host_ip, config.TCP_PORT)
                if net is not self.network:
                    return
                net.opponent_data  = {"ip": host_ip, "port": config.TCP_PORT}
                opponent_name      = net.exchange_names(self.player_name)
                self._start_countdown(opponent_name)
            except Exception as e:
                if net is None or net is self.network:
                    self._connection_error = self._fmt_error(e)
                    self.state = "JOIN_INPUT"

        threading.Thread(target=_connect, daemon=True).start()

    # ── CONNECTING ────────────────────────────────────────────────────────────
    # _do_join() thread'i arka planda bağlanmaya çalışırken gösterilen bekleme ekranı.
    # Başarıda thread COUNTDOWN'a geçer; hata durumunda JOIN_INPUT'a döner.

    def _run_connecting(self):
        self._draw_bg()

        title = self.font_large.render("BAGLANILIYOR", True, C_ACCENT)
        self._center(title, 196)

        dots = "." * ((pygame.time.get_ticks() // 300) % 5)
        anim = self.font_medium.render(dots, True, C_ACCENT)
        self._center(anim, 296)

        ip_s = self.font_small.render(f"Host: {self._connecting_to}", True, C_YELLOW)
        self._center(ip_s, 378)

        note = self.font_label.render(
            "3. bir kisi baglanmaya calisirsa [10061] Oyun dolu hatasi alir",
            True, C_DIM
        )
        self._center(note, 432)

        bw_esc = 300
        btn_esc_conn = pygame.Rect(config.WINDOW_WIDTH // 2 - bw_esc // 2, 460, bw_esc, 48)
        self._draw_key_button("ESC", "Iptal", btn_esc_conn, C_RED)

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if btn_esc_conn.collidepoint(event.pos):
                    self._reset_network()
                    self._connection_error = ""
                    self.state = "JOIN_INPUT"
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._reset_network()
                self._connection_error = ""
                self.state = "JOIN_INPUT"

        self.clock.tick(60)

    # ── COUNTDOWN ─────────────────────────────────────────────────────────────
    # 3 saniyelik geri sayım ekranı; süre dolunca start_game() → GAME.

    def _run_countdown(self):
        tcp_data = self.network.receive_tcp_message()
        if tcp_data and tcp_data.get("action") in ("quit", "disconnect"):
            self.state = "OPPONENT_LEFT"
            return

        elapsed   = time.time() - self._countdown_start
        remaining = COUNTDOWN_SEC - elapsed

        if remaining <= 0:
            self.game_logic.start_game()
            self.state = "GAME"
            return

        self.screen.fill((0, 0, 0))
        self.game_screen.draw(self.screen, self.game_data)

        ov = pygame.Surface((config.WINDOW_WIDTH, config.WINDOW_HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 148))
        self.screen.blit(ov, (0, 0))

        hazir = self.font_small.render("HAZIR OL!", True, C_MUTED)
        self._center(hazir, 228)

        num = self.font_title.render(str(int(remaining) + 1), True, C_YELLOW)
        self._center(num, 278)

        cx = config.WINDOW_WIDTH // 2
        p1 = self.font_small.render(self.game_data.player1_name, True, self.game_data.player1_color)
        vs = self.font_tiny.render("vs", True, C_MUTED)
        p2 = self.font_small.render(self.game_data.player2_name, True, self.game_data.player2_color)
        self.screen.blit(p1, (cx - p1.get_width() - 26, 440))
        self.screen.blit(vs, (cx - vs.get_width() // 2,   446))
        self.screen.blit(p2, (cx + 26, 440))

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._send_quit()
                self.running = False

        self.clock.tick(60)

    # ── GAME ──────────────────────────────────────────────────────────────────
    # Ana oyun döngüsü frame'i.
    #
    # Host:   BallPhysics.update() → gol/kazanma kontrolü → UDP gönder → UDP al (raket2)
    # Joiner: raket2 → UDP gönder → UDP al (top+skor+raket1)
    # Her ikisi: TCP → sohbet / game_over sinyali dinle.

    def _run_game(self):
        # TCP mesajlarini isle (chat + sinyal)
        tcp_data = self.network.receive_tcp_message()
        if tcp_data:
            action = tcp_data.get("action")
            if action == "chat":
                self.chat_handler.receive_message(tcp_data)
            elif action == "game_over":
                # Joiner host'tan son skoru ve kazananı alır (TCP garantili teslim)
                self.game_data.winner = tcp_data.get("winner", 2)
                self.game_data.score1 = tcp_data.get("score1", self.game_data.score1)
                self.game_data.score2 = tcp_data.get("score2", self.game_data.score2)
                self.state = "GAME_OVER"
                return
            elif action in ("quit", "disconnect"):
                # Rakip kasıtlı çıkış yaptı ("quit") veya bağlantısı koptu ("disconnect")
                self.state = "OPPONENT_LEFT"
                return

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                # Pencere kapatılıyor — rakibe haber ver, ardından çık
                self._send_quit()
                self.running = False
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                # Kasıtlı çıkış — rakibe quit sinyali gönder, lobiye dön
                self._send_quit()
                self._reset_network()
                self.state = "LOBBY"
                return
            self.game_screen.handle_input(event)

        now               = time.time()
        # goal_pause_active: golden hemen sonra GOAL_PAUSE_SEC boyunca True olur.
        # Bu sürede raket hareketi ve fizik durdurulur; "GOL!" yazısı ekranda kalır.
        goal_pause_active = now < self._goal_pause_until
        keys = pygame.key.get_pressed()

        # Saha sınırlarını yerel değişkenlere çek (döngü içinde sık kullanılıyor)
        ft = float(self.physics.field_top)      # Sahanın üst sınırı (piksel)
        fb = float(self.physics.field_bottom)   # Sahanın alt sınırı (piksel)
        ph = float(self.game_data.paddle_height)
        ps = self.game_data.paddle_speed

        # ═══════════════════════════════════════════════════════════════════
        # HOST DALI — Fizik yetkisi sadece host'ta
        # ═══════════════════════════════════════════════════════════════════
        if self.is_host:
            if not goal_pause_active:
                # Raket hareketi: saha sınırları dışına çıkmayı max/min ile engelle
                if keys[pygame.K_UP]:
                    self.game_data.paddle1_y = max(ft, self.game_data.paddle1_y - ps)
                if keys[pygame.K_DOWN]:
                    self.game_data.paddle1_y = min(fb - ph, self.game_data.paddle1_y + ps)

                # Fizik güncellemesi: True döndürürse bu karede gol atıldı
                if self.physics.update():
                    # GOAL_PAUSE_SEC saniye sonrasına kadar oyunu dondur
                    self._goal_pause_until = now + GOAL_PAUSE_SEC

                # Kazanma kontrolü: eşiğe ulaşıldıysa joiner'a TCP ile bildir.
                # TCP kullanılıyor çünkü UDP'de paket kaybı olursa joiner
                # "oyun bitti" sinyalini hiç alamayabilir.
                if self.game_logic.check_win_condition():
                    self._send_tcp({
                        "action": "game_over",
                        "winner": self.game_data.winner,
                        "score1": self.game_data.score1,
                        "score2": self.game_data.score2,
                    })
                    self.state = "GAME_OVER"
                    return

                # Her frame topun hız basamağını güncelle (gol sonrası hızlanma)
                self.game_logic.update_ball_speed()

            # UDP gönder/al: goal_pause aktif olsa bile pozisyonu paylaşmaya devam et;
            # joiner pause süresinde bile güncel konumu ekranda görmeli.
            self._send_host_udp()
            udp = self.network.receive_game_state_udp()
            if udp and udp.get("action") == "paddle_update":
                # Joiner'ın raket Y'sini güncelle (joiner kendi raketini kontrol eder)
                self.game_data.paddle2_y = udp.get("paddle_y", self.game_data.paddle2_y)

        # ═══════════════════════════════════════════════════════════════════
        # JOINER DALI — Sadece kendi raketini kontrol eder; her şey host'tan gelir
        # ═══════════════════════════════════════════════════════════════════
        else:
            if not goal_pause_active:
                # Joiner yalnızca paddle2_y'yi kontrol eder; top joiner'da hesaplanmaz
                if keys[pygame.K_UP]:
                    self.game_data.paddle2_y = max(ft, self.game_data.paddle2_y - ps)
                if keys[pygame.K_DOWN]:
                    self.game_data.paddle2_y = min(fb - ph, self.game_data.paddle2_y + ps)

            self._send_joiner_udp()
            udp = self.network.receive_game_state_udp()
            if udp and udp.get("action") == "game_state":
                # ── Joiner tarafında gol tespiti ─────────────────────────
                # Joiner fizik çalıştırmaz; golü "skor toplamı arttı mı?" ile anlar.
                # UDP paket kaybı olsa da skor hiç azalmayacağından bu kontrol güvenlidir.
                prev_total = self.game_data.score1 + self.game_data.score2

                # Host'tan gelen güncel durumu uygula
                self.game_data.paddle1_y = udp.get("paddle_y", self.game_data.paddle1_y)
                self.game_data.ball_x    = udp.get("ball_x",   self.game_data.ball_x)
                self.game_data.ball_y    = udp.get("ball_y",   self.game_data.ball_y)
                self.game_data.score1    = udp.get("score1",   self.game_data.score1)
                self.game_data.score2    = udp.get("score2",   self.game_data.score2)

                if self.game_data.score1 + self.game_data.score2 > prev_total:
                    # Gol atıldı → joiner da kendi goal_pause'unu başlat
                    self._goal_pause_until = time.time() + GOAL_PAUSE_SEC

                    # Host _reset_ball() ile her iki raketi de merkeze alır,
                    # ancak UDP paketi yalnızca paddle1_y'yi taşır.
                    # Joiner kendi raketini (paddle2_y) burada hesaplayarak merkeze alır.
                    centered = (self.physics.field_top + self.physics.field_bottom
                                - self.game_data.paddle_height) / 2.0
                    self.game_data.paddle2_y = centered

        # Ciz
        self.screen.fill((0, 0, 0))
        self.game_screen.draw(self.screen, self.game_data)

        if goal_pause_active:
            gw  = config.GAME_AREA_WIDTH
            cy  = config.WINDOW_HEIGHT // 2
            gol = pygame.Surface((gw, 80), pygame.SRCALPHA)
            gol.fill((0, 0, 0, 180))
            self.screen.blit(gol, (0, cy - 40))
            gs = self.font_medium.render("GOL!", True, C_YELLOW)
            self.screen.blit(gs, (gw // 2 - gs.get_width() // 2, cy - gs.get_height() // 2))

        pygame.display.flip()
        self.clock.tick(config.GAME_FPS)

    # ── GAME OVER ─────────────────────────────────────────────────────────────
    # Kazanan, final skor, ve üç senaryo yönetimi:
    #   A) Normal     : [R] Tekrar Oyna  [L] Lobi  [ESC] Çıkış
    #   B) Rakip R'ye bastı: Yanıp sönen bildirim kartı + aynı butonlar (kayarak)
    #   C) Ben R'ye bastım : "Rakip bekleniyor..." + [L] [ESC]
    # Her iki taraf rematch_accept gönderince → COUNTDOWN.

    def _run_game_over(self):
        tcp_data = self.network.receive_tcp_message()
        if tcp_data:
            action = tcp_data.get("action")
            if action == "rematch_accept":
                self._opponent_wants_rematch = True
            elif action in ("quit", "disconnect"):
                # Rakip oyun bitti ekranındayken çıktı
                self.state = "OPPONENT_LEFT"
                return

        if self._i_want_rematch and self._opponent_wants_rematch:
            opp = self.game_data.player2_name if self.is_host else self.game_data.player1_name
            self._start_countdown(opp)
            return

        self._draw_bg()

        ov_t = self.font_large.render("OYUN BITTI", True, C_WHITE)
        self._center(ov_t, 50)

        i_won = (self.game_data.winner == 1 and     self.is_host) or \
                (self.game_data.winner == 2 and not self.is_host)
        if i_won:
            res_srf   = self.font_title.render("KAZANDIN!", True, C_GREEN)
            res_color = C_GREEN
        else:
            res_srf   = self.font_title.render("RAKIP KAZANDI", True, C_RED)
            res_color = C_RED
        self._center(res_srf, 136)

        # Skor kutusu
        sc_card = pygame.Rect(config.WINDOW_WIDTH // 2 - 170, 254, 340, 96)
        self._draw_card(sc_card, border_color=res_color, radius=22)
        sc_srf = self.font_title.render(
            f"{self.game_data.score1}  -  {self.game_data.score2}", True, C_WHITE
        )
        self._center(sc_srf, sc_card.y + 12)
        p1n = self.font_label.render(self.game_data.player1_name[:12], True, self.game_data.player1_color)
        p2n = self.font_label.render(self.game_data.player2_name[:12], True, self.game_data.player2_color)
        self.screen.blit(p1n, (sc_card.x + 14, sc_card.bottom - 22))
        self.screen.blit(p2n, (sc_card.right - p2n.get_width() - 14, sc_card.bottom - 22))

        bw = 540
        cx = config.WINDOW_WIDTH // 2 - bw // 2

        # ── Rematch bölgesi (skor kutusunun altindan baslar: y=364) ────────────
        # Her senaryoda butunlere 14px bosluk birakarak dizilir; cakisma olmaz.
        #
        #  Senaryo A — hic kimse R'ye basmamis:
        #    R butonu    : y=364  h=62 → alt=426
        #    L butonu    : y=442  h=54 → alt=496
        #    ESC butonu  : y=508  h=48 → alt=556
        #
        #  Senaryo B — rakip R'ye bastı, ben basmadam (bildirim var):
        #    Bildirim    : y=364  h=50 → alt=414
        #    R butonu    : y=428  h=62 → alt=490
        #    L butonu    : y=506  h=54 → alt=560
        #    ESC butonu  : y=574  h=48 → alt=622
        #
        #  Senaryo C — ben R'ye bastim, rakip bekle mesaji:
        #    Bekle yazisi: y=374
        #    L butonu    : y=442  h=54 → alt=496
        #    ESC butonu  : y=508  h=48 → alt=556
        # ───────────────────────────────────────────────────────────────────────

        ZONE_TOP = 364   # skor kutusunun hemen altindan baslayan bölge

        btn_rematch = None

        if self._opponent_wants_rematch and not self._i_want_rematch:
            # Senaryo B
            opp_name   = self.game_data.player2_name if self.is_host else self.game_data.player1_name
            notif_card = pygame.Rect(config.WINDOW_WIDTH // 2 - 260, ZONE_TOP, 520, 50)
            self._draw_card(notif_card, border_color=C_YELLOW, radius=12)
            pulse       = (pygame.time.get_ticks() // 600) % 2 == 0
            notif_color = C_YELLOW if pulse else (200, 150, 30)
            notif_s     = self.font_small.render(
                f"{opp_name[:14]} tekrar oynamak istiyor!", True, notif_color
            )
            self._center(notif_s, notif_card.y + 12)
            btn_r_y   = ZONE_TOP + 50 + 14          # = 428
            btn_l_y   = btn_r_y  + 62 + 14          # = 504
            btn_esc_y = btn_l_y  + 54 + 14          # = 572

        elif self._i_want_rematch:
            # Senaryo C
            wait_s = self.font_small.render("Rakip bekleniyor...", True, C_YELLOW)
            self._center(wait_s, ZONE_TOP + 10)
            btn_r_y   = None                         # gizli
            btn_l_y   = ZONE_TOP + 78               # = 442
            btn_esc_y = btn_l_y  + 54 + 14          # = 510

        else:
            # Senaryo A
            btn_r_y   = ZONE_TOP                    # = 364
            btn_l_y   = ZONE_TOP + 62 + 16          # = 442
            btn_esc_y = btn_l_y  + 54 + 14          # = 510

        if btn_r_y is not None:
            btn_rematch = pygame.Rect(cx, btn_r_y, bw, 62)
            self._draw_key_button("R", "Tekrar Oyna  (her iki oyuncu basmali)", btn_rematch, C_GREEN)

        btn_lobby = pygame.Rect(cx, btn_l_y,   bw, 54)
        btn_exit  = pygame.Rect(cx, btn_esc_y, bw, 48)
        self._draw_key_button("L",   "Lobiye Don", btn_lobby, C_ACCENT)
        self._draw_key_button("ESC", "Cikis",      btn_exit,  C_RED)

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._send_quit()
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if btn_rematch and btn_rematch.collidepoint(event.pos) and not self._i_want_rematch:
                    self._i_want_rematch = True
                    self._send_tcp({"action": "rematch_accept"})
                elif btn_lobby.collidepoint(event.pos):
                    self._send_quit()
                    self._reset_network()
                    self.state = "LOBBY"
                elif btn_exit.collidepoint(event.pos):
                    self._send_quit()
                    self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r and not self._i_want_rematch:
                    self._i_want_rematch = True
                    self._send_tcp({"action": "rematch_accept"})
                elif event.key == pygame.K_l:
                    self._send_quit()
                    self._reset_network()
                    self.state = "LOBBY"
                elif event.key == pygame.K_ESCAPE:
                    self._send_quit()
                    self.running = False

        self.clock.tick(60)

    def _run_opponent_left(self):
        """Rakip oyundan ayrildiginda kullanici onayi isteyen ekran."""
        self._draw_bg()

        title = self.font_title.render("RAKIP OYUNDAN AYRILDI", True, C_RED)
        self._center(title, 150)

        card = pygame.Rect(config.WINDOW_WIDTH // 2 - 320, 250, 640, 210)
        self._draw_card(card, border_color=C_RED, radius=22)

        msg1 = self.font_small.render("Diger oyuncu baglantiyi kapatti veya lobiye dondu.", True, C_WHITE)
        msg2 = self.font_tiny.render("Tamam diyerek ana menuye donebilirsin.", True, C_MUTED)
        self._center(msg1, card.y + 48)
        self._center(msg2, card.y + 92)

        btn_ok = pygame.Rect(config.WINDOW_WIDTH // 2 - 190, card.y + 140, 380, 54)
        self._draw_key_button("ENTER", "Tamam", btn_ok, C_GREEN)

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if btn_ok.collidepoint(event.pos):
                    self._reset_network()
                    self.state = "LOBBY"
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_l):
                    self._reset_network()
                    self.state = "LOBBY"

        self.clock.tick(60)
    # ── Temizlik ──────────────────────────────────────────────────────────────

    def _cleanup(self):
        """
        Ağ soketlerini kapatır, pygame'i sonlandırır ve programdan çıkar.

        run() döngüsü sona erdiğinde (self.running = False) otomatik çağrılır.
        Daemon thread'ler zaten süreci takip ettiğinden ayrıca join gerekmez.
        """
        self.network.close()
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    pygame.init()
    client = GameClient()
    client.run()
