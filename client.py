# Last updated: 18/09/2026

import socket

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
host = "127.0.0.1"          # changed from gethostname() in the mycourses
port = 8888 # Using 8888 as it doesn't interfere with the well-known range of used ports
client.connect((host, port))

client.send("Hello server".encode('utf-8')) # <-- same structure as my courses

reply = client.recv(2024).decode('utf-8')
print("Client got:", reply)

client.close()
