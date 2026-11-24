"""Minimal local HTTP CONNECT proxy that routes api.telegram.org to a reachable IP.

Only listens on 127.0.0.1. Used by the Hermes Telegram gateway when local DNS
resolves api.telegram.org to blocked addresses.
"""
import select
import socket
import socketserver

TARGET_IP = "149.154.167.99"
LISTEN = ("127.0.0.1", 8899)


def pipe(a, b):
    sockets = [a, b]
    while sockets:
        readable, _, _ = select.select(sockets, [], [], 60)
        if not readable:
            break
        for sock in readable:
            try:
                data = sock.recv(65536)
            except OSError:
                return
            if not data:
                return
            other = b if sock is a else a
            try:
                other.sendall(data)
            except OSError:
                return


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            head = self.request.recv(8192)
        except OSError:
            return
        if not head:
            return
        first = head.split(b"\r\n", 1)[0].decode("latin-1", "replace")
        parts = first.split()
        if not parts:
            return
        if parts[0].upper() == "CONNECT":
            try:
                _, target = parts[1].split(":", 1)
                port = int(target)
            except (ValueError, IndexError):
                self.request.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                return
            try:
                upstream = socket.create_connection((TARGET_IP, port), 12)
            except OSError:
                self.request.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                return
            self.request.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
            pipe(self.request, upstream)
            return
        # Absolute-form request (defensive; Hermes uses CONNECT for HTTPS).
        try:
            upstream = socket.create_connection((TARGET_IP, 443), 12)
        except OSError:
            self.request.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            return
        try:
            upstream.sendall(head)
            pipe(self.request, upstream)
        finally:
            upstream.close()


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    print(f"Telegram relay listening on {LISTEN} -> {TARGET_IP}:443", flush=True)
    Server(LISTEN, Handler).serve_forever()
