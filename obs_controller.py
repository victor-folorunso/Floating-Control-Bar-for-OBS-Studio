import tkinter as tk
import tkinter.font as tkfont
import ctypes
import threading
import time

TRANS = '#010101'   # key color made transparent by Windows compositor
BG    = '#161616'
W, H  = 370, 42


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

        # 4 SEPARATE hotkeys
        self.hotkeys = {
            'Start Recording':  'ctrl+shift+alt+f9',
            'Stop Recording':   'ctrl+shift+alt+f10',
            'Pause Recording':  'ctrl+shift+alt+f11',
            'Resume Recording': 'ctrl+shift+alt+f12',
        }

        self.cv = tk.Canvas(self, width=W, height=H,
                            bg=TRANS, highlightthickness=0)
        self.cv.place(x=0, y=0)
        self._draw_pill()
        self._build()

        self.cv.tag_bind('pill', '<ButtonPress-1>', self._ds)
        self.cv.tag_bind('pill', '<B1-Motion>',     self._dm)

        self.after(300, self._exclude)

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

        self.dot = tk.Label(self, text='●', font=mon, fg='#303030', bg=BG)
        self.dot.place(x=14, y=cy, anchor='w')
        self._bd(self.dot)

        self.tvar = tk.StringVar(value='00:00:00')
        self.tlbl = tk.Label(self, textvariable=self.tvar, font=mon, fg='#383838', bg=BG)
        self.tlbl.place(x=30, y=cy, anchor='w')
        self._bd(self.tlbl)

        self.cv.create_line(110, 8, 110, H-8, fill='#252525', tags='pill')

        self.rbtn = tk.Button(self, text='START', font=mon,
                              fg='#777', bg=BG, activebackground=BG,
                              activeforeground='#fff', bd=0, padx=6,
                              pady=0, cursor='hand2', relief='flat',
                              command=self._toggle_rec)
        self.rbtn.place(x=124, y=cy, anchor='w')

        self.pbtn = tk.Button(self, text='PAUSE', font=mon,
                              fg='#2e2e2e', bg=BG, activebackground=BG,
                              activeforeground='#aaa', bd=0, padx=6,
                              pady=0, cursor='hand2', state='disabled',
                              relief='flat', command=self._toggle_pause)
        self.pbtn.place(x=224, y=cy, anchor='w')

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

    def _hk(self, action):
        try:
            import keyboard
            keyboard.send(self.hotkeys[action])
        except Exception:
            pass

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
            self._hk('Start Recording')
        else:
            self.recording = False
            self.paused    = False
            self._trunning = False
            self.rbtn.config(text='START', fg='#777')
            self.pbtn.config(state='disabled', text='PAUSE', fg='#2e2e2e')
            self.dot.config(fg='#303030')
            self.tlbl.config(fg='#383838')
            self._hk('Stop Recording')

    def _toggle_pause(self):
        if not self.recording:
            return
        if not self.paused:
            self.paused = True
            self.pbtn.config(text='RESUME', fg='#ffa040')
            self.dot.config(fg='#ffa040')
            self.tlbl.config(fg='#ffa040')
            self._hk('Pause Recording')
        else:
            self.paused = False
            self.pbtn.config(text='PAUSE', fg='#888')
            self.dot.config(fg='#ff4444')
            self.tlbl.config(fg='#ff4444')
            self._hk('Resume Recording')

    def _settings(self):
        win = tk.Toplevel(self)
        win.title('Hotkeys')
        win.configure(bg='#0f0f0f')
        win.geometry('370x240')
        win.attributes('-topmost', True)
        win.resizable(False, False)

        mon = tkfont.Font(family='Consolas', size=8, weight='bold')
        sml = tkfont.Font(family='Consolas', size=7)

        tk.Label(win, text='Replicate these exactly in  OBS → Settings → Hotkeys',
                 fg='#444', bg='#0f0f0f', font=sml).pack(pady=(14, 10))

        frm = tk.Frame(win, bg='#0f0f0f')
        frm.pack(fill='x', padx=22)

        self._svars = {}
        for action, combo in self.hotkeys.items():
            row = tk.Frame(frm, bg='#0f0f0f')
            row.pack(fill='x', pady=5)
            tk.Label(row, text=action, fg='#555', bg='#0f0f0f',
                     font=sml, width=18, anchor='w').pack(side='left')
            var = tk.StringVar(value=combo)
            self._svars[action] = var
            tk.Entry(row, textvariable=var, font=sml,
                     bg='#1c1c1c', fg='#e0e0e0', bd=0,
                     insertbackground='#e0e0e0', width=24
                     ).pack(side='left', padx=8)

        def save():
            for action, var in self._svars.items():
                self.hotkeys[action] = var.get()
            win.destroy()

        tk.Button(win, text='SAVE', font=mon, fg='#ccc', bg='#1e1e1e',
                  activebackground='#252525', bd=0, padx=12, pady=5,
                  cursor='hand2', command=save).pack(pady=14)

    def _ds(self, e):
        self._ox = e.x_root - self.winfo_x()
        self._oy = e.y_root - self.winfo_y()

    def _dm(self, e):
        self.geometry(f'+{e.x_root - self._ox}+{e.y_root - self._oy}')


if __name__ == '__main__':
    OBSController().mainloop()
