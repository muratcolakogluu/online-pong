import socket
import protocol
from game_state import GameState


def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    HOST = '127.0.0.1'
    PORT = 5555
    server_socket.bind((HOST, PORT))
    server_socket.listen(2)

    print(f"[BAŞARILI] Server başlatıldı ({HOST}:{PORT})")

    oyun = GameState()

    print("[BİLGİ] Oyuncu 1 bekleniyor...")
    p1_socket, p1_address = server_socket.accept()
    print(f"[BAĞLANTI] Oyuncu 1 geldi: {p1_address}")
    p1_socket.sendall(protocol.mesaj_hazirla("BAGLANTI", {"player_id": 1}))

    print("[BİLGİ] Oyuncu 2 bekleniyor...")
    p2_socket, p2_address = server_socket.accept()
    print(f"[BAĞLANTI] Oyuncu 2 geldi: {p2_address}")
    p2_socket.sendall(protocol.mesaj_hazirla("BAGLANTI", {"player_id": 2}))

    print("[BAŞARILI] İki oyuncu da bağlandı. İskelet kurulumu tamamlandı!")

    ilk_durum = oyun.durumu_getir()
    state_mesaji = protocol.mesaj_hazirla("STATE", ilk_durum)

    p1_socket.sendall(state_mesaji)
    p2_socket.sendall(state_mesaji)
    print("[BİLGİ] İlk oyun durumu (State) oyunculara iletildi.")

    p1_socket.close()
    p2_socket.close()
    server_socket.close()


if __name__ == "__main__":
    start_server()