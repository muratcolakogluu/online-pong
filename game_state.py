class GameState:
    def __init__(self):
        # Ekran sınırları (config.py ile uyumlu)
        self.screen_w = 800
        self.screen_h = 600
        self.paddle_h = 90
        self.paddle_speed = 10

        # Başlangıç konumları
        self.p1_y = 250
        self.p2_y = 250

        self.ball_x = 400
        self.ball_y = 300

        # Topun x ve y eksenindeki hızı
        self.ball_dx = 6
        self.ball_dy = 6

        self.score_p1 = 0
        self.score_p2 = 0

    def update_physics(self):
        """
        Saniyede 60 kez (60 FPS) çağrılacak fizik motoru.
        Server otoriter olduğu için bu hesaplar sadece burada yapılır.
        """
        # 1. Topu hareket ettir
        self.ball_x += self.ball_dx
        self.ball_y += self.ball_dy

        # 2. Üst ve alt duvarlara çarpma kontrolü
        if self.ball_y <= 0 or self.ball_y >= self.screen_h:
            self.ball_dy *= -1  # Yönü tersine çevir

        # 3. Raketlere çarpma kontrolü
        # Sol raket (P1) - X ekseninde 15 piksellik alanda duruyor
        if self.ball_x <= 30 and (self.p1_y <= self.ball_y <= self.p1_y + self.paddle_h):
            self.ball_dx *= -1
            self.ball_x = 30  # Duvara yapışma bug'ını önler

        # Sağ raket (P2) - X ekseninde 770 piksellik alanda duruyor
        if self.ball_x >= 770 and (self.p2_y <= self.ball_y <= self.p2_y + self.paddle_h):
            self.ball_dx *= -1
            self.ball_x = 770

        # 4. Skor Kontrolü (Top ekranın sağına veya soluna çıkarsa)
        if self.ball_x < 0:
            self.score_p2 += 1
            self.reset_ball()
        elif self.ball_x > self.screen_w:
            self.score_p1 += 1
            self.reset_ball()

    def reset_ball(self):
        """Gol olduğunda topu ortaya alıp yönünü ters çevirir"""
        self.ball_x = 400
        self.ball_y = 300
        self.ball_dx *= -1

    def durumu_getir(self):
        """Client'lara gönderilecek nihai veri sözlüğü"""
        return {
            "paddle_left_y": self.p1_y,
            "paddle_right_y": self.p2_y,
            "ball_x": self.ball_x,
            "ball_y": self.ball_y,
            "score_left": self.score_p1,
            "score_right": self.score_p2
        }