# Last updated: 27/09/2026

import socket
import subprocess # <-- Importing subprocess to run commands
import os, sys, stat # <-- Same structure pasted from the sample mycourses


host = "127.0.0.1"          # changed from gethostname() in the mycourses
port = 8888 # Using 8888 as it doesn't interfere with the well-known range of used ports

# Tracks the server's "current directory" across commands, since cd
# can't be done with subprocess.run(shell=True) -- that spawns a brand
# new process each call, so a normal shell "cd" would have no effect
# on the next command.
current_dir = os.getcwd() # getcwd returns a unicode string of the directory
 
# Keeps track of a file opened with openWrite so the next DP packet(s)
# know where to write. None when no file is open for writing. (will be changed when client asks)
open_write_file = None


def start_server(host, port):
    welcomeSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    welcomeSocket.bind((host, port))
    welcomeSocket.listen(5)
    print("Server is listening at port " + str(port))
    conn, addr = welcomeSocket.accept()
    print("Client connected!")
    return welcomeSocket, conn


# message = conn.recv(2024).decode('utf-8')
# print("Server got:", message)

def recieve_setup(conn):
    message = conn.recv(2024).decode('utf-8')   # "SS,RFMP,v1.0,0" is being recieved from client.py
    fields = message.split(",")                 # ["SS", "RFMP", "v1.0", "0"] is being split at the instance of the comma in the string 
    print("From Client to Server:", fields)     # Should print the 4 fields
    return fields

# if fields[0] != "SS" or fields[1] != "RFMP" or fields[2] != "v1.0" or fields[3] != "0":
#     conn.send("EE, 01 or 02, malformed packet or unsupported protocol or version".encode('utf-8')) <-- not suitable error handling so gonna update it

# Our set of error codes:
# 01  malformed packet
# 02  unsupported protocol or version
# 03  command failed
# 04  file error

def validate_setup(conn, fields):
    if len(fields) != 4 or fields[0] != "SS" or fields[3] not in ("0", "1"):
        # Wrong shape, wrong type, or a secure-flag that isn't 0/1 --> structural problem much better than 01 or 02 error code
        conn.send("EE,01,malformed packet".encode('utf-8')) # Fixed the field seperation for both 01 and 02
        return False

    elif fields[1] != "RFMP" or fields[2] != "v1.0":
        # Packet is well-formed, we just don't speak this protocol/version
        conn.send("EE,02,unsupported protocol or version".encode('utf-8')) # <-- much better than 01 or 02 as now its seprate
        return False

    else:
        conn.send("CC".encode('utf-8'))
        # Adding a command loop with one working command plus the end packet
        return True

def command_loop(conn):
# Without current_dir = new_path inside the function would create a brand-new local variable
#  that only exists inside that function call and disappears afterward
    
    # global current_dir, open_write_file
    global current_dir, open_write_file
 
    while True:
        msg = conn.recv(2024).decode('utf-8')
        fields = msg.split("," , 2) # maxsplit=2 so arguments can't break the split
 
        if fields[0] == "End":
            break
 
        elif fields[0] == "CM" and len(fields) == 3 and fields[1] == "prompt":
            command = fields[2]
 
            # cd needs special handling as subprocess.run(shell=True) runs
            # in its own throwaway process, so a plain "cd folder" would
            # never actually change directory for the *next* command.
            # We detect it here and use os.chdir() on the server itself,
            # then run every other command inside current_dir via cwd=.
            stripped = command.strip()
            if stripped == "cd" or stripped.startswith("cd "):
                target = stripped[2:].strip() if len(stripped) > 2 else ""
                new_path = os.path.join(current_dir, target) if target else current_dir
                new_path = os.path.abspath(new_path)
                if os.path.isdir(new_path):
                    current_dir = new_path
                    conn.send("SC".encode('utf-8'))
                else:
                    conn.send("EE,03,command failed".encode('utf-8'))
                continue
 
            # run fields[2] (e.g. "mkdir folder1") with subprocess.run(..., shell=True)
            # returncode == 0 -> send "SC", else send "EE,03,command failed"
            result = subprocess.run(command, shell=True, cwd=current_dir)   # runs e.g. "mkdir test1" inside current_dir
            if result.returncode == 0:
                conn.send("SC".encode('utf-8'))
            else:
                conn.send("EE,03,command failed".encode('utf-8'))
 
        elif fields[0] == "CM" and len(fields) == 3 and fields[1] == "openRead":
            # openRead isn't a prompt command -- it's its own CM subtype.
            # Server opens the named file in read mode and sends its
            # contents straight back to the client.
            filename = fields[2]
            path = os.path.join(current_dir, filename)
            try:
                with open(path, "r") as f:
                    content = f.read()
                conn.send(content.encode('utf-8'))
            except Exception:
                conn.send("EE,04,file error".encode('utf-8'))
 
        elif fields[0] == "CM" and len(fields) == 3 and fields[1] == "openWrite":
            # openWrite isn't a prompt command either -- it opens/creates
            # the named file in write mode and keeps it open, waiting for
            # DP (data packet) messages witoh the actual content to save.
            filename = fields[2]
            path = os.path.join(current_dir, filename)
            try:
                open_write_file = open(path, "w")
                conn.send("SC".encode('utf-8'))
            except Exception:
                open_write_file = None
                conn.send("EE,04,file error".encode('utf-8'))
 
        elif fields[0] == "DP":
            # Data packet: (DP, text) -- text to save into whichever file
            # was opened with openWrite. Sent after openWrite, can be sent
            # multiple times for multiple chunks of data.
            if open_write_file is None:
                conn.send("EE,04,file error".encode('utf-8'))
            else:
                text = msg.split(",", 1)[1] if len(fields) > 1 else ""
                try:
                    open_write_file.write(text)
                    conn.send("SC".encode('utf-8'))
                except Exception:
                    conn.send("EE,04,file error".encode('utf-8'))
 
        else:
            conn.send("EE,01,malformed packet".encode('utf-8'))

    # while True:
    #     msg = conn.recv(2024).decode('utf-8')
    #     fields = msg.split("," , 2) # maxsplit=2 so arguments can't break the split 

    #     if fields[0] == "End":
    #         break

    #     elif fields[0] == "CM" and len(fields) == 3 and fields[1] == "prompt":
    #         # run fields[2] (e.g. "mkdir folder1") with subprocess.run(..., shell=True)
    #         # returncode == 0 -> send "SC", else send "EE,03,command failed"
    #         # pass # do nothing statement used for testing 
    #                     # cd needs special handling -- subprocess.run(shell=True) runs
    #         # in its own throwaway process, so a plain "cd folder" would
    #         # never actually change directory for the *next* command.
    #         # We detect it here and use os.chdir() on the server itself,
    #         # then run every other command inside current_dir via cwd=.
    #         stripped = command.strip()
    #         if stripped == "cd" or stripped.startswith("cd "):
    #             target = stripped[2:].strip() if len(stripped) > 2 else ""
    #             new_path = os.path.join(current_dir, target) if target else current_dir
    #             new_path = os.path.abspath(new_path)
    #             if os.path.isdir(new_path):
    #                 current_dir = new_path
    #                 conn.send("SC".encode('utf-8'))
    #             else:
    #                 conn.send("EE,03,command failed".encode('utf-8'))
    #             continue
 
    #         # run fields[2] (e.g. "mkdir folder1") with subprocess.run(..., shell=True)
    #         # returncode == 0 -> send "SC", else send "EE,03,command failed"
    #         result = subprocess.run(fields[2], shell=True)   # runs e.g. "mkdir test1"
    #         if result.returncode == 0:
    #             conn.send("SC".encode('utf-8'))
    #         else:
    #             conn.send("EE,03,command failed".encode('utf-8'))
    #     else:
    #         conn.send("EE,01,malformed packet".encode('utf-8'))

def main():
    welcomeSocket, conn = start_server(host, port)
    fields = recieve_setup(conn)
    if validate_setup(conn, fields):
        command_loop(conn)
    conn.close()
    welcomeSocket.close()# <-- added this cause there was an error

main()

