import shutil
from datetime import datetime
from pathlib import Path

from database.banco import BANCO


class Backup:
    def criar_backup(self):
        destino = Path(BANCO).parent / f"backup_{datetime.now():%d_%m_%Y_%H_%M}.db"
        shutil.copy2(BANCO, destino)
        return destino
