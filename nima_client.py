# Last updated: 20/09/2026

import socket

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
host = "127.0.0.1"          # changed from gethostname() in the mycourses
port = 8888 # Using 8888 as it doesn't interfere with the well-known range of used ports
client.connect((host, port))

# client.send("Hello s".encode('utf-8')) # <-- same structure as my courses
client.send("SS,RFMP,v1.0,0".encode('utf-8')) # <-- modified so now the string sends "SS,RFMP,v1,0,0"
reply = client.recv(2024).decode('utf-8')
fields = reply.split(",") # <-- same as server side now done as per the document for error codes/description
# print("Client got:", reply) <-- unused


# Verifying if the field were correct using the same structure as the server.py
# if & elif statements
# Our set of error codes:
# 01  malformed packet
# 02  unsupported protocol or version
# 03  command failed
# 04  file error

if fields[0] != "CC" or len(fields) != 1:
    print("Error was:", reply)

else:
    print("Setup complete, server confirmed the connection")
    # operation phase goes here later
client.close()
