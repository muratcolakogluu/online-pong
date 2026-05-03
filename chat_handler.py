"""
chat_handler.py — Sohbet Mesaj Yöneticisi
===========================================
Oyun içi metin sohbetini yönetir.

  • Mesaj gönderme : TCP üzerinden JSON satırı olarak iletir.
  • Mesaj alma     : TCP'den gelen ham veriyi ChatMessage'a dönüştürür.
  • Sistem mesajı  : Bağlantı, gol, oyun başlangıcı gibi olaylar için
                     ağ üzerinden gönderilmeyen yerel bildirimler.
  • Görüntüleme    : ChatUI'nin render ettiği son N mesajı döndürür.

Ağ gönderimi P2PNetworkHandler.p2p_tcp_socket üzerinden yapılır.
"""

import json
import time
from typing import List, Dict


class ChatMessage:
    """Tek bir sohbet satırını temsil eder."""

    def __init__(self, sender: str, text: str, is_system: bool = False):
        self.sender    = sender
        self.text      = text
        self.timestamp = time.time()
        self.is_system = is_system   # True ise UI farklı renkle gösterir


class ChatHandler:
    """Sohbet geçmişini tutar ve TCP kanalı üzerinden mesaj alışverişi yapar."""

    def __init__(self, network_handler, player_name: str):
        self.network     = network_handler
        self.player_name = player_name
        self.messages:   List[ChatMessage] = []
        self.max_messages = 20   # Geçmişte tutulacak maksimum mesaj sayısı

    def send_message(self, text: str) -> bool:
        """
        Kullanıcının yazdığı metni TCP üzerinden karşı tarafa gönderir.

        Boş ya da sadece boşluk içeren mesajlar reddedilir (False döner).
        Gönderi başarılı olsun ya da olmasın mesaj yerel geçmişe eklenir
        ('You' gönderici olarak); böylece kullanıcı ne yazdığını görür.
        """
        if not text.strip():
            return False

        packet = {
            "action":      "chat",
            "sender_id":   self.player_name,
            "sender_name": self.player_name,
            "message":     text,
            "timestamp":   time.time(),
        }
        try:
            raw = (json.dumps(packet) + "\n").encode("utf-8")
            # P2P mimarisinde her zaman p2p_tcp_socket kullanılır
            if hasattr(self.network, "p2p_tcp_socket") and self.network.p2p_tcp_socket:
                self.network.p2p_tcp_socket.sendall(raw)
        except Exception as e:
            print(f"Sohbet gonderme hatasi: {e}")

        self.add_message("You", text, is_system=False)
        return True

    def receive_message(self, data: dict) -> bool:
        """
        TCP'den gelen sohbet paketini yerel geçmişe ekler.

        data: client.py tarafından ayrıştırılmış JSON dict
              {"action": "chat", "sender_name": ..., "message": ...}
        """
        try:
            sender  = data.get("sender_name", "Bilinmeyen")
            message = data.get("message", "")
            self.add_message(sender, message, is_system=False)
            return True
        except Exception as e:
            print(f"Sohbet alma hatasi: {e}")
            return False

    def add_system_message(self, text: str):
        """
        Ağ üzerinden gönderilmeyen yerel sistem bildirimi ekler.

        Örnek: 'Oyun başladı', 'Rakip bağlandı', 'Gol!'
        UI bu mesajları farklı (mavi) renkte gösterir.
        """
        self.add_message("[SİSTEM]", text, is_system=True)

    def add_message(self, sender: str, text: str, is_system: bool = False):
        """
        Mesajı geçmişe ekler; max_messages aşılırsa en eskiyi siler.

        Doğrudan çağrılabilir; send_message / receive_message / add_system_message
        hepsi bu metodu kullanır.
        """
        self.messages.append(ChatMessage(sender, text, is_system))
        if len(self.messages) > self.max_messages:
            self.messages.pop(0)

    def get_display_messages(self, count: int = 5) -> List[Dict]:
        """
        ChatUI'nin render edeceği son 'count' mesajı döndürür.

        Dönen liste: [{"sender": str, "text": str, "is_system": bool}, ...]
        """
        recent = self.messages[-count:] if len(self.messages) >= count else self.messages
        return [
            {"sender": m.sender, "text": m.text, "is_system": m.is_system}
            for m in recent
        ]
