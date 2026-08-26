import sqlite3
import threading
import time
from datetime import datetime, timedelta
from plyer import notification
import platform

try:
    if platform.system() == 'Windows':
        import winsound
    else:
        winsound = None
except ImportError:
    winsound = None

class NotificationAssistant:
    def __init__(self, db_path='reminders.db'):
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
                    spoken INTEGER DEFAULT 0
                )
            ''')

    def set_reminder(self, message, time_str):
        # Parse time_str to a datetime (very basic, can be improved)
        try:
            remind_at = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
        except Exception:
            # fallback: try just hour:minute today
            try:
                now = datetime.now()
                hour, minute = map(int, time_str.split(':'))
                remind_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            except Exception:
                remind_at = datetime.now() + timedelta(minutes=1)  # fallback: 1 min from now
        with self.conn:
            self.conn.execute('''
                INSERT INTO reminders (message, remind_at) VALUES (?, ?)
            ''', (message, remind_at.strftime('%Y-%m-%d %H:%M')))

    def _reminder_loop(self):
        while self.running:
            now = datetime.now().strftime('%Y-%m-%d %H:%M')
            with self.conn:
                cursor = self.conn.execute('''
                    SELECT id, message FROM reminders WHERE remind_at <= ? AND spoken = 0
                ''', (now,))
                found = False
                for row in cursor.fetchall():
                    found = True
                    print(f'[DEBUG] Triggering reminder: {row[1]} (id={row[0]})')
                    self._notify(row[1])
                    self.conn.execute('UPDATE reminders SET spoken = 1 WHERE id = ?', (row[0],))
            time.sleep(1)  # Check every second for instant reminders

    def _notify(self, message):
        print(f'[DEBUG] plyer_notification is: {notification}')
        if notification is None:
            if notification is None:
                print('[ERROR] plyer_notification is None. Please check for shadowing or import issues.')
                return
            print(f'[DEBUG] Showing notification: {message}')
            notification.notify(
                title='Ceaser Reminder',
                message=message,
                timeout=10
            )
            if platform.system() == 'Windows' and winsound is not None:
                try:
                    winsound.MessageBeep()
                except:
                    pass
            # You can add more sound logic for other operating systems if needed

    def list_reminders(self):
        with self.conn:
            cursor = self.conn.execute('SELECT id, message, remind_at, spoken FROM reminders ORDER BY remind_at ASC')
            return [
                {"id": row[0], "message": row[1], "remind_at": row[2], "spoken": bool(row[3])}
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

    def close(self):
        self.running = False
        self.thread.join()
        self.conn.close()

    def send_notification(self, message, title='Ceaser Notification', icon_path=None, sound=True):
        """Show a Windows toast notification instantly."""
        try:
            notification.notify(
                title=title,
                message=message,
                app_icon=icon_path,
                timeout=10
            )
            if sound and platform.system() == 'Windows':
                winsound.MessageBeep()
            return 'Notification sent.'
        except Exception as e:
            return f'Failed to send notification: {e}'
