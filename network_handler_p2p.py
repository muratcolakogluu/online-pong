"""
network_handler_p2p.py — P2P Ağ Katmanı
==========================================
İki ayrı soket kanalını yönetir:

  TCP (port 5000) — Güvenilir, sıralı iletim:
      • Oyuncu adı değişimi (bağlantı kurulurken bir kez)
      • Sohbet mesajları
      • 'game_over' sinyali (kazanan + final skor)
      • 'rematch_accept' sinyali

  UDP (host 5001, joiner 5002) — Düşük gecikmeli, kayıp-tolere:
      • Host → Joiner: top konumu, skor, host raket Y  (her frame)
      • Joiner → Host : joiner raket Y                 (her frame)

  Neden farklı UDP portları?
      Windows'ta SO_REUSEADDR aynı porta bağlanan iki sokete
      gelen paketleri karıştırabilir.  Host 5001, joiner 5002
      kullanarak bu çakışma kesin olarak önlenir.

  3. kişi koruma:
      host_tcp(), accept()'ten hemen sonra server soketini kapatır.
      Bu noktadan itibaren yeni TCP bağlantısı kabul edilmez;
      3. kişi [10061] ConnectionRefusedError alır.
"""

import socket
import json


class P2PNetworkHandler:
    """P2P oyun bağlantısını kuran ve yöneten sınıf."""

    def __init__(self, player_name: str = "Player",
                 tcp_port: int = 5000, udp_port: int = 5001):
        self.player_name = player_name
        self.tcp_port    = tcp_port
        self.udp_port    = udp_port   # setup_udp()'ten önce değiştirilebilir

        self.p2p_tcp_socket = None    # Karşı tarafla TCP bağlantısı
        self.p2p_udp_socket = None    # UDP gönderme/alma soketi
        self._server_socket = None    # Host'a özel: accept() sonrası kapanır
        self._tcp_buffer    = ""      # TCP satır tabanlı çerçeveleme tamponu
        self.local_udp_port = udp_port

        self.opponent_data: dict = {}  # {'ip': str, 'port': int}
        self.connected           = False

    # ── Yardımcı ─────────────────────────────────────────────────────────────

    @staticmethod
    def _reuse_socket(sock: socket.socket):
        """SO_REUSEADDR (ve desteklenen platformlarda SO_REUSEPORT) uygular."""
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass

    def _configure_connected_tcp(self):
        """TCP_NODELAY (Nagle kapalı) ve SO_KEEPALIVE uygular."""
        if not self.p2p_tcp_socket:
            return
        for level, opt in (
            (socket.IPPROTO_TCP, socket.TCP_NODELAY),
            (socket.SOL_SOCKET,  socket.SO_KEEPALIVE),
        ):
            try:
                self.p2p_tcp_socket.setsockopt(level, opt, 1)
            except OSError:
                pass

    # ── Kurulum ──────────────────────────────────────────────────────────────

    def setup_udp(self, bind_port: int | None = None):
        """
        UDP soketini oluşturur ve bağlar.

        bind_port verilmezse self.udp_port kullanılır.
        Soket non-blocking modda açılır; receive_game_state_udp()
        hemen döner, veri yoksa None döndürür.
        """
        port = bind_port if bind_port is not None else self.udp_port
        self.p2p_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._reuse_socket(self.p2p_udp_socket)
        self.p2p_udp_socket.bind(("", port))
        self.local_udp_port = self.p2p_udp_socket.getsockname()[1]
        self.p2p_udp_socket.setblocking(False)
        print(f"UDP soket acildi  port={self.local_udp_port}")

    def host_tcp(self):
        """
        Tek bir gelen TCP bağlantısını kabul eder (bloklayıcı).

        accept() döndükten hemen sonra _server_socket kapatılır.
        Böylece 3. bir kişi bağlanamaz; ConnectionRefusedError alır.
        """
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._reuse_socket(self._server_socket)
        self._server_socket.bind(("", self.tcp_port))
        self._server_socket.listen(1)
        print(f"TCP baglanti bekleniyor  port={self.tcp_port} ...")
        self.p2p_tcp_socket, addr = self._server_socket.accept()

        # ── 3. kişi koruması: server soket hemen kapatılıyor ──────────────
        self._server_socket.close()
        self._server_socket = None

        self._configure_connected_tcp()
        self.p2p_tcp_socket.settimeout(0.001)  # Non-blocking benzeri
        self.connected = True
        print(f"TCP P2P baglandi: {addr}")

    def connect_tcp(self, host: str, port: int):
        """
        Host'un TCP portuna bağlanır (bloklayıcı, 3 sn timeout).

        Bağlantı başarısızsa ConnectionRefusedError veya TimeoutError
        fırlatılır; _do_join() bunu yakalar ve Türkçe hata mesajına çevirir.
        """
        self.p2p_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.p2p_tcp_socket.settimeout(3.0)
        self.p2p_tcp_socket.connect((host, port))
        self._configure_connected_tcp()
        self.p2p_tcp_socket.settimeout(0.001)
        self.connected = True
        print(f"TCP P2P baglandi: {host}:{port}")

    def exchange_names(self, my_name: str) -> str:
        """
        TCP bağlantısı kurulduktan hemen sonra karşılıklı isim paylaşımı yapar.

        exchange_player_info()'nun sade sarmalayıcısı.
        Dönen değer: karşı tarafın oyuncu adı (str).
        """
        info = self.exchange_player_info(my_name)
        return info.get("name", "Rakip")

    def exchange_player_info(self, my_name: str) -> dict:
        """
        Bloklayıcı isim + UDP port paylaşımı (bağlantı kurulurken bir kez).

        Gönderilen/alınan JSON: {"action": "player_info", "name": ..., "udp_port": ...}
        5 sn içinde yanıt gelmezse {"name": "Rakip", ...} döner.
        """
        if not self.p2p_tcp_socket:
            return {"name": "Rakip", "udp_port": self.udp_port}
        try:
            self.p2p_tcp_socket.setblocking(True)
            self.p2p_tcp_socket.settimeout(5.0)

            payload = json.dumps({
                "action":   "player_info",
                "name":     my_name,
                "udp_port": self.local_udp_port,
            }) + "\n"
            self.p2p_tcp_socket.sendall(payload.encode())

            # Satır sonlanana kadar oku
            buf = b""
            while b"\n" not in buf:
                chunk = self.p2p_tcp_socket.recv(256)
                if not chunk:
                    break
                buf += chunk

            data = json.loads(buf.split(b"\n")[0].decode())
            if data.get("action") != "player_info":
                return {"name": "Rakip", "udp_port": self.udp_port}

            return {
                "name":     data.get("name", "Rakip"),
                "udp_port": int(data.get("udp_port", self.udp_port)),
            }
        except Exception as e:
            print(f"İsim paylasim hatasi: {e}")
            return {"name": "Rakip", "udp_port": self.udp_port}
        finally:
            self.p2p_tcp_socket.settimeout(0.001)

    # ── UDP — oyun durumu (her frame) ────────────────────────────────────────

    def receive_game_state_udp(self):
        """
        UDP tamponundaki tüm paketleri tüketir; yalnızca EN SON'unu döndürür.

        Joiner 1-2 kare geride kalırsa OS tamponu eskimiş paketlerle dolar.
        Tümünü okuyup sadece sonuncuyu almak algılanan gecikmeyi sıfırlar.
        Non-blocking soket; veri yoksa BlockingIOError fırlatılır → None döner.
        """
        if not self.p2p_udp_socket:
            return None

        latest = None

        # ── Tampon tamamen boşaltma döngüsü ──────────────────────────────
        # Sorun: 60 fps oyunda bir frame ~16 ms sürer.  Ağ gecikmesi veya
        # işlemci yükünden birkaç frame geç kalınırsa OS UDP tamponu birikmiş
        # (eski) paketlerle dolar.
        #
        # Naif çözüm — sadece bir paket oku:
        #   Eski paketi işleriz → top ekranda "geri gider" gibi titrer.
        #
        # Doğru çözüm — tüm tamponu boşalt, yalnızca sonuncuyu al:
        #   while True ile non-blocking recvfrom çağrılır; tampon boşalınca
        #   BlockingIOError fırlatılır → döngü kırılır.  "latest" değişkeni
        #   her başarılı okumada güncellenir; döngü bitince en taze paket
        #   elimizde kalır, eskiler yok sayılır.
        while True:
            try:
                data, _ = self.p2p_udp_socket.recvfrom(4096)
                latest  = json.loads(data.decode())   # Başarılıysa latest güncelle
            except (BlockingIOError, OSError):
                break   # Tampon boş → döngüden çık
            except Exception:
                break   # Bozuk / ayrıştırılamaz paket → atla

        return latest   # None → bu frame'de hiç UDP paketi gelmedi

    # ── TCP — sohbet ve sinyaller ────────────────────────────────────────────

    def receive_tcp_message(self):
        """
        TCP kanalından bir satır okur (non-blocking).

        TCP 'yapışma' sorununu çözmek için newline tabanlı çerçeveleme kullanılır:
        her mesaj JSON + '\\n' ile gönderilir, alıcı '\\n' bulunca ayrıştırır.

        Dönen değer: dict veya None.
        """
        if not self.p2p_tcp_socket:
            return None

        # ── TCP "yapışma" sorunu ve çözümü ───────────────────────────────
        # TCP bir byte-stream protokolüdür; paket sınırlarını korumaz.
        # Örnek: iki JSON mesajı aynı anda gelebilir:
        #   {"action":"chat",...}\n{"action":"game_over",...}\n
        # recv(1024) bunu tek seferde verebilir.  Naif json.loads() bu durumda
        # hata verir.  Çözüm: her mesajı "\n" ile bitir (çerçeveleme) ve
        # buffer'a biriktirerek "\n" görünce bir mesaj ayırt et.
        #
        # _tcp_buffer: önceki recv'den kalan, henüz tam satır oluşturmamış veri.

        # Tampon zaten tam bir satır içeriyorsa ağa gitmeden hemen ver
        if "\n" in self._tcp_buffer:
            line, self._tcp_buffer = self._tcp_buffer.split("\n", 1)
            # split("\n", 1) → [tamamlanan_satır, kalan_tampon]
            return json.loads(line.strip())

        try:
            chunk = self.p2p_tcp_socket.recv(1024)
            if chunk:
                self._tcp_buffer += chunk.decode("utf-8")   # Yeni veriyi tampona ekle
                if "\n" in self._tcp_buffer:
                    line, self._tcp_buffer = self._tcp_buffer.split("\n", 1)
                    return json.loads(line.strip())
                # "\n" yoksa mesaj henüz tamamlanmadı; bir sonraki çağrıda devam edilir
            else:
                # recv() boş bytes döndürdü → karşı taraf TCP bağlantısını kapattı
                # (normal kapatma: FIN paketi geldi, bağlantı düzgün sonlandı)
                return {"action": "disconnect"}
        except (socket.timeout, BlockingIOError, OSError):
            pass   # Non-blocking soket → bu karede veri yok, None dön
        except Exception as e:
            print(f"TCP alma hatasi: {e}")
        return None

    # ── Temizlik ─────────────────────────────────────────────────────────────

    def close(self):
        """
        Tüm açık soketleri kapatır.

        Önce shutdown() çağrısı yapılır: accept() veya recv() blokajında
        bekleyen arka plan iş parçacıklarının kilidini açar.
        """
        # shutdown → recv/accept blokajını kır
        for sock in (self.p2p_tcp_socket, self._server_socket):
            if sock:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass

        # Tüm soketleri kapat
        for sock in (self.p2p_tcp_socket, self.p2p_udp_socket, self._server_socket):
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

        self.connected          = False
        self.p2p_tcp_socket     = None
        self.p2p_udp_socket     = None
        self._server_socket     = None
