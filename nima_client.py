# Last updated: 24/09/2026

import socket

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
host = "127.0.0.1"          # changed from gethostname() in the mycourses
port = 8888 # Using 8888 as it doesn't interfere with the well-known range of used ports
client.connect((host, port))

# Following code was used for testing purposes:

# client.send("Hello s".encode('utf-8')) # <-- same structure as my courses
# client.send("SS,RFMP,v1.0,0".encode('utf-8')) # <-- modified so now the string sends "SS,RFMP,v1,0,0"
# reply = client.recv(2024).decode('utf-8')
# fields = reply.split(",") # <-- same as server side now done as per the document for error codes/description
# # print("Client got:", reply) <-- unused

# Updated Code 24/09/2026 to use functions
def send_packet(client, packet):
    client.send(packet.encode('utf-8'))

def receive_packet(client):
    return client.recv(2024).decode('utf-8')

def check_reply(reply):
    # Handles every server reply in ONE place, including Exception (EE) packets
    fields = reply.split(",", 2)
    if fields[0] == "EE" and len(fields) == 3:
        print("Error " + fields[1] + ": " + fields[2])
        return False
    elif fields[0] == "SC":
        print("Server: command successful")
        return True
    else:
        print("Server:", reply)
        return True






# Verifying if the field were correct using the same structure as the server.py
# if & elif statements
# Our set of error codes:
# 01  malformed packet
# 02  unsupported protocol or version
# 03  command failed
# 04  file error

def check_reply(reply):
    # This will handle every server reply in ONE place including (EE) packets
    # It was easy I just placed all the following code into the function
    fields = reply.split(",", 2)
    if fields[0] != "CC" or len(fields) != 1:
        print("Error was:", reply)
    else:
        print("Setup complete, server confirmed the connection")
        # operation phase goes here later
        while True:
            usercommand = str(input("Enter a command: "))
            if usercommand == "exit" or usercommand == "Exit":
                client.send("End".encode('utf-8')) # tell the server the user wrote exit
                break # stop the client loop cause End was sent to server
            else:
                # client.send(("CM,prompt,",usercommand).encode('utf-8')) # <-- apparently ,usercommand makes it into a tuple
                client.send(("CM,prompt," + usercommand).encode('utf-8')) # plus to prevent tuple
                reply = client.recv(2024).decode('utf-8') # <-- server's reply from the command
                print("Server:", reply)


client.close()
