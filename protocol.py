import json

def mesaj_hazirla(mesaj_tipi, veri):

    paket = {
        "tip": mesaj_tipi,
        "veri": veri
    }
    return json.dumps(paket).encode('utf-8')

def mesaj_coz(gelen_byte_veri):

    if not gelen_byte_veri:
        return None
    try:
        return json.loads(gelen_byte_veri.decode('utf-8'))
    except json.JSONDecodeError:
        return None