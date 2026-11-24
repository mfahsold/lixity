"""Open a static loopback document in the distribution's WebKitGTK library."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gtk, WebKit2


class ControlDocument(BaseHTTPRequestHandler):
    def do_GET(self):
        content = b'''<!doctype html><html lang="en"><head>
          <meta charset="utf-8"><title>Stock WebKitGTK test page</title></head>
          <body><h1>Stock WebKitGTK rendered this document</h1>
          <button type="button">Visible WebKitGTK control</button></body></html>'''
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


server = ThreadingHTTPServer(("127.0.0.1", 0), ControlDocument)
Thread(target=server.serve_forever, daemon=True).start()
window = Gtk.Window(title="Stock WebKitGTK control window")
window.set_default_size(1000, 720)
window.connect("destroy", Gtk.main_quit)
view = WebKit2.WebView()
window.add(view)
window.show_all()
view.load_uri(f"http://127.0.0.1:{server.server_port}/")
Gtk.main()
