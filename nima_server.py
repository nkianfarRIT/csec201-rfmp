# Last updated: 30/09/2026

import socket
import subprocess # <-- Importing subprocess to run commands
import os, sys, stat # <-- Same structure pasted from the sample mycourses
import base64 # <-- used to turn encrypted bytes into comma-safe text for the packets
import threading # <-- 1 thread per client same structure as the mycourses example will be implemented

# --- Encryption imports (RSA for the session-key handshake, AES/Caesar for the data) ---
# AI-generated section (per assignment instructions, encryption code can be GenAI-assisted,
# comments below explain what each part does so it can be walked through in discussion).
from cryptography.hazmat.primitives.asymmetric import rsa, padding as rsa_padding
from cryptography.hazmat.primitives import hashes, serialization, padding as sym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


host = "127.0.0.1"          # changed from gethostname() in the mycourses
port = 8888 # Using 8888 as it doesn't interfere with the well-known range of used ports

# multithreading note: the variables below were the single-client globals. They are kept
# here for reference, but each ClientThread now has its own copy on self (self.current_dir,
# self.session_key, ...) so two clients can't overwrite each other's key or directory.

class ClientThread(threading.Thread):
    # One ClientThread per connected client (same structure as myThread in TCPServerExampleThreading.py).
    # Everything on self belongs to that client only.
    # Every function inside the class takes self as its first parameter, and calls
    # other functions in the class as self.function_name(...)

    def __init__(self, conn, addr):
        threading.Thread.__init__(self)
        self.conn = conn
        self.addr = addr

        # per-client copies of the old globals above
        self.current_dir = os.getcwd()
        self.open_write_file = None
        self.secure = False
        self.algorithm = None
        self.session_key = None
        self.server_private_key = None
        self.server_public_key = None

        print("Got a connection from %s" % str(self.addr))

    def run(self):
        # run() is what t1.start() calls inside the new thread
        fields = self.recieve_setup()
        if self.validate_setup(fields):
            self.command_loop()
        # cleanup for this client only
        if self.open_write_file is not None:
            self.open_write_file.close()
            self.open_write_file = None
        self.conn.close()
        print("client:%s has ended connection" % str(self.addr))


    # Tracks the server's "current directory" across commands, since cd
    # can't be done with subprocess.run(shell=True) -- that spawns a brand
    # new process each call, so a normal shell "cd" would have no effect
    # on the next command.
    current_dir = os.getcwd() # getcwd returns a unicode string of the directory

    # Keeps track of a file opened with openWrite so the next DP packet(s)
    # know where to write. None when no file is open for writing. (will be changed when client asks)
    open_write_file = None

    # --- Secure-session state (only used when the Start-Packet asked for security = "1") ---
    # (these are class-level defaults; __init__ sets self.* copies so each thread uses its own)
    secure = False              # whether this connection negotiated encryption
    algorithm = None            # "AES" or "Caesar", chosen by the client in the EC packet
    session_key = None          # raw bytes, decrypted from the client's EC packet using RSA
    server_private_key = None   # generated fresh per run, never leaves the server
    server_public_key = None    # sent to the client in the Confirm-Connection-Packet


    def generate_rsa_keypair(self):
        # 2048-bit RSA keypair for the handshake. Only used to protect the session_key,
        # never to encrypt the actual file data (that's what the session key + AES/Caesar is for).
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        return private_key, private_key.public_key()


    def pem_to_b64(self, key_obj, is_private=False):
        # Serialize a key object to PEM text, then base64 it so it survives as a single
        # comma-safe field inside our plain "field,field,field" packet format.
        if is_private:
            pem = key_obj.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        else:
            pem = key_obj.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        return base64.b64encode(pem).decode('utf-8')


    def b64_to_public_key(self, b64_str):
        pem = base64.b64decode(b64_str)
        return serialization.load_pem_public_key(pem)


    def rsa_decrypt_session_key(self, encrypted_b64):
        # Client encrypted the session key with OUR public key; only our private key can open it.
        ciphertext = base64.b64decode(encrypted_b64)
        return self.server_private_key.decrypt(
            ciphertext,
            rsa_padding.OAEP(mgf=rsa_padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
        )


    def caesar_shift_from_key(self, key_bytes):
        # Turn the random session key into a repeatable shift 1-25 instead of hardcoding one.
        return (sum(key_bytes) % 25) + 1


    def caesar_encrypt(self, text, shift):
        result = []
        for ch in text:
            if ch.isalpha():
                base_ord = ord('A') if ch.isupper() else ord('a')
                result.append(chr((ord(ch) - base_ord + shift) % 26 + base_ord))
            else:
                result.append(ch)  # leave spaces/digits/punctuation untouched
        return "".join(result)


    def caesar_decrypt(self, text, shift):
        return self.caesar_encrypt(text, -shift % 26)


    def aes_encrypt(self, plaintext_str, key):
        # Fresh random IV every call (never reuse an IV with the same key), PKCS7-pad to the
        # 16-byte AES block size, then prepend the IV to the ciphertext so decrypt() can find it.
        iv = os.urandom(16)
        padder = sym_padding.PKCS7(128).padder()
        padded = padder.update(plaintext_str.encode('utf-8')) + padder.finalize()
        encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
        ciphertext = encryptor.update(padded) + encryptor.finalize()
        return base64.b64encode(iv + ciphertext).decode('utf-8')


    def aes_decrypt(self, token_b64, key):
        raw = base64.b64decode(token_b64)
        iv, ciphertext = raw[:16], raw[16:]
        decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()
        unpadder = sym_padding.PKCS7(128).unpadder()
        return (unpadder.update(padded) + unpadder.finalize()).decode('utf-8')


    def encrypt_text(self, plaintext_str):
        # Single entry point used by both openRead (server->client) and command_loop
        # so the caller doesn't need to care which algorithm was negotiated.
        if self.algorithm == "AES":
            return self.aes_encrypt(plaintext_str, self.session_key)
        else:  # "Caesar"
            shift = self.caesar_shift_from_key(self.session_key)
            return self.caesar_encrypt(plaintext_str, shift)


    def decrypt_text(self, token_str):
        if self.algorithm == "AES":
            return self.aes_decrypt(token_str, self.session_key)
        else:  # "Caesar"
            shift = self.caesar_shift_from_key(self.session_key)
            return self.caesar_decrypt(token_str, shift)


    def start_server(self, host, port):
        # (single-client version kept as reference, main ignores it an accepts in a loop instead)
        welcomeSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        welcomeSocket.bind((host, port))
        welcomeSocket.listen(5)
        print("Server is listening at port " + str(port))
        conn, addr = welcomeSocket.accept()
        print("Client connected!")
        return welcomeSocket, conn


    # message = conn.recv(2024).decode('utf-8')
    # print("Server got:", message)

    def recieve_setup(self):
        message = self.conn.recv(2024).decode('utf-8')   # "SS,RFMP,v1.0,0" is being recieved from client.py
        fields = message.split(",")                 # ["SS", "RFMP", "v1.0", "0"] is being split at the instance of the comma in the string
        print("From Client", self.addr, "to Server:", fields)     # Should print the 4 fields
        return fields

    # if fields[0] != "SS" or fields[1] != "RFMP" or fields[2] != "v1.0" or fields[3] != "0":
    #     conn.send("EE, 01 or 02, malformed packet or unsupported protocol or version".encode('utf-8')) <-- not suitable error handling so gonna update it

    # Our set of error codes:
    # 01  malformed packet
    # 02  unsupported protocol or version
    # 03  command failed
    # 04  file error



    def validate_setup(self, fields):
        # global secure, algorithm, session_key, server_private_key, server_public_key <-- not needed since using threads (self.*)

        if len(fields) != 4 or fields[0] != "SS" or fields[3] not in ("0", "1"):
            # Wrong shape, wrong type, or a secure-flag that isn't 0/1 --> structural problem much better than 01 or 02 error code
            self.conn.send("EE,01,malformed packet".encode('utf-8')) # Fixed the field seperation for both 01 and 02
            return False

        elif fields[1] != "RFMP" or fields[2] != "v1.0":
            # Packet is well-formed, we just don't speak this protocol/version
            self.conn.send("EE,02,unsupported protocol or version".encode('utf-8')) # <-- much better than 01 or 02 as now its seprate
            return False

        elif fields[3] == "0":
            # Unsecured path -- unchanged from teammate's version.
            self.secure = False
            self.conn.send("CC".encode('utf-8'))
            return True

        else:
            # fields[3] == "1" --> secure path.
            self.secure = True
            self.server_private_key, self.server_public_key = self.generate_rsa_keypair()
            server_pub_b64 = self.pem_to_b64(self.server_public_key, is_private=False)
            # Confirm-Connection-Packet now carries our public key: (CC, Server_public_key)
            self.conn.send(("CC," + server_pub_b64).encode('utf-8'))

            # Server now expects an Encryption-Packet before any commands:
            # (EC, Algorithm, session_key_encrypted_b64, username:Client_public_key_b64)
            ec_msg = self.conn.recv(4096).decode('utf-8')
            ec_fields = ec_msg.split(",", 3)
            if len(ec_fields) != 4 or ec_fields[0] != "EC" or ec_fields[1] not in ("AES", "Caesar"):
                self.conn.send("EE,01,malformed packet".encode('utf-8'))
                return False

            try:
                self.algorithm = ec_fields[1]
                self.session_key = self.rsa_decrypt_session_key(ec_fields[2])
                # ec_fields[3] is "username:Client_public_key_b64" -- the client's public key
                # isn't used again in this simplified project (nothing is ever RSA-encrypted
                # *for* the client), but we still parse it out to match the packet spec and
                # so a mismatched/garbled credentials field still gets caught as an error.
                username, _, _client_pub_b64 = ec_fields[3].partition(":")
                if not username:
                    raise ValueError("missing username in credentials field")
            except Exception:
                self.conn.send("EE,01,malformed packet".encode('utf-8'))
                return False

            self.conn.send("SC".encode('utf-8'))  # acknowledge the EC packet, then move into the command loop
            return True

    def command_loop(self):
    # Without current_dir = new_path inside the function would create a brand-new local variable
    #  that only exists inside that function call and disappears afterward

        # global current_dir, open_write_file <-- not needed since using threads

        while True:
            msg = self.conn.recv(2024).decode('utf-8')

            if not msg:
                # Empty recv = client closed the socket without sending End (e.g. closed the window).
                # Without this the thread would keep sending EE,01 to a dead socket and crash.
                break

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
                    new_path = os.path.join(self.current_dir, target) if target else self.current_dir
                    new_path = os.path.abspath(new_path)
                    if os.path.isdir(new_path):
                        self.current_dir = new_path
                        self.conn.send("SC".encode('utf-8'))
                    else:
                        self.conn.send("EE,03,command failed".encode('utf-8'))
                    continue

                # run fields[2] (e.g. "mkdir folder1") with subprocess.run(..., shell=True)
                # returncode == 0 -> send "SC", else send "EE,03,command failed"
                result = subprocess.run(command, shell=True, cwd=self.current_dir)   # runs e.g. "mkdir test1" inside current_dir
                if result.returncode == 0:
                    self.conn.send("SC".encode('utf-8'))
                else:
                    self.conn.send("EE,03,command failed".encode('utf-8'))

            elif fields[0] == "CM" and len(fields) == 3 and fields[1] == "openRead":
                # openRead isn't a prompt command -- it's its own CM subtype.
                # Server opens the named file in read mode and sends its
                # contents straight back to the client.
                filename = fields[2]
                path = os.path.join(self.current_dir, filename)
                try:
                    with open(path, "r") as f:
                        content = f.read()
                    # Spec: if the session is secured, encrypt the file contents with the
                    # session key before sending them back -- the client decrypts on arrival.
                    if self.secure:
                        content = self.encrypt_text(content)
                    self.conn.send(content.encode('utf-8'))
                except Exception:
                    self.conn.send("EE,04,file error".encode('utf-8'))

            elif fields[0] == "CM" and len(fields) == 3 and fields[1] == "openWrite":
                # openWrite isn't a prompt command either -- it opens/creates
                # the named file in write mode and keeps it open, waiting for
                # DP (data packet) messages witoh the actual content to save.
                filename = fields[2]
                path = os.path.join(self.current_dir, filename)
                try:
                    self.open_write_file = open(path, "w")
                    self.conn.send("SC".encode('utf-8'))
                except Exception:
                    self.open_write_file = None
                    self.conn.send("EE,04,file error".encode('utf-8'))

            elif fields[0] == "DP":
                # Data packet: (DP, text) -- text to save into whichever file
                # was opened with openWrite. Sent after openWrite, can be sent
                # multiple times for multiple chunks of data.
                if self.open_write_file is None:
                    self.conn.send("EE,04,file error".encode('utf-8'))
                else:
                    text = msg.split(",", 1)[1] if len(fields) > 1 else ""
                    try:
                        # Spec: the text field arrives encrypted when the session is secured,
                        # so decrypt with the session key before writing plaintext to disk.
                        if self.secure:
                            text = self.decrypt_text(text)
                        self.open_write_file.write(text)
                        self.open_write_file.flush()  # <-- fix: without this, a same-session openRead can see an
                                                #     empty/incomplete file because the OS hasn't flushed yet
                        self.conn.send("SC".encode('utf-8'))
                    except Exception:
                        self.conn.send("EE,04,file error".encode('utf-8'))

            else:
                self.conn.send("EE,01,malformed packet".encode('utf-8'))

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

# def main():   <-- single-client version, kept for reference
#     welcomeSocket, conn = start_server(host, port)
#     fields = recieve_setup(conn)
#     if validate_setup(conn, fields):
#         command_loop(conn)
#     conn.close()
#     welcomeSocket.close()# <-- added this cause there was an error

def main():
    # Multithreaded version, same pattern as TCPServerExampleThreading.py:
    # accept forever, give each client its own ClientThread, go straight back to accept().
    welcomeSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    welcomeSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # lets the server restart right away without "Address already in use" on port 8888
    welcomeSocket.bind((host, port))
    welcomeSocket.listen(5)
    print("Server is listening at port " + str(port))
    while True:
        conn, addr = welcomeSocket.accept()
        t1 = ClientThread(conn, addr)
        t1.start()

main()