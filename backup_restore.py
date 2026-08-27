import shutil, os
from datetime import datetime
from config import Config
def backup(): os.makedirs('data/backups', exist_ok=True); shutil.copy(Config.DB_PATH, f'data/backups/backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'); print('Backup created')
if __name__ == '__main__': backup()
