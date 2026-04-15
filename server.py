import socket
import select
import time
import protocol
from game_state import GameState
import config


def inputlari_isle(mesaj_str, oyun, player_id):
    """Client'tan gelen tuş verilerini State'e yansıtır"""
    paket = protocol.mesaj_coz(mesaj_str)
    if not paket or paket.get("tip") != "INPUT":
        return

    # Asıl tuş verilerinin olduğu iç kutuyu alıyoruz
    veri = paket.get("veri", {})

    # Eğer oyuncu raketi yukarı hareket ettirdiyse ve ekrandan taşmıyorsa:
    if veri.get("move_up"):
        if player_id == 1 and oyun.p1_y > 0:
            oyun.p1_y -= oyun.paddle_speed
        elif player_id == 2 and oyun.p2_y > 0:
            oyun.p2_y -= oyun.paddle_speed

    if veri.get("move_down"):
        if player_id == 1 and oyun.p1_y < (oyun.screen_h - oyun.paddle_h):
            oyun.p1_y += oyun.paddle_speed
        elif player_id == 2 and oyun.p2_y < (oyun.screen_h - oyun.paddle_h):
            oyun.p2_y += oyun.paddle_speed


def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    HOST = config.SERVER_HOST
    PORT = config.SERVER_PORT

    server_socket.bind((HOST, PORT))
    server_socket.listen(2)
    print(f"[BAŞARILI] Server {HOST}:{PORT} üzerinde dinliyor.")

    # --- OYUNCULARI KABUL ETME ---
    print("[BİLGİ] Oyuncu 1 bekleniyor...")
    p1_socket, _ = server_socket.accept()
    p1_socket.sendall(protocol.mesaj_hazirla("BAGLANTI", {"player_id": 1}))
    print("[BAĞLANTI] Oyuncu 1 geldi.")

    print("[BİLGİ] Oyuncu 2 bekleniyor...")
    p2_socket, _ = server_socket.accept()
    p2_socket.sendall(protocol.mesaj_hazirla("BAGLANTI", {"player_id": 2}))
    print("[BAĞLANTI] Oyuncu 2 geldi.")

    # Soketleri "Non-blocking" (engelleyici olmayan) moda alıyoruz
    p1_socket.setblocking(0)
    p2_socket.setblocking(0)

    oyun = GameState()

    # TCP paket birikmelerini çözeceğimiz tamponlar (buffer)
    p1_buffer = ""
    p2_buffer = ""

    print("\n[BAŞARILI] OYUN BAŞLADI! (Game Loop Devrede)")

    # --- ANA OYUN DÖNGÜSÜ (GAME LOOP) ---
    while True:
        # 1. AŞAMA: İSTEMCİLERDEN INPUT ALMA (ASENKRON)
        try:
            # select ile veri gelip gelmediğini kontrol et
            okunabilir, _, _ = select.select([p1_socket, p2_socket], [], [], 0)

            for sock in okunabilir:
                gelen_veri = sock.recv(1024).decode('utf-8')
                if not gelen_veri:
                    print("Bir oyuncu oyundan çıktı!")
                    return  # Oyunu bitir

                # Hangi oyuncudan geldiğini bul ve buffer'ına ekle
                if sock == p1_socket:
                    p1_buffer += gelen_veri
                    # TCP yapışmasını çöz (\n işaretine göre satır satır böl)
                    while '\n' in p1_buffer:
                        mesaj, p1_buffer = p1_buffer.split('\n', 1)
                        inputlari_isle(mesaj, oyun, 1)
                else:
                    p2_buffer += gelen_veri
                    while '\n' in p2_buffer:
                        mesaj, p2_buffer = p2_buffer.split('\n', 1)
                        inputlari_isle(mesaj, oyun, 2)
        except Exception as e:
            print("Ağ Hatası:", e)
            break

        # 2. AŞAMA: FİZİK MOTORUNU ÇALIŞTIR
        oyun.update_physics()

        # 3. AŞAMA: YENİ DURUMU (STATE) İSTEMCİLERE GÖNDER
        state_mesaji = protocol.mesaj_hazirla("STATE", oyun.durumu_getir())
        try:
            p1_socket.sendall(state_mesaji)
            p2_socket.sendall(state_mesaji)
        except:
            print("Gönderim hatası, bağlantı kopmuş olabilir.")
            break

        # 4. AŞAMA: TİCK RATE (Saniyede 60 kez çalışması için uyut)
        time.sleep(1 / 60)

    # Döngü kırılırsa temizlik yap
    p1_socket.close()
    p2_socket.close()
    server_socket.close()


if __name__ == "__main__":
    start_server()