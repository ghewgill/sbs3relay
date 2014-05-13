import asyncore
import datetime
import select
import socket
import sys
import time

class Decoder:
    DLE = 0x10
    STX = 0x02
    ETX = 0x03
    StNone = "none" #object()
    StSTX = "STX" #object()
    StType = "Type" #object()
    StData = "Data" #object()
    StCRC1 = "CRC1" #object()
    StCRC2 = "CRC2" #object()
    def __init__(self, handler):
        self.handler = handler
        self.state = Decoder.StNone
        self.dle = False
        self.packet = None
        self.crchi = 0
        self.crclo = 0
    def handle(self, buf):
        for c in buf:
            if self.state is Decoder.StNone:
                if c == Decoder.DLE:
                    self.state = Decoder.StSTX
                    self.dle = False
            elif self.state is Decoder.StSTX:
                if c == Decoder.STX:
                    self.state = Decoder.StType
                else:
                    print("decode error: state={}, c={}".format(self.state, c), file=sys.stderr)
                    self.state = Decoder.StNone
            elif self.state is Decoder.StType:
                if c != Decoder.DLE:
                    self.packet = [c]
                    self.state = Decoder.StData
                else:
                    print("decode error: state={}, c={}".format(self.state, c), file=sys.stderr)
                    self.state = Decoder.StNone
            elif self.state is Decoder.StData:
                if self.dle:
                    self.dle = False
                    if c == Decoder.DLE:
                        self.packet.append(c)
                    elif c == Decoder.ETX:
                        self.state = Decoder.StCRC1
                    else:
                        print("decode error: state={}, c={}".format(self.state, c), file=sys.stderr)
                        self.state = Decoder.StNone
                elif c == Decoder.DLE:
                    self.dle = True
                else:
                    self.packet.append(c)
            elif self.state is Decoder.StCRC1:
                if self.dle:
                    self.dle = False
                    if c == Decoder.DLE:
                        self.crchi = c
                        self.state = Decoder.StCRC2
                    else:
                        print("decode error: state={}, c={}".format(self.state, c), file=sys.stderr)
                        self.state = Decoder.StNone
                elif c == Decoder.DLE:
                    self.dle = True
                else:
                    self.crchi = c
                    self.state = Decoder.StCRC2
            elif self.state is Decoder.StCRC2:
                if self.dle:
                    self.dle = False
                    if c == Decoder.DLE:
                        self.crclo = c
                        self.state = Decoder.StNone
                        self.handler(self.packet, self.crc())
                    else:
                        print("decode error: state={}, c={}".format(self.state, c), file=sys.stderr)
                        self.state = Decoder.StNone
                elif c == Decoder.DLE:
                    self.dle = True
                else:
                    self.crclo = c
                    self.state = Decoder.StNone
                    self.handler(self.packet, self.crc())
    def crc(self):
        return (self.crchi << 8) + self.crclo

class AircraftInfo:
    def __init__(self, identity):
        self.seen = 0
        self.identity = identity
        self.addr = -1
        self.aircraft_type = -1
        self.flight = ""
        self.altitude = -1
        self.raw_latitude = -1
        self.raw_longitude = -1

Aircraft = dict()
LastUpdate = 0

ais_charset = "?ABCDEFGHIJKLMNOPQRSTUVWXYZ????? ???????????????0123456789??????"

def decodeAC12(msg):
    if msg[5] & 1:
        n = ((msg[5] >> 1) << 4) | (msg[6] >> 4)
        return 25 * n - 1000

def update():
    print("\x1b[H\x1b[2J", end="")
    print("Seen     Squawk Address Type Flight   Altitude Latitude Longitude")
    now = time.time()
    for ai in sorted(Aircraft.values(), key=lambda x: x.seen, reverse=True):
        age = now - ai.seen
        if age < 300:
            ts = time.gmtime(ai.seen)
            print("{0:02}:{1:02}:{2:02} {identity:04}   {addr:06x}  {aircraft_type:4} {flight:8} {altitude:8} {raw_latitude:8} {raw_longitude:9}".format(ts.tm_hour, ts.tm_min, ts.tm_sec, **ai.__dict__))
        else:
            del Aircraft[ai.identity]
    if not hasattr(update, "i"):
        update.i = 0
    print("|/-\\"[update.i], end="")
    update.i = (update.i + 1) % 4
    sys.stdout.flush()

def packet(buf, crc):
    if buf[0] == 0x01:
        #print("packet:", datetime.datetime.today().isoformat(), " ".join("{:02x}".format(x) for x in buf), "{:04x}".format(crc))
        msg = buf[5:]
        msgtype = msg[0] >> 3
        a = ((msg[3] & 0x80) >> 5) | ((msg[2] & 0x02) >> 0) | ((msg[2] & 0x08) >> 3)
        b = ((msg[3] & 0x02) << 1) | ((msg[3] & 0x08) >> 2) | ((msg[3] & 0x20) >> 5)
        c = ((msg[2] & 0x01) << 2) | ((msg[2] & 0x04) >> 1) | ((msg[2] & 0x10) >> 4)
        d = ((msg[3] & 0x01) << 2) | ((msg[3] & 0x04) >> 1) | ((msg[3] & 0x10) >> 4)
        identity = a*1000 + b*100 + c*10 + d
        ai = Aircraft.get(identity)
        if ai is None:
            ai = AircraftInfo(identity)
            Aircraft[identity] = ai
        ai.seen = time.time()
        if msgtype == 17:
            ai.addr = (msg[1] << 16) | (msg[2] << 8) | msg[3]
            metype = msg[4] >> 3
            mesub = msg[4] & 7
            if 1 <= metype <= 4:
                ai.aircraft_type = metype - 1
                ai.flight = (ais_charset[msg[5]>>2]
                           + ais_charset[((msg[5]&3)<<4)|(msg[6]>>4)]
                           + ais_charset[((msg[6]&15)<<2)|(msg[7]>>6)]
                           + ais_charset[msg[7]&63]
                           + ais_charset[msg[8]>>2]
                           + ais_charset[((msg[8]&3)<<4)|(msg[9]>>4)]
                           + ais_charset[((msg[9]&15)<<2)|(msg[10]>>6)]
                           + ais_charset[msg[10]&63])
            elif 9 <= metype <= 18:
                ai.altitude = decodeAC12(msg)
                ai.raw_latitude = ((msg[6] & 3) << 15) | (msg[7] << 7) | (msg[8] >> 1)
                ai.raw_longitude = ((msg[8] & 1) << 16) | (msg[9] << 8) | msg[10]
    now = time.time()
    global LastUpdate
    if now - LastUpdate > 1:
        update()
        LastUpdate = now

Server = None

class RelayServer(asyncore.dispatcher_with_send):
    def __init__(self):
        asyncore.dispatcher_with_send.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect(("adsb.flightaware.com", 15000))
    def handle_close(self):
        print("RelayServer close")
        global Server
        Server = RelayServer()

class Sbs3Client(asyncore.dispatcher):
    def __init__(self):
        asyncore.dispatcher.__init__(self)
        self.decoder = Decoder(packet)
    def handle_close(self):
        print("Sbs3Client close")
    def handle_read(self):
        buf = self.recv(4096)
        if buf:
            Server.send(buf)
            self.decoder.handle(buf)
    def writable(self):
        return False

def main():
    sbs3address = None
    sbs3port = None
    with open("sbsrelay.config") as f:
        for s in f:
            if not s or s.startswith("#"):
                continue
            a = s.split()
            if a[0] == "sbs3address":
                sbs3address = a[1]
            elif a[0] == "sbs3port":
                sbs3port = int(a[1])

    if not (sbs3address and sbs3port):
        print("sbsrelay: need sbs3address and sbs3port in sbsrelay.config", file=sys.stderr)
        sys.exit(1)

    global Server
    Server = RelayServer()
    sbs3 = Sbs3Client()
    sbs3.create_socket(socket.AF_INET, socket.SOCK_STREAM)
    sbs3.connect((sbs3address, sbs3port))
    asyncore.loop()

def test(fn):
    with open(fn) as f:
        for s in f:
            a = s.split()
            buf = [int(x, 16) for x in a if len(x) == 2]
            crc = int(a[-1], 16)
            packet(buf, crc)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test(sys.argv[1])
        sys.exit(0)
    main()
