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
    if (bytes <= 0)
    {
        printf("No reply from server during setup\n");
        closesocket(client_fd);
        WSACleanup();
        return 1;
    }
    // recv does not add the string terminator, so we add it ourselves
    buffer[bytes] = '\0';

    // Server must reply with exactly CC
    // Anything else (for example EE,01,malformed packet) is an error
    if (strcmp(buffer, "CC") != 0)
    {
        printf("Setup failed, server replied: %s\n", buffer);
        closesocket(client_fd);
        WSACleanup();
        return 1;
    }
    printf("Setup complete, server confirmed the connection\n");
    // Operation Phase: Asking which file to read
    // The C client only supports the openRead command
    // %255s reads one word and stops at 255 characters so filename can't overflow
    char filename[256];
    char command[300];
    printf("Enter filename to read: ");
    if (scanf("%255s", filename) != 1)
    {
        printf("Could not read filename\n");
        closesocket(client_fd);
        WSACleanup();
        return 1;
    }

    // Building and Sending the Command Packet
    // Format: CM,openRead,<filename>
    // snprintf never writes more than the size of command
    snprintf(command, sizeof(command), "CM,openRead,%s", filename);
    send(client_fd, command, (int)strlen(command), 0);

    // Receiving the file contents (or an error packet)
    bytes = recv(client_fd, buffer, BUFFER_SIZE - 1, 0);
    if (bytes > 0)
    {
        buffer[bytes] = '\0';
        // EE = Exception-Packet, for example EE,04,file error when the file can't be opened
        if (strncmp(buffer, "EE,", 3) == 0)
        {
            printf("Server error: %s\n", buffer);
        }
        else
        {
            printf("File contents:\n%s\n", buffer);
        }
    }
    // Closing Phase
    // The End packet tells the server we are finished, then we clean up
    send(client_fd, "End", 3, 0);
    closesocket(client_fd);
    WSACleanup();
    return 0;
}