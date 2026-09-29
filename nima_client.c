#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <winsock2.h> // Core Windows Sockets API
#include <ws2tcpip.h> // IP address formatting functions (inet_pton)

// Linking Windows Socket Library to GCC compilers
#pragma comment(lib, "ws2_32.lib")

#define SERVER_IP "127.0.0.1" // Server IP address (localhost)
#define PORT 8888             // Server port number matching
#define BUFFER_SIZE 2024

int main()
{
    // Initializing Windows Sockets DLL
    // Required on Windows to using any network sockets
    WSADATA wsaData;
    int wsa_result = WSAStartup(MAKEWORD(2, 2), &wsaData);
    if (wsa_result != 0)
    {
        printf("WSAStartup failed with error code: %d\n", wsa_result);
        return 1;
    }

    // Creating TCP Socket
    // AF_INET     = IPv4 addressing family
    // SOCK_STREAM = TCP protocol (reliable, connection-oriented)
    // 0           = Default IP protocol
    SOCKET client_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (client_fd == INVALID_SOCKET)
    {
        printf("Socket creation failed with error code: %d\n", WSAGetLastError());
        WSACleanup();
        return 1;
    }

    // Configuring Server Address Structure
    // memset fills the struct with zeros so no leftover values remain
    // htons converts the port number to network byte order
    // inet_pton converts the IP text "127.0.0.1" into its binary form
    struct sockaddr_in server_addr;
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(PORT);
    inet_pton(AF_INET, SERVER_IP, &server_addr.sin_addr);

    // Connecting to Server
    // SOCKET_ERROR means the server is not running or not reachable
    int connect_result = connect(client_fd, (struct sockaddr *)&server_addr, sizeof(server_addr));
    if (connect_result == SOCKET_ERROR)
    {
        printf("Connection failed with error code: %d\n", WSAGetLastError());
        closesocket(client_fd);
        WSACleanup();
        return 1;
    }
    printf("Connected to server!\n");


    // Creating Receive Buffer
    // Every reply from the server is stored here before we read it
    char buffer[BUFFER_SIZE];

    // Setup Phase: Sending the Start-Packet
    // SS = start, RFMP = protocol name, v1.0 = version, 0 = unsecured (no encryption)
    const char *start_packet = "SS,RFMP,v1.0,0";
    send(client_fd, start_packet, (int)strlen(start_packet), 0);

    // Setup Phase: Waiting for the Confirm-Connection-Packet
    // recv returns the number of bytes received (0 = connection closed, negative = error)
    int bytes = recv(client_fd, buffer, BUFFER_SIZE - 1, 0);
    if(bytes <= 0){
        printf("No reply from server during setup\n");
        closesocket(client_fd);
        WSACleanup();
        return 1;
    }
    // recv does not add the string terminator, so we add it ourselves
    buffer[bytes] = '\0';

    // Server must reply with exactly CC
    // Anything else (for example EE,01,malformed packet) is an error
    if(strcmp(buffer, "CC") != 0){
        printf("Setup failed, server replied: %s\n", buffer);
        closesocket(client_fd);
        WSACleanup();
        return 1;
    }
    printf("Setup complete, server confirmed the connection\n");
}