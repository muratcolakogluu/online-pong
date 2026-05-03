"""
physics.py — Top Fiziği
=========================
Topun her frame güncellenmesini yönetir.

YALNIZCA HOST tarafında çalışır:
  Host fizik hesaplar → UDP ile joiner'a gönderir.
  Joiner bu modülü import eder ama update() çağırmaz.

Swept AABB çarpışma tespiti:
  Klasik "bu frame'de üst üste biniyor mu?" kontrolü, yüksek hızda
  topun raket içinden geçmesine (tünel etkisi) neden olur.
  Swept AABB, topun önceki ve mevcut konumu arasındaki doğru parçasını
  rakete karşı test eder; çarpışma anındaki Y koordinatı enterpolasyonla
  hesaplanır.
"""

import config
from game_state import GameData


class BallPhysics:
    """Top fiziğini ve çarpışma tespitini yönetir."""

    def __init__(self, game_data: GameData):
        self.game = game_data

        # ── Saha sınırları ────────────────────────────────────────────────
        # window_width: gol tespitinde topun x sınırı olarak kullanılır.
        # field_top / field_bottom: duvar çarpışması ve raket sıfırlama için.
        self.window_width  = config.GAME_AREA_WIDTH
        self.field_top     = config.FIELD_TOP
        self.field_bottom  = config.WINDOW_HEIGHT - config.FIELD_BOTTOM_MARGIN

        # ── Raket çarpışma bölgeleri (piksel sabitleri) ───────────────────
        # Sol raket (host): x=20, genişlik=15 → sağ kenar x=35
        # Bu değerler game_screen.py'deki çizim koordinatlarıyla birebir eşleşmeli.
        self.paddle1_x     = 20
        self.paddle1_width = 15

        # Sağ raket (joiner): sol kenar = GAME_AREA_WIDTH - 35 = 685
        # Çarpışma sırasında yalnızca paddle2_x (sol kenar) kullanılır;
        # genişlik değerine gerek yoktur.
        self.paddle2_x     = config.GAME_AREA_WIDTH - 35

    def update(self) -> bool:
        """
        Top konumunu bir frame ilerletir; çarpışma ve gol kontrolü yapar.

        Dönüş: True  → gol oldu (host GOAL_PAUSE_SEC süre bekler)
               False → normal frame
        """
        prev_x = self.game.ball_x
        prev_y = self.game.ball_y

        # Hızı konuma ekle
        self.game.ball_x += self.game.ball_vx
        self.game.ball_y += self.game.ball_vy

        self._check_wall_collision()
        self._check_paddle_collision(prev_x, prev_y)
        return self._check_goal()

    def _check_wall_collision(self) -> bool:
        """
        Üst ve alt duvar çarpışmalarını kontrol eder.

        Top field_top veya field_bottom sınırını aşarsa dikey hız
        tersine çevrilir ve top sınır içine geri alınır.
        """
        r = self.game.ball_radius
        if self.game.ball_y < self.field_top + r:
            self.game.ball_y  = float(self.field_top + r)
            self.game.ball_vy = abs(self.game.ball_vy)     # Aşağı yansıt
            return True
        if self.game.ball_y > self.field_bottom - r:
            self.game.ball_y  = float(self.field_bottom - r)
            self.game.ball_vy = -abs(self.game.ball_vy)    # Yukarı yansıt
            return True
        return False

    def _check_paddle_collision(self, prev_x: float, prev_y: float) -> bool:
        """
        Swept AABB ile raket çarpışması kontrol eder.

        Algoritma:
          1. Topun bu frame'deki hareketi doğru parçası olarak modellenir:
             (prev_x, prev_y) → (ball_x, ball_y).
          2. Topun raket kenarını geçip geçmediği kontrol edilir.
          3. Geçmişse, enterpolasyonla geçiş anındaki Y (cross_y) hesaplanır.
          4. cross_y raket Y aralığına giriyorsa çarpışma onaylanır.
          5. Hız x bileşeni tersine çevrilir; raketin merkezine göre
             dikey açı verilir (uca çarpınca daha dik çıkar).
        """
        r  = self.game.ball_radius
        bx = self.game.ball_x
        by = self.game.ball_y

        # ── Sol raket (host) — top sola gidiyorsa ────────────────────────
        if self.game.ball_vx < 0:
            p1_right = self.paddle1_x + self.paddle1_width   # Sol raketin sağ kenarı = 35 px

            # Önceki karede raketin sağ tarafındaydı (prev_x - r >= p1_right)
            # ama bu karede geçti (bx - r <= p1_right) → çarpışma var
            if prev_x - r >= p1_right and bx - r <= p1_right:

                # ── Parametrik geçiş zamanı (t ∈ [0,1]) ──────────────────
                # Topun sağ kenarının tam olarak raketin sağ kenarını geçtiği
                # "t" anını bulmak için doğrusal interpolasyon:
                #   t=0 → önceki kare konumu
                #   t=1 → bu karenin sonu
                # Böleni 0 kontrolü: top hiç hareket etmemişse t=0 al
                t = (prev_x - r - p1_right) / (prev_x - bx) if prev_x != bx else 0

                # t anındaki Y konumu: topun o kesişme anında tam nerede olduğunu bul
                cross_y = prev_y + (by - prev_y) * t

                p1y = self.game.paddle1_y
                p1h = self.game.paddle_height

                # cross_y raketin Y aralığına giriyor mu? (top rakete değdi mi?)
                if cross_y + r > p1y and cross_y - r < p1y + p1h:
                    self.game.ball_vx = abs(self.game.ball_vx)    # Yatay hızı tersine çevir → sağa yansıt

                    # ── Açı verme (rel: raketin merkezine göre konum) ──────
                    # rel = -1 → raketin üst ucu   (top yukarı çıkar)
                    # rel =  0 → raketin tam ortası (top düz gider)
                    # rel = +1 → raketin alt ucu    (top aşağı iner)
                    # 0.75 çarpanı: dikey hızı yatay hızın %75'iyle sınırlar,
                    # aşırı açılı çıkışların önüne geçer
                    rel = (cross_y - (p1y + p1h / 2)) / (p1h / 2)
                    self.game.ball_vy = rel * abs(self.game.ball_vx) * 0.75

                    # +1 ekstra piksel: bir sonraki frame'de top hâlâ raket içindeymiş gibi
                    # algılanmasın (ikinci çarpışma / titreme önleme)
                    self.game.ball_x = p1_right + r + 1
                    return True

        # ── Sağ raket (joiner) — top sağa gidiyorsa ─────────────────────
        if self.game.ball_vx > 0:
            p2_left = self.paddle2_x   # Sağ raketin sol kenarı = 685 px

            # Önceki karede raketin sol tarafındaydı (prev_x + r <= p2_left)
            # ama bu karede geçti (bx + r >= p2_left) → çarpışma var
            if prev_x + r <= p2_left and bx + r >= p2_left:

                # Geçiş zamanı t: topun sol kenarının raketin sol kenarını kestiği an
                t = (p2_left - (prev_x + r)) / (bx - prev_x) if bx != prev_x else 0

                # Kesişme anındaki Y: sol raket hesabıyla aynı mantık
                cross_y = prev_y + (by - prev_y) * t

                p2y = self.game.paddle2_y
                p2h = self.game.paddle_height

                if cross_y + r > p2y and cross_y - r < p2y + p2h:
                    self.game.ball_vx = -abs(self.game.ball_vx)   # Sola yansıt

                    # Aynı açı verme formülü (raketin merkezine göre relatif konum)
                    rel = (cross_y - (p2y + p2h / 2)) / (p2h / 2)
                    self.game.ball_vy = rel * abs(self.game.ball_vx) * 0.75

                    # -1 ekstra piksel: sağ raket için raket içi sıkışmayı önle
                    self.game.ball_x = p2_left - r - 1
                    return True

        return False

    def _check_goal(self) -> bool:
        """
        Topun sol veya sağ sınırı aşıp aşmadığını kontrol eder.

        Sınır aşılırsa:
          • İlgili oyuncunun skoru artırılır.
          • _reset_ball() çağrılır: top ortaya, raketler merkeze.
          • True döner → client.py GOAL_PAUSE_SEC süre oyunu dondurur.
        """
        # Top sol duvarı geçti → host raketi kaçırdı → joiner 1 puan kazandı
        if self.game.ball_x < 0:
            self.game.score2 += 1
            self._reset_ball()
            return True

        # Top sağ duvarı geçti → joiner raketi kaçırdı → host 1 puan kazandı
        if self.game.ball_x > self.window_width:
            self.game.score1 += 1
            self._reset_ball()
            return True

        return False   # Gol yok, oyun devam ediyor

    def _reset_ball(self):
        """
        Golden sonra topu ve raketleri başlangıç konumuna alır.

        • Top sahaya ortalar.
        • Her iki raket dikey merkeze alınır.
        • ball_speed sıfırlanır → GameLogic.update_ball_speed() bir
          sonraki frame'de gol sayısına göre doğru hızı yeniden atar.
        • Son golü kimin yediğine göre top karşı tarafa doğru fırlatılır.

        Joiner paddle2_y için: client.py gol tespitinde bunu manuel
        olarak tekrar hesaplar (UDP ile gönderilmiyor).
        """
        # Top sahaya ortala
        self.game.ball_x = self.window_width / 2.0
        self.game.ball_y = (self.field_top + self.field_bottom) / 2.0

        # Raketleri dikey merkeze al
        # Formül: (sahanın üst + alt kenarı - raket yüksekliği) / 2
        centered_y = (self.field_top + self.field_bottom - self.game.paddle_height) / 2.0
        self.game.paddle1_y = centered_y
        self.game.paddle2_y = centered_y

        # ── Sonraki servisi belirle ───────────────────────────────────────
        # Golü yiyen taraf (yani rakibi öne geçen taraf) psikolojik avantajı
        # korumak için topu KENDİ tarafına doğru alır (karşı tarafa servis).
        # score1 > score2 → host öndeydi → top sağa (joiner'a) gider (+1)
        # score2 > score1 → joiner öndeydi → top sola (host'a) gider (-1)
        direction           = 1 if self.game.score1 > self.game.score2 else -1
        self.game.ball_vx   = 5.0 * direction
        self.game.ball_vy   = 2.0

        # ball_speed = 0 sinyali: GameLogic.update_ball_speed() bir sonraki
        # frame'de bu sıfırı görünce gol sayısına göre doğru hızı yeniden atar.
        # Böylece reset kodunun GameLogic'i doğrudan çağırması gerekmez.
        self.game.ball_speed = 0.0
