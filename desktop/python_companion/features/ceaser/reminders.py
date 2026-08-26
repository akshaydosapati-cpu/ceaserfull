import sqlite3
import threading
import time
from datetime import datetime
from plyer import notification
import os

class Reminders:
    def __init__(self, db_path='reminders_local.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._create_table()
        self.running = True
        self.thread = threading.Thread(target=self._reminder_loop, daemon=True)
        self.thread.start()

    def _create_table(self):
        with self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT,
                    remind_at TEXT,
                    notified INTEGER DEFAULT 0
                )
            ''')

    def add_reminder(self, message, time_str):
        with self.conn:
            self.conn.execute('''
                INSERT INTO reminders (message, remind_at) VALUES (?, ?)
            ''', (message, time_str))

    def list_reminders(self):
        with self.conn:
            cursor = self.conn.execute('SELECT id, message, remind_at, notified FROM reminders ORDER BY remind_at ASC')
            return [
                {"id": row[0], "message": row[1], "remind_at": row[2], "notified": bool(row[3])}
                for row in cursor.fetchall()
            ]

    def update_reminder(self, reminder_id, message=None, time_str=None):
        with self.conn:
            if message and time_str:
                self.conn.execute('UPDATE reminders SET message = ?, remind_at = ? WHERE id = ?', (message, time_str, reminder_id))
            elif message:
                self.conn.execute('UPDATE reminders SET message = ? WHERE id = ?', (message, reminder_id))
            elif time_str:
                self.conn.execute('UPDATE reminders SET remind_at = ? WHERE id = ?', (time_str, reminder_id))

    def delete_reminder(self, reminder_id):
        with self.conn:
            self.conn.execute('DELETE FROM reminders WHERE id = ?', (reminder_id,))

    def _reminder_loop(self):
        while self.running:
            now = datetime.now().strftime('%Y-%m-%d %H:%M')
            with self.conn:
                cursor = self.conn.execute('''
                    SELECT id, message FROM reminders WHERE remind_at <= ? AND notified = 0
                ''', (now,))
                for row in cursor.fetchall():
                    notification.notify(
                        title='Reminder',
                        message=row[1],
                        timeout=10
                    )
                    self.conn.execute('UPDATE reminders SET notified = 1 WHERE id = ?', (row[0],))
            time.sleep(30)

    def close(self):
        self.running = False
        self.thread.join()
        self.conn.close() 