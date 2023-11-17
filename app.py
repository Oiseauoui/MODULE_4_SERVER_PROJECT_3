import errno
import json
import logging
import mimetypes
import pathlib
import socket
import urllib
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from urllib.parse import unquote_plus
from flask import Flask
from jinja2 import Environment, FileSystemLoader
import time

app = Flask(__name__, template_folder='templates')


BASE_DIR = pathlib.Path()


env = Environment(loader=FileSystemLoader('templates'))
json_file_path = None

SERVER_IP = '127.0.0.1'
SERVER_PORT = 5000
BUFFER = 1024
LOG_FILE = 'server.log'
DATA_FILE = 'storage/data.json'

logging.basicConfig(filename=LOG_FILE, level=logging.INFO)


def send_data_to_socket(body):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.sendto(body, (SERVER_IP, SERVER_PORT))
    client_socket.close()


class HTTPHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        # self.send_html('message.html')
        body = self.rfile.read(int(self.headers['Content-Length']))
        send_data_to_socket(body)

        self.send_response(302)
        self.send_header('Location', '/')
        self.end_headers()

    def do_GET(self):
        route = urllib.parse.urlparse(self.path)
        match route.path:
            case "/":
                self.send_html('index.html')
            case "/message":
                self.send_html('message.html')
            case "/blog":
                self.render_template('blog.html')
            case _:
                # print(BASE_DIR / route.path[1:])
                file = BASE_DIR / route.path[1:]
                if file.exists():
                    self.send_static(file)
                else:
                    self.send_html('error.html', 404)

                # self.send_html('error.html', 404)

    def send_html(self, filename, status_code=200):
        self.send_response(status_code)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        with open(filename, 'rb') as f:
            self.wfile.write(f.read())

    def render_template(self, filename, status_code=200):
        self.send_response(status_code)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        with open('blog.json', 'r', encoding='utf-8') as file_descriptor:
            r = json.load(file_descriptor)

        template = env.get_template(filename)
        print("Template loaded:", template)

        try:
            html = template.render(blogs=r)
            self.wfile.write(html.encode())
            print("Rendering successful")
        except Exception as e:
            print(f"Error rendering template: {e}")

    def send_static(self, filename):
        self.send_response(200)
        mime_type, *rest = mimetypes.guess_type(filename)
        if mime_type:
            self.send_header('Content-Type', mime_type)
        else:
            self.send_header('Content-Type', 'text/plain')

        self.end_headers()
        with open(filename, 'rb') as f:
            self.wfile.write(f.read())


def run(server=HTTPServer, handler=HTTPHandler):
    address = ('0.0.0.0', 3000)
    http_server = server(address, handler)
    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        http_server.server_close()


def save_data(data):
    global json_file_path
    body = unquote_plus(data.decode())
    try:
        payload = {key: value for key, value in [el.split('=') for el in body.split('&')]}
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        json_file_path = BASE_DIR.joinpath(DATA_FILE)

        try:
            with open(json_file_path, 'r', encoding='utf-8') as existing_file:
                existing_data = json.load(existing_file)
        except (FileNotFoundError, json.JSONDecodeError):
            existing_data = {}

        entry = {timestamp: payload}
        existing_data.update(entry)

        with open(json_file_path, 'w', encoding='utf-8') as file_desc:
            json.dump(existing_data, file_desc, ensure_ascii=False, indent=2)

        print(entry)
    except ValueError as err:
        logging.error(f"Failed to parse data {body} with error {err}")
    except OSError as err:
        logging.error(f"Failed to write data to {json_file_path} with error {err}")



def run_socket_server(ip, port):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server = (ip, port)

    try:
        server_socket.bind(server)
        while True:
            data, address = server_socket.recvfrom(BUFFER)
            save_data(data)
    except KeyboardInterrupt:
        logging.info('Socket server stopped')
    except OSError as e:
        if e.errno == errno.WSAEADDRINUSE:
            print(f"Port {port} is already in use. Waiting for 1 second before retrying.")
            time.sleep(1)
        else:
            raise
    finally:
        server_socket.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="%(threadName)s %(message)s")
    STORAGE_DIR = pathlib.Path().joinpath('storage')
    FILE_STORAGE = STORAGE_DIR / 'data.json'
    if not FILE_STORAGE.exists():
        with open(FILE_STORAGE, 'w', encoding='utf-8') as fd:
            json.dump({}, fd, ensure_ascii=False)

    thread_run = Thread(target=run)
    thread_run.start()

    thread_socket_server = Thread(target=run_socket_server, args=(SERVER_IP, SERVER_PORT))
    thread_socket_server.start()
