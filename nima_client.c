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
}