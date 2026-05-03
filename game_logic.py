"""
game_logic.py — Oyun Kuralları
================================
Fizikten bağımsız kural katmanı: kazanma koşulu ve top hız yönetimi.

  "Ne olmalı?" sorusuna cevap verir.
  "Nasıl hesaplanır?" sorusu physics.py'ye aittir.

Sadece host tarafında çalışır; joiner fizik veya kural hesabı yapmaz.
"""

import math
from game_state import GameData, GameState


class GameLogic:
    """
    Oyun kurallarını uygular.

    SPEED_PROGRESSION: Gol sayısına göre top hız çarpanı.
      0 gol → x1.0, 1 gol → x1.1, ..., 4+ gol → x1.4
    """

    # Her golde topun hızlanma oranı (indeks = toplam gol sayısı, maks 4)
    SPEED_PROGRESSION = {0: 1.0, 1: 1.1, 2: 1.2, 3: 1.3, 4: 1.4}

    def __init__(self, game_data: GameData):
        self.game = game_data

    def check_win_condition(self) -> bool:
        """
        Herhangi bir oyuncunun max_score'a ulaşıp ulaşmadığını kontrol eder.

        Ulaştıysa GameData.winner ve state alanlarını günceller, True döner.
        Host bu dönüşü yakalayıp joiner'a TCP ile 'game_over' sinyali gönderir.
        """
        if self.game.score1 >= self.game.max_score:
            self.game.winner = 1
            self.game.state  = GameState.GAME_OVER
            return True
        if self.game.score2 >= self.game.max_score:
            self.game.winner = 2
            self.game.state  = GameState.GAME_OVER
            return True
        return False

    def update_ball_speed(self):
        """
        Toplam gol sayısına göre top hızını ayarlar (host tarafında her frame).

        Mevcut hız zaten hedef hızdaysa hiçbir şey yapmaz (gereksiz
        vektör yeniden ölçeklendirmesini önler). physics._reset_ball()
        ball_speed'i sıfırladığı için her golden sonra hız yeniden hesaplanır.
        """
        # Toplam atılan gol sayısı → hangi hız basamağındayız?
        # 5. golden sonra artık hızlanma olmaz (indeks 4'te takılır)
        total_goals  = self.game.score1 + self.game.score2
        progress_idx = min(total_goals, 4)
        target_speed = 5.0 * self.SPEED_PROGRESSION[progress_idx]
        # Örnek: 3 gol → 5.0 × 1.3 = 6.5 piksel/frame

        # Küçük tolerans (0.001): float yuvarlama hatasından kaynaklanan
        # gereksiz yeniden ölçeklendirmeleri önler
        if abs(self.game.ball_speed - target_speed) <= 0.001:
            return

        # ── Yön koruyarak ölçeklendirme ──────────────────────────────────
        # math.hypot(vx, vy): vektörün gerçek büyüklüğü (Pisagor teoremi)
        # ratio = hedef_hız / mevcut_hız → her iki bileşeni aynı oranda büyüt/küçült
        # Böylece topun hareketi yönünü değiştirmez, sadece hızlanır/yavaşlar
        current_speed = math.hypot(self.game.ball_vx, self.game.ball_vy)
        if current_speed > 0:   # Sıfıra bölmeyi önle (teorik durum)
            ratio = target_speed / current_speed
            self.game.ball_vx *= ratio
            self.game.ball_vy *= ratio
        self.game.ball_speed = target_speed

    def start_game(self):
        """Geri sayım bitti; oyun durumunu RUNNING'e geçirir."""
        self.game.state = GameState.RUNNING
