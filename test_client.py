import socket

# 1. Soket oluştur
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

print("Server'a bağlanmaya çalışılıyor...")

# 2. Server'ın IP ve Portuna bağlan (Aynı numaralar olmak zorunda)
client_socket.connect(('127.0.0.1', 5555))

# 3. Server'dan gelen mesajı dinle (1024 byte'a kadar)
gelen_veri = client_socket.recv(1024)

# 4. Byte olarak gelen veriyi okunabilir string'e çevir
print(f"BAŞARILI! Serverdan gelen mesaj: {gelen_veri.decode('utf-8')}")

# Kapat
client_socket.close()