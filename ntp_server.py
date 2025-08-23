import socket
import struct
import time
import queue
import threading
import select
import logging, sys, time
import sys
import os
import datetime

tz = os.getenv("TZ", "UTC")  # default UTC if not set
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)

if hasattr(time, "tzset"):
    time.tzset()


IGNORE_CLIENT_IPS = set(
    ip.strip() for ip in os.getenv("IGNORE_CLIENT_IPS", "").split(",") if ip.strip()
)
logging.info("Ignoring IPs for logging: %s", ", ".join(IGNORE_CLIENT_IPS) or "None")


# Global variables
taskQueue = queue.Queue()
stopFlag = False


def system_to_ntp_time(timestamp):
    """Convert system time (Unix epoch) to NTP time."""
    return timestamp + NTP.NTP_DELTA


def _to_int(timestamp):
    """Return the integral part of a timestamp."""
    return int(timestamp)


def _to_frac(timestamp, n=32):
    """Return the fractional part of a timestamp."""
    return int(abs(timestamp - _to_int(timestamp)) * 2 ** n)


def _to_time(integ, frac, n=32):
    """Return a timestamp from its integral and fractional parts."""
    return integ + float(frac) / 2 ** n


class NTPException(Exception):
    """Exception raised by this module."""
    pass


class NTP:
    """Helper class defining constants."""

    _SYSTEM_EPOCH = datetime.date(*time.gmtime(0)[:3])  # 1970-01-01
    _NTP_EPOCH    = datetime.date(1900, 1, 1)
    NTP_DELTA = (_SYSTEM_EPOCH - _NTP_EPOCH).days * 24 * 3600

    REF_ID_TABLE = {
        'DNC': "DNC routing protocol",
        'NIST': "NIST public modem",
        'TSP': "TSP time protocol",
        'DTS': "Digital Time Service",
        'ATOM': "Atomic clock (calibrated)",
        'VLF': "VLF radio (OMEGA, etc)",
        'callsign': "Generic radio",
        'LORC': "LORAN-C radionavidation",
        'GOES': "GOES UHF environment satellite",
        'GPS': "GPS UHF satellite positioning",
    }

    STRATUM_TABLE = {
        0: "unspecified",
        1: "primary reference",
    }

    MODE_TABLE = {
        0: "unspecified",
        1: "symmetric active",
        2: "symmetric passive",
        3: "client",
        4: "server",
        5: "broadcast",
        6: "reserved for NTP control messages",
        7: "reserved for private use",
    }

    LEAP_TABLE = {
        0: "no warning",
        1: "last minute has 61 seconds",
        2: "last minute has 59 seconds",
        3: "alarm condition (clock not synchronized)",
    }


class NTPPacket:
    """Represents an NTP packet."""
    _PACKET_FORMAT = "!B B B b 11I"

    def __init__(self, version=2, mode=3, tx_timestamp=0):
        self.leap = 0  # Leap indicator
        self.version = version  # NTP version
        self.mode = mode  # Mode (client/server)
        self.stratum = 0
        self.poll = 0
        self.precision = 0
        self.root_delay = 0
        self.root_dispersion = 0
        self.ref_id = 0
        self.ref_timestamp = 0
        self.orig_timestamp = 0
        self.orig_timestamp_high = 0
        self.orig_timestamp_low = 0
        self.recv_timestamp = 0
        self.tx_timestamp = tx_timestamp
        self.tx_timestamp_high = 0
        self.tx_timestamp_low = 0

    def to_data(self):
        """Convert this NTPPacket into a binary buffer."""
        try:
            packed = struct.pack(
                NTPPacket._PACKET_FORMAT,
                (self.leap << 6 | self.version << 3 | self.mode),
                self.stratum,
                self.poll,
                self.precision,
                _to_int(self.root_delay) << 16 | _to_frac(self.root_delay, 16),
                _to_int(self.root_dispersion) << 16 | _to_frac(self.root_dispersion, 16),
                self.ref_id,
                _to_int(self.ref_timestamp),
                _to_frac(self.ref_timestamp),
                self.orig_timestamp_high,
                self.orig_timestamp_low,
                _to_int(self.recv_timestamp),
                _to_frac(self.recv_timestamp),
                _to_int(self.tx_timestamp),
                _to_frac(self.tx_timestamp)
            )
        except struct.error:
            raise NTPException("Invalid NTP packet fields.")
        return packed

    def from_data(self, data):
        """Populate this packet from a received binary buffer."""
        pkt_len = struct.calcsize(NTPPacket._PACKET_FORMAT)
        if len(data) < pkt_len:
            raise NTPException("Invalid NTP packet: too short (" + str(len(data)) + " bytes)")
        try:
            unpacked = struct.unpack(
                NTPPacket._PACKET_FORMAT,
                data[0:pkt_len]
            )
        except struct.error:
            raise NTPException("Invalid NTP packet: unpack error")

        self.leap = (unpacked[0] >> 6) & 0x3
        self.version = (unpacked[0] >> 3) & 0x7
        self.mode = unpacked[0] & 0x7
        self.stratum = unpacked[1]
        self.poll = unpacked[2]
        self.precision = unpacked[3]
        self.root_delay = float(unpacked[4]) / 2 ** 16
        self.root_dispersion = float(unpacked[5]) / 2 ** 16
        self.ref_id = unpacked[6]
        self.ref_timestamp = _to_time(unpacked[7], unpacked[8])
        self.orig_timestamp = _to_time(unpacked[9], unpacked[10])
        self.orig_timestamp_high = unpacked[9]
        self.orig_timestamp_low = unpacked[10]
        self.recv_timestamp = _to_time(unpacked[11], unpacked[12])
        self.tx_timestamp = _to_time(unpacked[13], unpacked[14])
        self.tx_timestamp_high = unpacked[13]
        self.tx_timestamp_low = unpacked[14]

    def GetTxTimeStamp(self):
        return (self.tx_timestamp_high, self.tx_timestamp_low)

    def SetOriginTimeStamp(self, high, low):
        self.orig_timestamp_high = high
        self.orig_timestamp_low = low


class RecvThread(threading.Thread):
    def __init__(self, sock):
        super().__init__()
        self.sock = sock

    def run(self):
        global taskQueue, stopFlag
        while True:
            if stopFlag:
                print("RecvThread Ended")
                break
            rlist, _, _ = select.select([self.sock], [], [], 1)
            if rlist:
                for s in rlist:
                    try:
                        data, addr = s.recvfrom(1024)
                        recvTimestamp = system_to_ntp_time(time.time())
                        taskQueue.put((data, addr, recvTimestamp))
                    except socket.error as msg:
                        print(msg)


class WorkThread(threading.Thread):
    def __init__(self, sock):
        super().__init__()
        self.sock = sock

    def run(self):
        global taskQueue, stopFlag
        while True:
            if stopFlag:
                print("WorkThread Ended")
                break
            try:
                data, addr, recvTimestamp = taskQueue.get(timeout=1)
                recvPacket = NTPPacket()
                try:
                    recvPacket.from_data(data)
                except NTPException:
                    # ignore malformed/short packets
                    continue
                timeStamp_high, timeStamp_low = recvPacket.GetTxTimeStamp()
                sendPacket = NTPPacket(version=3, mode=4)
                sendPacket.stratum = 2
                sendPacket.poll = 10
                sendPacket.ref_timestamp = recvTimestamp - 5
                sendPacket.SetOriginTimeStamp(timeStamp_high, timeStamp_low)
                sendPacket.recv_timestamp = recvTimestamp
                sendPacket.tx_timestamp = system_to_ntp_time(time.time())
                #### Time with timezone
                ## Get local time zone offset in seconds
                #tz_offset = int(datetime.datetime.now().astimezone().utcoffset().total_seconds())
                ## Append the 4-byte timezone offset extension to the standard packet
                #response = sendPacket.to_data() + struct.pack("!i", tz_offset)
                
                
                #### Time without timezone
                response = sendPacket.to_data()

                self.sock.sendto(response, addr)
                if addr[0] not in IGNORE_CLIENT_IPS:
                    logging.info("Handled NTP request from %s", addr[0])
            except queue.Empty:
                continue


def main():
    listenIp = "0.0.0.0"
    listenPort = 123
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((listenIp, listenPort))
    logging.info(f"Listening on {sock.getsockname()}")

    recvThread = RecvThread(sock)
    recvThread.start()
    workThread = WorkThread(sock)
    workThread.start()

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Exiting...")
        global stopFlag
        stopFlag = True
        recvThread.join()
        workThread.join()
        print("Exited")


if __name__ == '__main__':
    main()
