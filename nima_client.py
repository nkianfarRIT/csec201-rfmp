# Last updated: 04/10/2026

import socket
import os
import base64 # <-- turns encrypted bytes / PEM keys into comma-safe text for the packets

# --- Encryption imports, mirrors nima_server.py (same reasoning: RSA only protects the
# session key during the handshake; AES/Caesar + that session key protect the actual data) ---
from cryptography.hazmat.primitives.asymmetric import rsa, padding as rsa_padding
from cryptography.hazmat.primitives import hashes, serialization, padding as sym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

host = "127.0.0.1"          # changed from gethostname() in the mycourses
port = 8888 # Using 8888 as it doesn't interfere with the well-known range of used ports

# --- Secure-session state, only populated when the user opts into security = "1" ---
secure = False
algorithm = None       # "AES" or "Caesar"
session_key = None     # raw bytes we generate ourselves, then hand to the server via RSA

def connect_to_server(host, port):
    # creating socket, connecting & returning the socket object
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((host, port))
    return client # <-- preventing bug off nothing

# ---------------- crypto helpers (same implementations as the server side) ----------------

def pem_to_b64(key_obj, is_private=False):
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

def b64_to_public_key(b64_str):
    pem = base64.b64decode(b64_str)
    return serialization.load_pem_public_key(pem)

def rsa_encrypt_session_key(session_key_bytes, server_public_key):
    # Only the server's matching private key can undo this.
    ciphertext = server_public_key.encrypt(
        session_key_bytes,
        rsa_padding.OAEP(mgf=rsa_padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    return base64.b64encode(ciphertext).decode('utf-8')

def caesar_shift_from_key(key_bytes):
    return (sum(key_bytes) % 25) + 1

def caesar_encrypt(text, shift):
    result = []
    for ch in text:
        if ch.isalpha():
            base_ord = ord('A') if ch.isupper() else ord('a')
            result.append(chr((ord(ch) - base_ord + shift) % 26 + base_ord))
        else:
            result.append(ch)
    return "".join(result)

def caesar_decrypt(text, shift):
    return caesar_encrypt(text, -shift % 26)

def aes_encrypt(plaintext_str, key):
    iv = os.urandom(16)
    padder = sym_padding.PKCS7(128).padder()
    padded = padder.update(plaintext_str.encode('utf-8')) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(iv + ciphertext).decode('utf-8')

def aes_decrypt(token_b64, key):
    raw = base64.b64decode(token_b64)
    iv, ciphertext = raw[:16], raw[16:]
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = sym_padding.PKCS7(128).unpadder()
    return (unpadder.update(padded) + unpadder.finalize()).decode('utf-8')

def encrypt_text(plaintext_str):
    if algorithm == "AES":
        return aes_encrypt(plaintext_str, session_key)
    else:
        shift = caesar_shift_from_key(session_key)
        return caesar_encrypt(plaintext_str, shift)

def decrypt_text(token_str):
    if algorithm == "AES":
        return aes_decrypt(token_str, session_key)
    else:
        shift = caesar_shift_from_key(session_key)
        return caesar_decrypt(token_str, shift)

def do_setup(client, secure_flag):
    # sending our string
    # client.send("Hello s".encode('utf-8')) # <-- same structure as my courses
    client.send(("SS,RFMP,v1.0," + secure_flag).encode('utf-8'))

def setup_result(client, secure_flag):
    global secure, algorithm, session_key

    reply = client.recv(4096).decode('utf-8')

    if secure_flag == "0":
        fields = reply.split(",")
        if fields[0] != "CC" or len(fields) != 1:
            print("Error was:", reply)
            return False
        secure = False
        return True

    # secure_flag == "1" --> expect (CC, Server_public_key)
    fields = reply.split(",", 1)
    if fields[0] != "CC" or len(fields) != 2:
        print("Error was:", reply)
        return False

    secure = True
    server_public_key = b64_to_public_key(fields[1])

    # Client prepares its three keys per the spec: a random session key for AES/Caesar,
    # plus its own RSA keypair (the public half rides along in the EC packet's credentials
    # field; nothing in this simplified project actually decrypts anything *with* it, since
    # the server never sends the client anything RSA-encrypted, but it keeps the packet
    # shape matching (EC, Algorithm, session_key, username:Client_public_key)).
    session_key = os.urandom(16)  # 16 bytes = valid AES-128 key, and plenty of entropy for the Caesar shift
    client_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    client_public_b64 = pem_to_b64(client_private_key.public_key(), is_private=False)

    algo_choice = ""
    while algo_choice not in ("AES", "Caesar"):
        algo_choice = input("Choose encryption algorithm (AES/Caesar): ").strip()
    algorithm = algo_choice

    encrypted_key_b64 = rsa_encrypt_session_key(session_key, server_public_key)
    username = "faaiz"  # per-project username field required by the EC packet's credentials

    ec_packet = "EC," + algorithm + "," + encrypted_key_b64 + "," + username + ":" + client_public_b64
    client.send(ec_packet.encode('utf-8'))

    ack = client.recv(2024).decode('utf-8')
    if ack != "SC":
        print("Error was:", ack)
        return False

    return True

# Verifying if the field were correct using the same structure as the server.py
# if & elif statements
# Our set of error codes:
# 01  malformed packet
# 02  unsupported protocol or version
# 03  command failed
# 04  file error

# Menu shown to the user so they can pick an option instead of typing raw commands
MENU = """
========= RFMP Client =========
 1) mkdir      - create a folder
 2) cd         - change directory
 3) rmdir      - delete a folder
 4) del        - delete a file
 5) ren        - rename a file/folder
 6) openRead   - read a file from the server
 7) openWrite  - write text to a file on the server
 8) Other command (whoami, ls, hostname, date, uptime)
 0) Exit
==============================="""
def build_command():
    # Turns the user's menu choice into the same command string the loop already handles
    print(MENU)
    choice = input("Choose an option: ").strip()
    if choice == "1": return "mkdir " + input("Folder name: ").strip()
    if choice == "2": return "cd " + input("Path: ").strip()
    if choice == "3": return "rmdir " + input("Folder name: ").strip()
    if choice == "4": return "del " + input("File name: ").strip()
    if choice == "5": return "ren " + input("Current name: ").strip() + " " + input("New name: ").strip()
    if choice == "6": return "openRead " + input("File name: ").strip()
    if choice == "7": return "openWrite " + input("File name: ").strip()
    if choice == "8": return input("Command: ").strip()
    if choice == "0": return "exit"
    return None  # anything else is an invalid option
def command_loop(client):
    while True:
        usercommand = build_command()  # menu replaces the old free-text "Enter a command" prompt
        if usercommand is None:
            print("Invalid option, try again")
            continue
        
        if usercommand == "exit" or usercommand == "Exit":
            client.send("End".encode('utf-8')) # tell the server the user wrote exit
            break # stop the client loop cause End was sent to server
        elif usercommand.startswith("openWrite "):
            filename = usercommand[len("openWrite "):].strip()
            client.send(("CM,openWrite," + filename).encode('utf-8'))
            reply = client.recv(2024).decode('utf-8')
            print("Server:", reply)
            if reply == "SC":
                data = input("Enter the text to write: ")
                # Spec: encrypt the text field before sending when the session is secured.
                if secure:
                    data = encrypt_text(data)
                client.send(("DP," + data).encode('utf-8'))
                reply = client.recv(2024).decode('utf-8')
                print("Server:", reply)

        elif usercommand.startswith("openRead "):
            filename = usercommand[len("openRead "):].strip()
            client.send(("CM,openRead," + filename).encode('utf-8'))
            reply = client.recv(4096).decode('utf-8')
            # Server encrypts the file contents before sending them back when secured,
            # so decrypt here before showing the user the real text.
            if secure and not reply.startswith("EE,"):
                try:
                    reply = decrypt_text(reply)
                except Exception:
                    print("Warning: could not decrypt server reply, showing raw text")
            print("Server:", reply)

        else:
            # client.send(("CM,prompt,",usercommand).encode('utf-8')) # <-- apparently ,usercommand makes it into a tuple
            client.send(("CM,prompt," + usercommand).encode('utf-8')) # plus to prevent tuple
            reply = client.recv(2024).decode('utf-8') # <-- server's reply from the command
            print("Server:", reply)

def main():
    client = connect_to_server(host, port)

    secure_flag = ""
    while secure_flag not in ("0", "1"):
        secure_flag = input("Secure communication? (1 = yes, 0 = no): ").strip()

    do_setup(client, secure_flag)
    if not setup_result(client, secure_flag):
        print("Setup failed, closing connection")
    else:
        print("Setup complete, server confirmed the connection" + (" (secure)" if secure_flag == "1" else ""))
        command_loop(client)
    client.close()

main()