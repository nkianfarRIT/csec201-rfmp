# Last updated: 19/09/2026

import socket
import os, sys, stat # <-- Same structure pasted from the sample mycourses

welcomeSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
host = "127.0.0.1"          # changed from gethostname() in the mycourses
port = 8888 # Using 8888 as it doesn't interfere with the well-known range of used ports
welcomeSocket.bind((host, port))
welcomeSocket.listen(5)
print("Server is listening at port " + str(port))

conn, addr = welcomeSocket.accept()
print("Client connected!")

# message = conn.recv(2024).decode('utf-8')
# print("Server got:", message)

message = conn.recv(2024).decode('utf-8')   # "SS,RFMP,v1.0,0" is being recieved from client.py
fields = message.split(",")                 # ["SS", "RFMP", "v1.0", "0"] is being split at the instance of the comma in the string 
print("Server got:", fields)     # Should print the 4 fields

conn.send("Hello back".encode('utf-8'))
conn.close()