import socket

ESP_MAC = "ECE3341ADFBC"   # MAC printed by ESP (NO colons)
ESP_HOST = f"esp-{ESP_MAC}.local"
ESP_PORT = 8080

print(f"Connecting to {ESP_HOST} ...")

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((ESP_HOST, ESP_PORT))

print("Connected to ESP32")

def send(cmd):
    print("Sending:", cmd)
    sock.sendall((cmd + "\n").encode())

# Test commands
send("T1_ON")
send("T1_OFF")
import socket

ESP_MAC = "ECE3341ADFBC"   # MAC printed by ESP (NO colons)
ESP_HOST = f"esp-{ESP_MAC}.local"
ESP_PORT = 8080

print(f"Connecting to {ESP_HOST} ...")

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((ESP_HOST, ESP_PORT))

print("Connected to ESP32")

def send(cmd):
    print("Sending:", cmd)
    sock.sendall((cmd + "\n").encode())

# Test commands
send("T1_ON")
send("T1_OFF")
