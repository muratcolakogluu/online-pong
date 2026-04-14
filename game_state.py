class GameState:
    def __init__(self):
        self.ball_x = 400
        self.ball_y = 300

        self.p1_y = 250
        self.p2_y = 250

        self.score_p1 = 0
        self.score_p2 = 0

    def durumu_getir(self):

        return {
            "ball_x": self.ball_x,
            "ball_y": self.ball_y,
            "p1_y": self.p1_y,
            "p2_y": self.p2_y,
            "score_p1": self.score_p1,
            "score_p2": self.score_p2
        }