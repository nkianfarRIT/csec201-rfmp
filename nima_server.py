# Last updated: 20/09/2026

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

# if fields[0] != "SS" or fields[1] != "RFMP" or fields[2] != "v1.0" or fields[3] != "0":
#     conn.send("EE, 01 or 02, malformed packet or unsupported protocol or version".encode('utf-8')) <-- not suitable error handling so gonna update it

# Our set of error codes:
# 01  malformed packet
# 02  unsupported protocol or version
# 03  command failed
# 04  file error

if len(fields) != 4 or fields[0] != "SS" or fields[3] not in ("0", "1"):
    # Wrong shape, wrong type, or a secure-flag that isn't 0/1 --> structural problem much better than 01 or 02 error code
    conn.send("EE,01,malformed packet".encode('utf-8')) # Fixed the field seperation for both 01 and 02

elif fields[1] != "RFMP" or fields[2] != "v1.0":
    # Packet is well-formed, we just don't speak this protocol/version
    conn.send("EE,02,unsupported protocol or version".encode('utf-8')) # <-- much better than 01 or 02 as now its seprate

else:
    conn.send("CC".encode('utf-8'))

conn.close()
welcomeSocket.close() # <-- added this cause there was an error

