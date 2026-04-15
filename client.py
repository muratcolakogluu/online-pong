"""
============================================================================
client.py - Pong Oyunu Client Tarafı
============================================================================

Sorumluluğu:
1. Pygame ile oyun ekranını yönetmek
2. Kullanıcı inputu almak
3. Server'dan state almak (şu an mock)
4. Oyun durumunu ekrana çizmek

Mimarı: Katmanlı (Layered) - Her sınıf bir sorumluluğu var
============================================================================
"""

import pygame
import sys
from typing import Tuple, Dict
import json

# Local imports
import config


# ============================================================================
# OYUN DURUMU YAPILANDIRMASI
# ============================================================================

class GameState:
    """
    Server'dan alacağımız oyun durumunu temsil eder.

    Şu an mock data ile çalışıyor, ama server gerçek veriler gönderdiğinde
    bu yapı aynı kalacak. Network kodun detayı değişirse, bu yapı değişmez.

    Öğrenilen Ağ Kavramı:
    - Serialization/Deserialization (JSON'a dönüştürme)
    """

    def __init__(self):
        # Sol oyuncu (Player 1)
        self.paddle_left_y = config.PADDLE_START_Y

        # Sağ oyuncu (Player 2)
        self.paddle_right_y = config.PADDLE_START_Y

        # Top pozisyonu
        self.ball_x = config.BALL_START_X
        self.ball_y = config.BALL_START_Y

        # Skorlar
        self.score_left = 0
        self.score_right = 0

        # Oyun durumu
        self.is_running = True

    def update_from_state(self, data: Dict):
        """
        Server'dan gelen JSON data'yı parse edip state güncellemesi.

        Örnek gelen data:
        {
            "paddle_left_y": 250,
            "paddle_right_y": 280,
            "ball_x": 400,
            "ball_y": 300,
            "score_left": 2,
            "score_right": 1
        }
        """
        try:
            self.paddle_left_y = data.get("paddle_left_y", self.paddle_left_y)
            self.paddle_right_y = data.get("paddle_right_y", self.paddle_right_y)
            self.ball_x = data.get("ball_x", self.ball_x)
            self.ball_y = data.get("ball_y", self.ball_y)
            self.score_left = data.get("score_left", self.score_left)
            self.score_right = data.get("score_right", self.score_right)
        except Exception as e:
            print(f"❌ State update hatası: {e}")


# ============================================================================
# NETWORK HANDLER - SUNUCU BAĞLANTISI
# ============================================================================

class NetworkHandler:
    """
    Server'la iletişimi yönetir.

    Şu an MOCK (Test) mode'da:
    - Gerçek server bağlantısı yok
    - Mock data döndürüyoruz

    İleride açılacaklar:
    - TCP socket oluşturma
    - UDP socket oluşturma
    - Bağlantı yönetimi
    - Error handling

    Öğrenilen Ağ Kavramları:
    - Socket programming
    - Client-Server mimarisi
    - Network I/O
    """

    def __init__(self, host: str = config.SERVER_HOST,
                 port: int = config.SERVER_PORT,
                 protocol: str = config.PROTOCOL):
        self.host = host
        self.port = port
        self.protocol = protocol
        self.connected = False
        self.socket = None

        if config.DEBUG:
            print(f"🌐 NetworkHandler başlatıldı: {protocol}/{host}:{port}")

        # Şu an herhangi bir bağlantı açmıyoruz (mock mode)
        self.connected = False

    def connect(self):
        """
        Server'a bağlanma (şu an mock).

        SONRA YAPILACAKLAR:
        ```python
        import socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        self.connected = True
        ```
        """
        if config.SHOW_NETWORK_DEBUG:
            print(f"🔗 Mock bağlantı: {self.host}:{self.port}")
        self.connected = True

    def send_input(self, input_data: Dict):
        """
        Oyuncunun input'unu (paddle hareketi) server'a gönder.

        Input örneği:
        {
            "paddle_y": 250,
            "player_id": 1
        }

        SONRA YAPILACAKLAR:
        - Gerçek socket.send() çağrısı
        - Error handling
        """
        if not self.connected:
            return

        try:
            json_data = json.dumps(input_data)
            if config.SHOW_NETWORK_DEBUG:
                print(f"📤 Input gönderiliyor: {json_data}")
            # self.socket.send(json_data.encode())
        except Exception as e:
            print(f"❌ Send hatası: {e}")

    def receive_state(self) -> Dict:
        """
        Server'dan oyun durumunu al.

        SONRA YAPILACAKLAR:
        - Gerçek socket.recv() çağrısı
        - JSON parse
        - Timeout handling

        Şu an mock data döndürüyoruz.
        """
        if not self.connected:
            return self._get_mock_state()

        try:
            # self.data = self.socket.recv(config.BUFFER_SIZE)
            # return json.loads(self.data.decode())
            return self._get_mock_state()
        except Exception as e:
            print(f"❌ Receive hatası: {e}")
            return self._get_mock_state()

    def _get_mock_state(self) -> Dict:
        """
        Test amaçlı mock oyun durumu.
        Bu, gerçek server yapılıncaya kadar kullanılır.
        """
        return {
            "paddle_left_y": config.PADDLE_START_Y,
            "paddle_right_y": config.PADDLE_START_Y,
            "ball_x": config.BALL_START_X,
            "ball_y": config.BALL_START_Y,
            "score_left": 0,
            "score_right": 0
        }

    def disconnect(self):
        """Sunucudan bağlantıyı kes."""
        if self.socket:
            self.socket.close()
        self.connected = False
        if config.SHOW_NETWORK_DEBUG:
            print("🔌 Bağlantı kapatıldı")


# ============================================================================
# INPUT HANDLER - KLAVYE GİRİŞİ
# ============================================================================

class InputHandler:
    """
    Kullanıcı inputunu (keyboard) yönetir.

    Sorumluluğu:
    - Hangi tuşların basıldığını algıla
    - Paddle'ın hareket yönünü belirle
    - Input'u server'a göndermek üzere hazırla

    Öğrenilen Kavram:
    - Event-driven programming
    - Client-side input validation
    """

    def __init__(self, player_id: int = 1):
        self.player_id = player_id
        self.paddle_y = config.PADDLE_START_Y

        # Hangi tuşlara basılı olduğu
        self.keys_pressed = {
            "up": False,
            "down": False
        }

    def handle_events(self) -> bool:
        """
        Pygame event'lerini işle.

        Return: Oyun devam ediyorsa True, çıkmak istenirse False
        """
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP or event.key == pygame.K_w:
                    self.keys_pressed["up"] = True
                elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                    self.keys_pressed["down"] = True

            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_UP or event.key == pygame.K_w:
                    self.keys_pressed["up"] = False
                elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                    self.keys_pressed["down"] = False

        return True

    def get_input_data(self) -> Dict:
        """
        Şu andaki input'u bir dict'e dönüştür (server'a göndermek için).

        Return örneği:
        {
            "player_id": 1,
            "move_up": False,
            "move_down": True
        }
        """
        return {
            "player_id": self.player_id,
            "move_up": self.keys_pressed["up"],
            "move_down": self.keys_pressed["down"]
        }


# ============================================================================
# GAME DISPLAY - PYGAME RENDERING
# ============================================================================

class GameDisplay:
    """
    Tüm oyun öğelerini ekrana çizer.

    Sorumluluğu:
    - Pygame surface'ını yönetmek
    - Paddle, ball, skor vs çizmek
    - Ekranı güncellemek (refresh)

    Mimarı Not:
    - Hiç oyun lojiği içermez
    - Sadece GameState'i alıp çizer
    - Network bilgisi yoktur
    """

    def __init__(self, width: int = config.WINDOW_WIDTH,
                 height: int = config.WINDOW_HEIGHT):
        self.width = width
        self.height = height

        # Pygame screen
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption(config.WINDOW_TITLE)

        # Font
        self.font_large = pygame.font.Font(None, 72)
        self.font_small = pygame.font.Font(None, 36)

        # Saat
        self.clock = pygame.time.Clock()
        self.fps = config.FPS
        self.frame_count = 0

    def draw_background(self):
        """Arka planı çiz (siyah)."""
        self.screen.fill(config.BACKGROUND_COLOR)

    def draw_center_line(self):
        """Ortada çizgi çiz (dekoratif)."""
        for y in range(0, self.height, 20):
            pygame.draw.line(
                self.screen,
                config.WHITE,
                (self.width // 2, y),
                (self.width // 2, y + 10),
                2
            )

    def draw_paddle(self, x: float, y: float, color: Tuple[int, int, int] = config.WHITE):
        """
        Paddle'ı çiz.

        Args:
            x: Paddle'ın x koordinatı (piksel)
            y: Paddle'ın y koordinatı (piksel)
            color: Renk (RGB tuple)
        """
        pygame.draw.rect(
            self.screen,
            color,
            (x, y, config.PADDLE_WIDTH, config.PADDLE_HEIGHT),
            0  # 0 = dolu dikdörtgen
        )

    def draw_ball(self, x: float, y: float, color: Tuple[int, int, int] = config.WHITE):
        """
        Top'u çiz.

        Args:
            x: Top'un merkez x koordinatı
            y: Top'un merkez y koordinatı
            color: Renk (RGB tuple)
        """
        pygame.draw.circle(
            self.screen,
            color,
            (int(x), int(y)),
            config.BALL_SIZE
        )

    def draw_score(self, left_score: int, right_score: int):
        """
        Skorları ekranın üstüne çiz.

        Args:
            left_score: Sol oyuncunun skoru
            right_score: Sağ oyuncunun skoru
        """
        # Sol skor
        left_text = self.font_large.render(
            str(left_score),
            True,
            config.TEXT_COLOR
        )
        self.screen.blit(
            left_text,
            (self.width // 4 - left_text.get_width() // 2, 30)
        )

        # Sağ skor
        right_text = self.font_large.render(
            str(right_score),
            True,
            config.TEXT_COLOR
        )
        self.screen.blit(
            right_text,
            (3 * self.width // 4 - right_text.get_width() // 2, 30)
        )

    def draw_debug_info(self, fps: int, connected: bool):
        """
        Debug bilgisi göster (FPS, bağlantı durumu).

        Args:
            fps: Şu andaki FPS
            connected: Server'a bağlı mı?
        """
        if not config.SHOW_FPS and not config.DEBUG:
            return

        debug_text = f"FPS: {fps} | Connected: {connected}"
        text = self.font_small.render(debug_text, True, config.GREEN)
        self.screen.blit(text, (10, self.height - 40))

    def draw_all(self, game_state: GameState, fps: int, connected: bool):
        """
        Ekranın tümünü çiz (ana çizim fonksiyonu).

        Bu fonksiyon sırada:
        1. Arka plan temizle
        2. Tüm nesneleri çiz
        3. Ekranı güncelle

        Args:
            game_state: Oyun durumu nesnesi
            fps: Şu andaki FPS (debug için)
            connected: Server bağlantı durumu
        """
        # 1. Temizle
        self.draw_background()
        self.draw_center_line()

        # 2. Nesneleri çiz
        self.draw_paddle(
            config.PADDLE_LEFT_X,
            game_state.paddle_left_y
        )
        self.draw_paddle(
            config.PADDLE_RIGHT_X,
            game_state.paddle_right_y
        )
        self.draw_ball(
            game_state.ball_x,
            game_state.ball_y
        )
        self.draw_score(
            game_state.score_left,
            game_state.score_right
        )
        self.draw_debug_info(fps, connected)

        # 3. Güncelle
        pygame.display.flip()

        self.frame_count += 1

    def tick(self):
        """FPS'i kontrol et ve frame süresini al."""
        self.clock.tick(self.fps)

    def get_fps(self) -> int:
        """Şu andaki FPS'i al."""
        return int(self.clock.get_fps())


# ============================================================================
# MAIN GAME CLIENT
# ============================================================================

class GameClient:
    """
    Ana oyun istemcisi. Tüm bileşenleri (network, display, input) koordine eder.

    Tasarım Prensibi:
    - Bu sınıf sadece bileşenleri bir araya getirir
    - Her bileşen kendi işini yapar
    - Bu sınıf "orkestratör"dür

    Game Loop:
    1. Input'u oku
    2. Input'u server'a gönder
    3. Server'dan state al
    4. State'i ekrana çiz
    5. Tekrar 1'e git
    """

    def __init__(self, player_id: int = 1):
        # Bileşenleri başlat
        self.network = NetworkHandler()
        self.display = GameDisplay()
        self.input = InputHandler(player_id=player_id)
        self.game_state = GameState()

        # Oyun durumu
        self.running = True
        self.connected = False

        if config.DEBUG:
            print("✅ GameClient başlatıldı")

    def initialize(self):
        """
        Oyunun başlangıç ayarlarını yap.

        SONRA YAPILACAKLAR:
        - Server'a bağlan
        - Player ID'ni gönder
        - İlk state'i al
        """
        if config.DEBUG:
            print("🚀 Oyun başlatılıyor...")

        # Ağa bağlan (şu an mock)
        self.network.connect()
        self.connected = self.network.connected

        if config.DEBUG:
            print(f"📡 Bağlantı durumu: {self.connected}")

    def run(self):
        """
        Ana oyun loopü. Oyun bitene kadar çalışır.

        Sıra:
        1. Olayları işle (input)
        2. Input'u gönder
        3. State'i al
        4. Çiz
        5. Tekrar
        """
        self.initialize()

        while self.running:
            # 1. Input'u oku ve olayları işle
            self.running = self.input.handle_events()

            # 2. Input'u server'a gönder
            input_data = self.input.get_input_data()
            self.network.send_input(input_data)

            # 3. Server'dan state al
            state_data = self.network.receive_state()
            self.game_state.update_from_state(state_data)

            # 4. Ekrana çiz
            fps = self.display.get_fps()
            self.display.draw_all(
                self.game_state,
                fps,
                self.connected
            )

            # 5. FPS kontrolü
            self.display.tick()

        self.cleanup()

    def cleanup(self):
        """Oyun bitirme işlemleri."""
        self.network.disconnect()
        pygame.quit()
        print("👋 Oyun sonlandırıldı")
        sys.exit()


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    # Pygame başlat
    pygame.init()

    # Oyunu çalıştır
    client = GameClient(player_id=1)
    client.run()