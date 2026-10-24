"""Reuse the installed app's CDP framing for SteamVR's loopback systemui.

Only the connection setup differs from bridge/native_bridge.py (0.8.2, MIT).
No new listener is created here; browser/field contents are never requested.
"""
import base64
import hashlib
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import socket
import sys
import time
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener


def runtime_module():
    path=Path.home()/'.local/share/framekeyboard/unified-jis/runtime/share/framekeyboard/bridge/native_bridge.py'
    spec=importlib.util.spec_from_file_location('frame_jis_runtime_transport',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def require_loopback(port):
    found=False
    for table in ('tcp','tcp6'):
        try:lines=Path('/proc/net',table).read_text().splitlines()[1:]
        except FileNotFoundError:
            if table=='tcp6':continue
            raise ValueError('systemui-debugger-unavailable') from None
        for line in lines:
            fields=line.split()
            if fields[3]!='0A':continue
            host,number=fields[1].split(':')
            if int(number,16)!=port:continue
            found=True;raw=bytes.fromhex(host)
            if sys.byteorder=='little':raw=b''.join(raw[i:i+4][::-1] for i in range(0,len(raw),4))
            address=ipaddress.ip_address(raw);address=getattr(address,'ipv4_mapped',None) or address
            if not address.is_loopback:raise ValueError('systemui-debugger-not-loopback')
    if not found:raise ValueError('systemui-debugger-unavailable')


def systemui_client():
    module=runtime_module()
    class SystemUiCDP(module.CDP):
        def __init__(self):
            self.socket=None;self.pending=b'';self.sequence=0
            try:
                require_loopback(9223)
                self.network_checked=time.monotonic()
                opener=build_opener(ProxyHandler({}),module.NoDebuggerRedirects())
                with opener.open('http://127.0.0.1:9223/json/list',timeout=.4) as response:
                    data=response.read(1024*1024+1)
                if len(data)>1024*1024:raise ValueError('systemui-target-list-too-large')
                targets=json.loads(data)
                matches=[t for t in targets if t.get('title')=='systemui']
                if len(matches)!=1:raise ValueError('systemui-target-unavailable')
                url=urlsplit(matches[0]['webSocketDebuggerUrl'])
                if url.scheme!='ws' or url.hostname not in ('localhost','127.0.0.1') or url.port!=9223:
                    raise ValueError('systemui-target-not-loopback')
                self.socket=socket.create_connection(('127.0.0.1',9223),timeout=.3)
                key=base64.b64encode(os.urandom(16)).decode()
                path=url.path+('?' + url.query if url.query else '')
                self.socket.sendall((f'GET {path} HTTP/1.1\r\nHost: 127.0.0.1:9223\r\n'
                    'Upgrade: websocket\r\nConnection: Upgrade\r\n'
                    f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
                while b'\r\n\r\n' not in self.pending:
                    chunk=self.socket.recv(4096)
                    if not chunk:raise EOFError()
                    self.pending+=chunk
                    if len(self.pending)>16384:raise ValueError('systemui-invalid-upgrade')
                header,self.pending=self.pending.split(b'\r\n\r\n',1)
                accept=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest())
                if not header.startswith(b'HTTP/1.1 101 ') or accept.lower() not in header.lower():
                    raise ValueError('systemui-upgrade-refused')
            except BaseException:
                self.close();raise
        def evaluate(self,expression,timeout=.4):
            require_loopback(9223)
            return super().evaluate(expression,timeout)
    return SystemUiCDP()
