
import socket
import struct
import sys
import time

HOST = "127.0.0.1"
PORT = 123
TIMEOUT = 2.0

def build_client_request():
    # LI=0, VN=3, Mode=3 (client)
    LI = 0
    VN = 3
    MODE = 3
    first_byte = (LI << 6) | (VN << 3) | MODE
    pkt = bytearray(48)
    pkt[0] = first_byte
    # Transmit Timestamp = current time in NTP epoch (not strictly needed for check)
    return bytes(pkt)

def main():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(TIMEOUT)
        s.sendto(build_client_request(), (HOST, PORT))
        data, _ = s.recvfrom(512)
        # Basic sanity: NTP reply should be exactly 48 bytes
        if len(data) != 48:
            print(f"Unexpected length: {len(data)}")
            sys.exit(1)
        # Also check mode field in response is 4 (server)
        mode = data[0] & 0x7
        if mode != 4:
            print(f"Unexpected mode: {mode}")
            sys.exit(1)
        print("OK")
        sys.exit(0)
    except Exception as e:
        print(f"Healthcheck failure: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
