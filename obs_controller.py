import tkinter as tk
import tkinter.font as tkfont
import ctypes
import threading
import time
import json
import hashlib
import base64
import struct
import socket
import ssl

# ── Minimal WebSocket client (no external deps) ───────────────────────────────

def _ws_handshake(host, port, password):
    """Open a raw WebSocket connection to OBS and return the socket."""
    s = socket.create_connection((host, port), timeout=5)
    key = base64.b64encode(b'obscontroller1234567890==').decode()
    s.sendall((
        f"GET / HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n\r\n"
    ).encode())
    resp = b''
    while b'\r\n\r\n' not in resp:
        resp += s.recv(1024)
    return s

def _ws_recv(s):
    """Read one WebSocket frame and return the payload as a dict."""
    header = b''
    while len(header) < 2:
        header += s.recv(2 - len(header))
    b0, b1 = header
    masked  = (b1 & 0x80) != 0
    length  = b1 & 0x7F
    if length == 126:
        raw = b''
        while len(raw) < 2: raw += s.recv(2 - len(raw))
        length = struct.unpack('>H', raw)[0]
    elif length == 127:
        raw = b''
        while len(raw) < 8: raw += s.recv(8 - len(raw))
        length = struct.unpack('>Q', raw)[0]
    payload = b''
    while len(payload) < length:
        payload += s.recv(length - len(payload))
    return json.loads(payload.decode('utf-8'))

def _ws_send(s, data):
    """Send a dict as a masked WebSocket text frame."""
    payload = json.dumps(data).encode('utf-8')
    length  = len(payload)
    mask    = b'\x00\x00\x00\x00'           # zero mask = no-op XOR
    if length < 126:
        header = bytes([0x81, 0x80 | length])
    elif length < 65536:
        header = bytes([0x81, 0xFE]) + struct.pack('>H', length)
    else:
        header = bytes([0x81, 0xFF]) + struct.pack('>Q', length)
    s.sendall(header + mask + payload)


class OBSWebSocket:
    """
    Tiny OBS WebSocket v5 client.
    Password can be empty string '' if auth is disabled in OBS.
    """
    def __init__(self, host='localhost', port=4455, password=''):
        self.host     = host
        self.port     = port
        self.password = password
        self._sock    = None
        self._lock    = threading.Lock()
        self._msg_id  = 0

    def connect(self):
        self._sock = _ws_handshake(self.host, self.port, self.password)
        # receive Hello
        hello = _ws_recv(self._sock)                   # op 0
        auth_required = hello.get('d', {}).get('authentication')
        # send Identify (op 1)
        identify = {'op': 1, 'd': {'rpcVersion': 1}}
        if auth_required and self.password:
            challenge = auth_required['challenge']
            salt      = auth_required['salt']
            secret    = base64.b64encode(
                hashlib.sha256((self.password + salt).encode()).digest()
            ).decode()
            auth_str  = base64.b64encode(
                hashlib.sha256((secret + challenge).encode()).digest()
            ).decode()
            identify['d']['authentication'] = auth_str
        _ws_send(self._sock, identify)
        _ws_recv(self._sock)                           # op 2 Identified

    def call(self, request_type, data=None):
        with self._lock:
            self._msg_id += 1
            msg = {
                'op': 6,
                'd': {
                    'requestType': request_type,
                    'requestId':   str(self._msg_id),
                    'requestData': data or {},
                }
            }
            _ws_send(self._sock, msg)
            resp = _ws_recv(self._sock)
            return resp

    def close(self):
        if self._sock:
            try: self._sock.close()
            except: pass
            self._sock = None

    @property
    def connected(self):
        return self._sock is not None


# ── UI constants ──────────────────────────────────────────────────────────────
TRANS = '#010101'
BG    = '#161616'
W, H  = 400, 42


class OBSController(tk.Tk):
    def __init__(self):
        super().__init__()
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.attributes('-transparentcolor', TRANS)
        self.configure(bg=TRANS)
        self.geometry(f'{W}x{H}+120+80')
        self.resizable(False, False)

        self.recording = False
        self.paused    = False
        self.elapsed   = 0
        self._trunning = False

        self.ws   = OBSWebSocket(host='localhost', port=4455, password='')
        self._try_connect()

        self.cv = tk.Canvas(self, width=W, height=H,
                            bg=TRANS, highlightthickness=0)
        self.cv.place(x=0, y=0)
        self._draw_pill()
        self._build()

        self.cv.tag_bind('pill', '<ButtonPress-1>', self._ds)
        self.cv.tag_bind('pill', '<B1-Motion>',     self._dm)

        self.after(300, self._exclude)

    # ── WebSocket ─────────────────────────────────────────────────────────────

    def _try_connect(self):
        def _conn():
            try:
                self.ws.connect()
                self.after(0, lambda: self._set_status('connected'))
            except Exception as e:
                self.after(0, lambda: self._set_status(f'no obs'))
        threading.Thread(target=_conn, daemon=True).start()

    def _set_status(self, s):
        color = '#33aa55' if s == 'connected' else '#aa3333'
        if hasattr(self, 'conn_dot'):
            self.conn_dot.config(fg=color)

    def _obs(self, request_type, data=None):
        if not self.ws.connected:
            self._try_connect()
            return
        def _call():
            try:
                self.ws.call(request_type, data)
            except Exception:
                self.ws.close()
                self.after(0, lambda: self._set_status('no obs'))
        threading.Thread(target=_call, daemon=True).start()

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw_pill(self):
        kw = dict(fill=BG, outline='', tags='pill')
        self.cv.create_arc(0,    0, H,   H, start=90,  extent=180, style='chord', **kw)
        self.cv.create_arc(W-H, 0, W,   H, start=270, extent=180, style='chord', **kw)
        self.cv.create_rectangle(H//2, 0, W-H//2, H, fill=BG, outline='', tags='pill')
        b = '#2c2c2c'
        self.cv.create_arc(0,    0, H,   H, start=90,  extent=180, style='arc', outline=b, width=1, tags='pill')
        self.cv.create_arc(W-H, 0, W,   H, start=270, extent=180, style='arc', outline=b, width=1, tags='pill')
        self.cv.create_line(H//2, 0,   W-H//2, 0,   fill=b, tags='pill')
        self.cv.create_line(H//2, H-1, W-H//2, H-1, fill=b, tags='pill')

    def _build(self):
        cy  = H // 2
        mon = tkfont.Font(family='Consolas', size=8, weight='bold')
        sml = tkfont.Font(family='Consolas', size=7)

        # connection indicator dot (left edge)
        self.conn_dot = tk.Label(self, text='●', font=sml, fg='#aa3333', bg=BG)
        self.conn_dot.place(x=10, y=cy, anchor='w')
        self._bd(self.conn_dot)

        # recording dot + timer
        self.dot = tk.Label(self, text='●', font=mon, fg='#303030', bg=BG)
        self.dot.place(x=24, y=cy, anchor='w')
        self._bd(self.dot)

        self.tvar = tk.StringVar(value='00:00:00')
        self.tlbl = tk.Label(self, textvariable=self.tvar, font=mon, fg='#383838', bg=BG)
        self.tlbl.place(x=40, y=cy, anchor='w')
        self._bd(self.tlbl)

        self.cv.create_line(118, 8, 118, H-8, fill='#252525', tags='pill')

        self.rbtn = tk.Button(self, text='START', font=mon,
                              fg='#777', bg=BG, activebackground=BG,
                              activeforeground='#fff', bd=0, padx=6,
                              pady=0, cursor='hand2', relief='flat',
                              command=self._toggle_rec)
        self.rbtn.place(x=130, y=cy, anchor='w')

        self.pbtn = tk.Button(self, text='PAUSE', font=mon,
                              fg='#2e2e2e', bg=BG, activebackground=BG,
                              activeforeground='#aaa', bd=0, padx=6,
                              pady=0, cursor='hand2', state='disabled',
                              relief='flat', command=self._toggle_pause)
        self.pbtn.place(x=232, y=cy, anchor='w')

        self.cv.create_line(W-50, 8, W-50, H-8, fill='#252525', tags='pill')

        gear = tk.Label(self, text='⚙', font=sml, fg='#3a3a3a', bg=BG, cursor='hand2')
        gear.place(x=W-36, y=cy, anchor='center')
        gear.bind('<Button-1>', lambda e: self._settings())

        close = tk.Label(self, text='✕', font=sml, fg='#272727', bg=BG, cursor='hand2')
        close.place(x=W-18, y=cy, anchor='center')
        close.bind('<Button-1>', lambda e: self.destroy())

    def _bd(self, w):
        w.bind('<ButtonPress-1>', self._ds)
        w.bind('<B1-Motion>',     self._dm)

    def _exclude(self):
        self.update_idletasks()
        self.update()
        hwnd = self.winfo_id()
        ret  = ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
        if ret == 0:
            hwnd2 = ctypes.windll.user32.GetParent(hwnd)
            if hwnd2:
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd2, 0x00000011)

    # ── Timer ─────────────────────────────────────────────────────────────────

    def _tick(self):
        while self._trunning:
            time.sleep(1)
            if self._trunning and not self.paused:
                self.elapsed += 1
                h = self.elapsed // 3600
                m = (self.elapsed % 3600) // 60
                s = self.elapsed % 60
                try:
                    self.tvar.set(f'{h:02d}:{m:02d}:{s:02d}')
                except Exception:
                    break

    # ── Controls ──────────────────────────────────────────────────────────────

    def _toggle_rec(self):
        if not self.recording:
            self.recording = True
            self.paused    = False
            self.elapsed   = 0
            self._trunning = True
            self.tvar.set('00:00:00')
            threading.Thread(target=self._tick, daemon=True).start()
            self.rbtn.config(text='STOP',  fg='#ff4444')
            self.pbtn.config(state='normal', text='PAUSE', fg='#888')
            self.dot.config(fg='#ff4444')
            self.tlbl.config(fg='#ff4444')
            self._obs('StartRecord')
        else:
            self.recording = False
            self.paused    = False
            self._trunning = False
            self.rbtn.config(text='START', fg='#777')
            self.pbtn.config(state='disabled', text='PAUSE', fg='#2e2e2e')
            self.dot.config(fg='#303030')
            self.tlbl.config(fg='#383838')
            self._obs('StopRecord')

    def _toggle_pause(self):
        if not self.recording:
            return
        if not self.paused:
            self.paused = True
            self.pbtn.config(text='RESUME', fg='#ffa040')
            self.dot.config(fg='#ffa040')
            self.tlbl.config(fg='#ffa040')
            self._obs('PauseRecord')
        else:
            self.paused = False
            self.pbtn.config(text='PAUSE', fg='#888')
            self.dot.config(fg='#ff4444')
            self.tlbl.config(fg='#ff4444')
            self._obs('ResumeRecord')

    # ── Settings ──────────────────────────────────────────────────────────────

    def _settings(self):
        win = tk.Toplevel(self)
        win.title('OBS WebSocket')
        win.configure(bg='#0f0f0f')
        win.geometry('320x180')
        win.attributes('-topmost', True)
        win.resizable(False, False)

        mon = tkfont.Font(family='Consolas', size=8, weight='bold')
        sml = tkfont.Font(family='Consolas', size=7)

        tk.Label(win, text='OBS → Tools → WebSocket Server Settings',
                 fg='#444', bg='#0f0f0f', font=sml).pack(pady=(14, 10))

        frm = tk.Frame(win, bg='#0f0f0f')
        frm.pack(fill='x', padx=22)

        fields = [('Host', self.ws.host), ('Port', str(self.ws.port)), ('Password', self.ws.password)]
        svars  = []
        for label, val in fields:
            row = tk.Frame(frm, bg='#0f0f0f')
            row.pack(fill='x', pady=5)
            tk.Label(row, text=label, fg='#555', bg='#0f0f0f',
                     font=sml, width=10, anchor='w').pack(side='left')
            var = tk.StringVar(value=val)
            svars.append(var)
            tk.Entry(row, textvariable=var, font=sml,
                     bg='#1c1c1c', fg='#e0e0e0', bd=0,
                     insertbackground='#e0e0e0', width=20,
                     show='*' if label == 'Password' else ''
                     ).pack(side='left', padx=8)

        def save():
            self.ws.close()
            self.ws.host     = svars[0].get()
            self.ws.port     = int(svars[1].get() or 4455)
            self.ws.password = svars[2].get()
            self._try_connect()
            win.destroy()

        tk.Button(win, text='SAVE & RECONNECT', font=mon, fg='#ccc', bg='#1e1e1e',
                  activebackground='#252525', bd=0, padx=12, pady=5,
                  cursor='hand2', command=save).pack(pady=14)

    # ── Drag ──────────────────────────────────────────────────────────────────

    def _ds(self, e):
        self._ox = e.x_root - self.winfo_x()
        self._oy = e.y_root - self.winfo_y()

    def _dm(self, e):
        self.geometry(f'+{e.x_root - self._ox}+{e.y_root - self._oy}')


if __name__ == '__main__':
    OBSController().mainloop()
