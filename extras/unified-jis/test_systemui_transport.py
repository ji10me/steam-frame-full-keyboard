import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import base64
import hashlib
import unittest
from unittest.mock import patch

import frame_jis_cdp as transport

spec=importlib.util.spec_from_file_location('tested_runtime_transport',Path(__file__).resolve().parents[2]/'bridge/native_bridge.py')
runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)


class Response:
    def __init__(self,value):self.value=value
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,_):return json.dumps(self.value).encode()


class WebSocket:
    def __init__(self,valid=True):self.valid=valid;self.closed=False;self.request=b''
    def sendall(self,data):self.request+=data
    def recv(self,_):
        key=self.request.split(b'Sec-WebSocket-Key: ',1)[1].split(b'\r\n',1)[0]
        accept=base64.b64encode(hashlib.sha1(key+b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest())
        return b'HTTP/1.1 101 Switching Protocols\r\nSec-WebSocket-Accept: '+(accept if self.valid else b'invalid')+b'\r\n\r\n'
    def close(self):self.closed=True


class Transport(unittest.TestCase):
    def connect(self,targets,ws=None):
        ws=ws or WebSocket()
        opener=SimpleNamespace(open=lambda *args,**kwargs:Response(targets))
        with patch.object(transport,'runtime_module',return_value=runtime), \
             patch.object(transport,'require_loopback'), \
             patch.object(transport,'build_opener',return_value=opener), \
             patch.object(transport.socket,'create_connection',return_value=ws) as connect:
            try:return transport.systemui_client(),ws,connect
            except BaseException:
                self.assertTrue(ws.closed or not connect.called)
                raise

    def test_exact_systemui_context_and_websocket_validation(self):
        client,ws,connect=self.connect([{'title':'systemui','webSocketDebuggerUrl':'ws://127.0.0.1:9223/devtools/page/test'}])
        connect.assert_called_once_with(('127.0.0.1',9223),timeout=.3)
        self.assertIn(b'GET /devtools/page/test HTTP/1.1',ws.request)
        client.close();self.assertTrue(ws.closed)

    def test_unknown_duplicate_and_nonlocal_targets_rejected(self):
        for targets in ([{'title':'unrelated'}],[{'title':'systemui'}]*2,
            *[[{'title':'systemui','webSocketDebuggerUrl':url}] for url in
              ('ws://example.com:9223/x','ws://127.0.0.1:8080/x','wss://127.0.0.1:9223/x')]):
            with self.subTest(targets=targets),self.assertRaises(ValueError):self.connect(targets)

    def test_bad_upgrade_closes_owned_socket(self):
        with self.assertRaises(ValueError):self.connect([{'title':'systemui','webSocketDebuggerUrl':'ws://localhost:9223/x'}],WebSocket(False))

    def test_loopback_binding_required_and_ipv6_optional(self):
        for address,allowed in [('0100007F',True),('00000000',False),('0101A8C0',False)]:
            def read(path):
                if path.name=='tcp6':raise FileNotFoundError()
                return 'header\n0: '+address+':2407 00000000:0000 0A 0 0\n'
            with self.subTest(address=address),patch.object(Path,'read_text',read):
                if allowed:transport.require_loopback(9223)
                else:
                    with self.assertRaises(ValueError):transport.require_loopback(9223)
        with patch.object(Path,'read_text',return_value='header\n'):
            with self.assertRaises(ValueError):transport.require_loopback(9223)


if __name__=='__main__':unittest.main()
