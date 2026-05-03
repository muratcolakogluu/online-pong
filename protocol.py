# ╔══════════════════════════════════════════════════════════════════╗
# ║  PHASE 1 DOSYASI — Mevcut P2P oyununda KULLANILMAZ              ║
# ║  server.py tarafından kullanılan mesaj serileştirme yardımcısı. ║
# ╚══════════════════════════════════════════════════════════════════╝
import json

def mesaj_hazirla(mesaj_tipi, veri):

    paket = {
        "tip": mesaj_tipi,
        "veri": veri
    }
    return (json.dumps(paket) + "\n").encode('utf-8')

def mesaj_coz(gelen_string):

    try:
        return json.loads(gelen_string)
    except json.JSONDecodeError:
        return None