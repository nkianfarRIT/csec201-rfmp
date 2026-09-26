# Last updated: 20/09/2026

import socket

host = "127.0.0.1"          # changed from gethostname() in the mycourses
port = 8888 # Using 8888 as it doesn't interfere with the well-known range of used ports

def connect_to_server(host, port):
    # creating socket, connecting & returning the socket object
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((host, port))
    return client # <-- preventing bug off nothing

def do_setup(client):
    # sending our string
    # client.send("Hello s".encode('utf-8')) # <-- same structure as my courses
    client.send("SS,RFMP,v1.0,0".encode('utf-8')) # <-- modified so now the string sends "SS,RFMP,v1,0,0"

def setup_result(client):
    reply = client.recv(2024).decode('utf-8')
    fields = reply.split(",") # <-- same as server side now done as per the document for error codes/description
    if fields[0] != "CC" or len(fields) != 1:
        print("Error was:", reply)
        return False
    return True


# Verifying if the field were correct using the same structure as the server.py
# if & elif statements
# Our set of error codes:
# 01  malformed packet
# 02  unsupported protocol or version
# 03  command failed
# 04  file error

def command_loop(client):
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

def main():
    client = connect_to_server(host, port)
    fields = do_setup(client)
    if not setup_result(client):
        print("Error was:", fields)
    else:
        print("Setup complete, server confirmed the connection")
        command_loop(client)
    client.close()

main()

