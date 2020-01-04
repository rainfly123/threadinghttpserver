#!/usr/bin/env python
import os, datetime, sys, urlparse
import SimpleHTTPServer
import wave
import daemon
import urllib
import requests
import traceback
import SocketServer

PORT = 2020
HOST = '0.0.0.0'

class Handler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    def _set_headers(self, length):
        self.send_response(200)
        if length > 0:
            self.send_header('Content-length', str(length))
        self.end_headers()

    def _get_chunk_size(self):
        data = self.rfile.read(2)
        while data[-2:] != b"\r\n":
            data += self.rfile.read(1)
        return int(data[:-2], 16)

    def _get_chunk_data(self, chunk_size):
        data = self.rfile.read(chunk_size)
        self.rfile.read(2)
        return data

    def _write_wav(self, data, rates, bits, ch):
        t = datetime.datetime.utcnow()
        time = t.strftime('%Y%m%dT%H%M%SZ')
        filename = str.format('{}_{}_{}_{}.wav', time, rates, bits, ch)

        wavfile = wave.open(os.path.join("/dev/shm/waves",filename), 'wb')
        wavfile.setparams((ch, bits/8, rates, 0, 'NONE', 'NONE'))
        wavfile.writeframes(bytearray(data))
        wavfile.close()
        return filename

    def do_POST(self):
        urlparts = urlparse.urlparse(self.path)
        request_file_path = urlparts.path.strip('/')
        print urlparts.query, urlparts.path
        total_bytes = 0
        sample_rates = 0
        bits = 0
        channel = 0
        #ip = self.headers.get('X-Forwarded-For', '')
        ip = self.client_address[0]
        print ip
        if (request_file_path == 'api/sr'
            and self.headers.get('Transfer-Encoding', '').lower() == 'chunked'):
            data = []
            sample_rates = self.headers.get('x-audio-sample-rates', '').lower()
            bits = self.headers.get('x-audio-bits', '').lower()
            channel = self.headers.get('x-audio-channel', '').lower()
            sample_rates = self.headers.get('x-audio-sample-rates', '').lower()

            print("Audio information, sample rates: {}, bits: {}, channel(s): {}".format(sample_rates, bits, channel))
            # https://stackoverflow.com/questions/24500752/how-can-i-read-exactly-one-response-chunk-with-pythons-http-client
            while True:
                chunk_size = self._get_chunk_size()
                total_bytes += chunk_size
                print("Total bytes received: {}".format(total_bytes))
                sys.stdout.write("\033[F")
                if (chunk_size == 0):
                    break
                else:
                    chunk_data = self._get_chunk_data(chunk_size)
                    data += chunk_data

            filename = self._write_wav(data, int(sample_rates), int(bits), int(channel))
            body = 'File {} was written, size {}'.format(filename, total_bytes)
            self._set_headers(len(body))
            self.wfile.write(body)
            self.wfile.close()
            sendout(ip, urlparts.query, filename)
        else:
            return SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)

def sendout(ip, query, filename):
    headers={
        'X-Forwarded-For':ip
    }
    url = "http://127.0.0.1:2019/nsr?{}&file={}".format(query, filename)
    res = requests.get(url, headers=headers)
    res.close()

class ThreadingTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == '__main__':
    #sendout("devid=adf", "a.wav")
    #daemon.daemonize("/tmp/chunk.pid")
    if not os.path.exists('/dev/shm/waves'):
        os.mkdir("/dev/shm/waves")
    try:
        httpd = ThreadingTCPServer((HOST, PORT), Handler)
        print("Serving HTTP on {} port {}".format(HOST, PORT));
        httpd.serve_forever()
    except Exception:
        f = open("/tmp/server", "a")
        traceback.print_exc(file=f)
        f.close()

