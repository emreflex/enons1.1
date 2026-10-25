"""HTTP ve masaüstü iş parçacıkları için kalıcı, sınırlı istek kuyruğu."""
import sqlite3
import threading
from datetime import datetime


class Store:
    def __init__(self, path):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('''CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY, created TEXT NOT NULL, plate TEXT NOT NULL,
            reason TEXT NOT NULL, status TEXT NOT NULL, error TEXT NOT NULL DEFAULT '')''')
        with self.db:
            self.db.execute("UPDATE requests SET status='error', error='Önceki oturum kesildi; tekrar onaylayın.' WHERE status='playing'")

    def add(self, plate, reason):
        with self.lock, self.db:
            count = self.db.execute("SELECT count(*) FROM requests WHERE status IN ('pending','playing','error')").fetchone()[0]
            if count >= 200:
                raise ValueError('İstek kuyruğu dolu. Görevlinin mevcut istekleri işlemesini bekleyiniz.')
            cur = self.db.execute('INSERT INTO requests(created,plate,reason,status) VALUES(?,?,?,?)',
                                  (datetime.now().isoformat(timespec='seconds'), plate, reason, 'pending'))
            return cur.lastrowid

    def rows(self):
        with self.lock:
            return [dict(row) for row in self.db.execute(
                "SELECT * FROM requests ORDER BY CASE WHEN status IN ('pending','playing','error') THEN 0 ELSE 1 END, id DESC LIMIT 500")]

    def claim(self, request_id):
        with self.lock, self.db:
            cur = self.db.execute("UPDATE requests SET status='playing', error='' WHERE id=? AND status IN ('pending','error')", (request_id,))
            if not cur.rowcount:
                return None
            return dict(self.db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone())

    def finish(self, request_id, status, error=''):
        with self.lock, self.db:
            self.db.execute('UPDATE requests SET status=?,error=? WHERE id=?', (status, error[:500], request_id))

    def reject(self, request_id):
        with self.lock, self.db:
            self.db.execute("UPDATE requests SET status='rejected' WHERE id=? AND status IN ('pending','error')", (request_id,))
