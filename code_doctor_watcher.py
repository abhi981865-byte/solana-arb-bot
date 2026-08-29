import os
import sys
import time
import subprocess

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "watchdog"])
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

class BotWatcherHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_run = 0

    def on_modified(self, event):
        if event.src_path.endswith('.py') and not ('code_doctor' in event.src_path or 'venv' in event.src_path):
            current_time = time.time()
            if current_time - self.last_run > 2:  # Debounce trigger
                self.last_run = current_time
                print(f"\n[Watcher] Change detected in {event.src_path}... Running Code Doctor!")
                subprocess.run([sys.executable, "code_doctor_ultimate.py", "--fix"])

if __name__ == "__main__":
    print("🤖 Code Doctor Watcher Running... Monitoring file changes in background.")
    event_handler = BotWatcherHandler()
    observer = Observer()
    observer.schedule(event_handler, path='.', recursive=True)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\nWatcher Stopped.")
    observer.join()
