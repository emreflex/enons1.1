"""Windows masaüstü onay paneli + yerel Flask sunucusu."""
import argparse
from pathlib import Path
import queue
import secrets
import socket
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from werkzeug.serving import make_server
from plaka_anons.audio import Player, SoundBank, list_music_sessions
from plaka_anons.plates import REASONS
from plaka_anons.store import Store
from plaka_anons.web import create_app

ROOT = Path(__file__).resolve().parent
STATUS = {'pending': 'Onay bekliyor', 'playing': 'Okunuyor', 'done': 'Tamamlandı',
          'error': 'Hata / tekrar onayla', 'rejected': 'Reddedildi'}


def lan_addresses():
    # İnternet bağlantısı gerektirmeyen aday adresler; VPN/sanal adaptörler de olabilir.
    try:
        return sorted({x[4][0] for x in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
                       if not x[4][0].startswith('127.')})
    except OSError:
        return []


class Panel:
    def __init__(self, root, bank, store, port):
        self.root, self.store = root, store
        self.events, self.jobs = queue.Queue(), queue.Queue(maxsize=1)
        self.stop = threading.Event()
        self.busy = False
        self.closing = False
        password = secrets.token_hex(8)
        self.server = make_server('0.0.0.0', port,
                                 create_app(store, password, lambda: self.events.put(('new', None))))
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker = threading.Thread(target=self.work, args=(bank,), daemon=False)
        root.title('Plaka Anons • Kontrol Paneli')
        root.geometry('1080x650')
        ttk.Label(root, text='PLAKA ANONS', font=('Segoe UI', 20, 'bold')).pack(pady=12)
        addresses = ', '.join(f'{ip}:{port}' for ip in lan_addresses()) or 'ipconfig ile Wi-Fi IPv4 adresini bulun'
        ttk.Label(root, text=f'Telefon bağlantısı: {addresses}  |  Eşleştirme parolası: {password}').pack(pady=6)
        ttk.Label(root, text='Windows varsayılan ses çıkışını amfiye ayarlayın. Telefon ve bilgisayar aynı ağda olmalı.').pack()
        row = ttk.Frame(root)
        row.pack(fill='x', padx=15, pady=12)
        ttk.Label(row, text='Kısılacak müzik uygulaması:').pack(side='left')
        self.music = ttk.Combobox(row, state='readonly', width=45)
        self.music.pack(side='left', padx=10)
        ttk.Button(row, text='Uygulamaları yenile', command=self.refresh_music).pack(side='left')
        frame = ttk.Frame(root)
        frame.pack(fill='both', expand=True, padx=15)
        self.table = ttk.Treeview(frame, columns=('time', 'plate', 'reason', 'status', 'error'), show='headings', selectmode='browse')
        for key, title, width in [('time', 'Zaman', 160), ('plate', 'Plaka', 140), ('reason', 'Sebep', 120), ('status', 'Durum', 145), ('error', 'Açıklama', 320)]:
            self.table.heading(key, text=title)
            self.table.column(key, width=width)
        self.table.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(frame, orient='vertical', command=self.table.yview)
        scroll.pack(side='right', fill='y')
        self.table.configure(yscrollcommand=scroll.set)
        actions = ttk.Frame(root)
        actions.pack(pady=12)
        self.approve_button = ttk.Button(actions, text='Seçileni onayla ve anons et', command=self.approve)
        self.approve_button.pack(side='left', padx=8)
        ttk.Button(actions, text='Seçileni reddet', command=self.reject).pack(side='left', padx=8)
        ttk.Button(actions, text='Anonsu durdur', command=self.stop.set).pack(side='left', padx=8)
        self.status = tk.StringVar(value='Hazır. Telefon istekleri onayınız olmadan okunmaz.')
        ttk.Label(root, textvariable=self.status).pack(pady=8)
        self.refresh_music()
        self.refresh_table()
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.server_thread.start()
        self.worker.start()
        root.after(150, self.poll)

    def refresh_music(self):
        try:
            import comtypes
            comtypes.CoInitialize()
            try:
                sessions = list_music_sessions()
            finally:
                comtypes.CoUninitialize()
            self.music_options = {'Ses kısma yok': None}
            self.music_options.update({f'{name} (PID {pid})': pid for pid, name in sessions.items()})
            previous = self.music.get()
            self.music['values'] = list(self.music_options)
            self.music.set(previous if previous in self.music_options else 'Ses kısma yok')
        except Exception as exc:
            self.music_options = {'Ses kısma yok': None}
            self.music['values'] = list(self.music_options)
            self.music.current(0)
            messagebox.showwarning('Ses mikseri', str(exc))

    def refresh_table(self):
        selected = self.table.selection()
        self.table.delete(*self.table.get_children())
        for row in self.store.rows():
            self.table.insert('', 'end', iid=str(row['id']), values=(row['created'], row['plate'],
                REASONS[row['reason']][0], STATUS[row['status']], row['error']))
        if selected and self.table.exists(selected[0]):
            self.table.selection_set(selected)

    def approve(self):
        selected = self.table.selection()
        if self.closing or self.busy or not selected:
            return
        row = self.store.claim(int(selected[0]))
        if row:
            self.stop.clear()
            self.busy = True
            self.approve_button.state(['disabled'])
            self.jobs.put((row, self.music_options.get(self.music.get())))
            self.refresh_table()

    def reject(self):
        selected = self.table.selection()
        if selected:
            self.store.reject(int(selected[0]))
            self.refresh_table()

    def work(self, bank):
        player = Player(bank, self.stop)
        while True:
            job = self.jobs.get()
            if job is None:
                return
            row, pid = job
            try:
                player.play(row['plate'], row['reason'], pid)
                self.store.finish(row['id'], 'done')
                self.events.put(('finished', 'Anons tamamlandı.'))
            except Exception as exc:
                self.store.finish(row['id'], 'error', str(exc))
                self.events.put(('finished', f'Anons hatası: {exc}'))

    def poll(self):
        dirty = False
        while True:
            try:
                kind, text = self.events.get_nowait()
            except queue.Empty:
                break
            dirty = True
            if kind == 'new':
                import winsound
                try:
                    winsound.PlaySound('SystemAsterisk', winsound.SND_ALIAS | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
                    self.status.set('Yeni plaka isteği geldi.')
                except RuntimeError:
                    self.status.set('Yeni plaka isteği geldi. Bildirim sesi çalınamadı.')
            else:
                self.busy = False
                if not self.closing:
                    self.approve_button.state(['!disabled'])
                self.status.set(text)
        if dirty:
            self.refresh_table()
        if self.closing and not self.worker.is_alive():
            self.server.server_close()
            self.root.destroy()
            return
        self.root.after(150, self.poll)

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.stop.set()
        self.approve_button.state(['disabled'])
        # Kuyruk doluysa işçi önce aldığı işi (durdurarak) bitirir.
        def shutdown():
            self.server.shutdown()
            self.jobs.put(None)
        threading.Thread(target=shutdown, daemon=True).start()
        self.status.set('Kapatılıyor; müzik seviyesi geri yükleniyor…')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bank', type=Path, default=ROOT / 'ses_bankasi')
    parser.add_argument('--port', type=int, default=5000)
    args = parser.parse_args()
    if sys.platform != 'win32':
        parser.exit(1, 'Masaüstü oynatıcı Windows gerektirir. Web/çözümleyici testleri diğer sistemlerde çalışır.\n')
    root = tk.Tk()
    root.withdraw()
    try:
        bank = SoundBank(args.bank)
        store = Store(ROOT / 'istekler.sqlite3')
        Panel(root, bank, store, args.port)
    except Exception as exc:
        messagebox.showerror('Başlatılamadı', str(exc))
        root.destroy()
        return 1
    root.deiconify()
    root.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
