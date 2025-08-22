# migrate_sqlite_persona.py
from __future__ import annotations
import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def resolve_sqlite_path(dsn: str) -> Path:
    # Beklenen format: sqlite:///./app.db  veya sqlite:///C:/path/app.db
    if not dsn.startswith("sqlite:///"):
        raise SystemExit(f"Bu script sadece sqlite için yazıldı. DATABASE_URL='{dsn}'")
    path = dsn[len("sqlite:///"):]
    return Path(path).resolve()

def has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cur.fetchall()]  # [cid, name, type, notnull, dflt, pk]
    return column in cols

def main():
    dsn = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    db_path = resolve_sqlite_path(dsn)
    if not db_path.exists():
        raise SystemExit(f"SQLite dosyası bulunamadı: {db_path}\n"
                         "Eğer sıfırdan kuracaksanız app.db oluşturulması için API'yi bir kez çalıştırın.")

    print(f"[i] SQLite: {db_path}")
    conn = sqlite3.connect(str(db_path))
    try:
        # Sütun yoksa ekle (SQLite'ta JSON tipi TEXT olarak saklanır)
        if not has_column(conn, "bots", "persona_profile"):
            print("[i] bots.persona_profile sütunu ekleniyor...")
            conn.execute("ALTER TABLE bots ADD COLUMN persona_profile TEXT")
            conn.execute("UPDATE bots SET persona_profile='{}' WHERE persona_profile IS NULL")
            conn.commit()
            print("[ok] persona_profile eklendi.")
        else:
            print("[=] persona_profile zaten var, değişiklik yapılmadı.")

        # (İsteğe bağlı güvenlik) Diğer beklenen sütunlar için de kontrol:
        for col in ("speed_profile", "active_hours", "persona_hint"):
            if not has_column(conn, "bots", col):
                print(f"[uyarı] bots.{col} eksik görünüyor. Eski bir şema olabilir.")
                # Gerekirse burada ALTER TABLE eklenebilir.

        print("[bitti] Migration tamam.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
