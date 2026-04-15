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