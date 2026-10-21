import sqlite3

def init_db(db_path="kristiansand_okonomi.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        bruker_id VARCHAR(50),
        rolle VARCHAR(30),
        handling_kategori VARCHAR(50),
        ansvar_spurt_om VARCHAR(10),
        sporring_tekst TEXT,
        ai_respons_sammendrag TEXT
    )
    """)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
