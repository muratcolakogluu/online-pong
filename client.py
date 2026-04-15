"""
============================================================================
client.py - Pong Oyunu Client Tarafı (GERÇEK BAĞLANTI EKLENDİ)
============================================================================
"""

import pygame
import sys
import socket
import json
from typing import Tuple, Dict

# Local imports
import config

# ============================================================================
# OYUN DURUMU YAPILANDIRMASI
# ============================================================================

class GameState:
    def __init__(self):
        self.paddle_left_y = config.PADDLE_START_Y
        self.paddle_right_y = config.PADDLE_START_Y
        self.ball_x = config.BALL_START_X
        self.ball_y = config.BALL_START_Y
        self.score_left = 0
        self.score_right = 0
        self.is_running = True

    def update_from_state(self, data: Dict):
        try:
            self.paddle_left_y = data.get("paddle_left_y", self.paddle_left_y)
            self.paddle_right_y = data.get("paddle_right_y", self.paddle_right_y)
            self.ball_x = data.get("ball_x", self.ball_x)
            self.ball_y = data.get("ball_y", self.ball_y)
            self.score_left = data.get("score_left", self.score_left)
            self.score_right = data.get("score_right", self.score_right)
        except Exception as e:
            pass # Saniyede 60 kere hata basmasın diye pass geçiyoruz

# ============================================================================
# NETWORK HANDLER - SUNUCU BAĞLANTISI
# ============================================================================

class NetworkHandler:
    def __init__(self, host: str = config.SERVER_HOST,
                 port: int = config.SERVER_PORT,
                 protocol: str = config.PROTOCOL):
        self.host = host
        self.port = port
        self.protocol = protocol
        self.connected = False
        self.socket = None

        # TCP yapışmasını çözmek için gelen verileri biriktirdiğimiz yer
        self.buffer = ""

        if config.DEBUG:
            print(f"🌐 NetworkHandler başlatıldı: {protocol}/{host}:{port}")

    def connect(self):
        """Gerçek TCP soketi ile Server'a bağlanma"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            # Soketi non-blocking yapmıyoruz ki recv donmasın, timeout veriyoruz
            self.socket.settimeout(0.02)
            self.connected = True
            print(f"🔗 BAŞARILI: Gerçek sunucuya bağlanıldı ({self.host}:{self.port})")
        except Exception as e:
            print(f"❌ BAĞLANTI HATASI: Sunucu açık mı? Hata: {e}")
            self.connected = False

    def send_input(self, input_data: Dict):
        """Kullanıcı input'unu server'a gönder"""
        if not self.connected:
            return

        try:
            # TCP yapışmasını önlemek için mesajın sonuna \n koyup yolluyoruz
            paket = {"tip": "INPUT", "veri": input_data}
            json_data = json.dumps(paket) + "\n"
            self.socket.sendall(json_data.encode('utf-8'))
        except Exception as e:
            print(f"❌ Send hatası: {e}")
            self.connected = False

    def receive_state(self) -> Dict:
        """Server'dan gelen oyun durumunu al ve en güncelini döndür"""
        if not self.connected:
            return self._get_mock_state()

        try:
            data = self.socket.recv(4096).decode('utf-8')
            if not data:
                print("❌ Server bağlantıyı kopardı.")
                self.connected = False
                return self._get_mock_state()

            self.buffer += data

            en_guncel_veri = None

            # Gelen veriyi \n karakterine göre parçala
            while '\n' in self.buffer:
                mesaj, self.buffer = self.buffer.split('\n', 1)
                try:
                    paket = json.loads(mesaj)
                    if paket.get("tip") == "STATE":
                        en_guncel_veri = paket.get("veri")
                except json.JSONDecodeError:
                    continue

            if en_guncel_veri:
                return en_guncel_veri
            else:
                return self._get_mock_state()

        except socket.timeout:
            # Saniyenin 60'ta 1'inde veri gelmezse beklemeyi bırak
            return self._get_mock_state()
        except BlockingIOError:
            return self._get_mock_state()
        except Exception as e:
            return self._get_mock_state()

    def _get_mock_state(self) -> Dict:
        return {
            "paddle_left_y": config.PADDLE_START_Y,
            "paddle_right_y": config.PADDLE_START_Y,
            "ball_x": config.BALL_START_X,
            "ball_y": config.BALL_START_Y,
            "score_left": 0,
            "score_right": 0
        }

    def disconnect(self):
        if self.socket:
            self.socket.close()
        self.connected = False
        if config.SHOW_NETWORK_DEBUG:
            print("🔌 Bağlantı kapatıldı")

# ============================================================================
# INPUT HANDLER - KLAVYE GİRİŞİ
# ============================================================================

class InputHandler:
    def __init__(self, player_id: int = 1):
        self.player_id = player_id
        self.keys_pressed = {"up": False, "down": False}

    def handle_events(self) -> bool:
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
        return {
            "player_id": self.player_id,
            "move_up": self.keys_pressed["up"],
            "move_down": self.keys_pressed["down"]
        }

# ============================================================================
# GAME DISPLAY - PYGAME RENDERING
# ============================================================================

class GameDisplay:
    def __init__(self, width: int = config.WINDOW_WIDTH, height: int = config.WINDOW_HEIGHT):
        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption(config.WINDOW_TITLE)
        self.font_large = pygame.font.Font(None, 72)
        self.font_small = pygame.font.Font(None, 36)
        self.clock = pygame.time.Clock()
        self.fps = config.FPS

    def draw_background(self):
        self.screen.fill(config.BACKGROUND_COLOR)

    def draw_center_line(self):
        for y in range(0, self.height, 20):
            pygame.draw.line(self.screen, config.WHITE, (self.width // 2, y), (self.width // 2, y + 10), 2)

    def draw_paddle(self, x: float, y: float, color: Tuple[int, int, int] = config.WHITE):
        pygame.draw.rect(self.screen, color, (x, y, config.PADDLE_WIDTH, config.PADDLE_HEIGHT), 0)

    def draw_ball(self, x: float, y: float, color: Tuple[int, int, int] = config.WHITE):
        pygame.draw.circle(self.screen, color, (int(x), int(y)), config.BALL_SIZE)

    def draw_score(self, left_score: int, right_score: int):
        left_text = self.font_large.render(str(left_score), True, config.TEXT_COLOR)
        self.screen.blit(left_text, (self.width // 4 - left_text.get_width() // 2, 30))
        right_text = self.font_large.render(str(right_score), True, config.TEXT_COLOR)
        self.screen.blit(right_text, (3 * self.width // 4 - right_text.get_width() // 2, 30))

    def draw_debug_info(self, fps: int, connected: bool):
        if not config.SHOW_FPS and not config.DEBUG:
            return
        text = self.font_small.render(f"FPS: {fps} | Connected: {connected}", True, config.GREEN)
        self.screen.blit(text, (10, self.height - 40))

    def draw_all(self, game_state: GameState, fps: int, connected: bool):
        self.draw_background()
        self.draw_center_line()
        self.draw_paddle(config.PADDLE_LEFT_X, game_state.paddle_left_y)
        self.draw_paddle(config.PADDLE_RIGHT_X, game_state.paddle_right_y)
        self.draw_ball(game_state.ball_x, game_state.ball_y)
        self.draw_score(game_state.score_left, game_state.score_right)
        self.draw_debug_info(fps, connected)
        pygame.display.flip()

    def tick(self):
        self.clock.tick(self.fps)

    def get_fps(self) -> int:
        return int(self.clock.get_fps())

# ============================================================================
# MAIN GAME CLIENT
# ============================================================================

class GameClient:
    def __init__(self, player_id: int = 1):
        self.network = NetworkHandler()
        self.display = GameDisplay()
        self.input = InputHandler(player_id=player_id)
        self.game_state = GameState()
        self.running = True
        self.connected = False

    def initialize(self):
        self.network.connect()
        self.connected = self.network.connected

    def run(self):
        self.initialize()
        while self.running:
            self.running = self.input.handle_events()

            # Inputu gönder
            input_data = self.input.get_input_data()
            self.network.send_input(input_data)

            # State'i al ve güncelle
            state_data = self.network.receive_state()
            self.game_state.update_from_state(state_data)

            # Ekrana çiz
            self.display.draw_all(self.game_state, self.display.get_fps(), self.connected)
            self.display.tick()

        self.cleanup()

    def cleanup(self):
        self.network.disconnect()
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    pygame.init()
    # Şimdilik herkes Player 1 inputu yolluyor testi için
    client = GameClient(player_id=1)
    client.run()