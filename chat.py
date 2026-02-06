import sqlite3

def init_db():
    conn = sqlite3.connect('chat.db')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            is_private INTEGER NOT NULL,
            creator_id INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            login TEXT NOT NULL,
            image_url TEXT,
            is_read INTEGER,
            FOREIGN KEY (chat_id) REFERENCES chats (id)
        )
    ''')
    conn.execute('''
            CREATE TABLE IF NOT EXISTS chat_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES chats (id),
                FOREIGN KEY (user_id) REFERENCES personal_date (id)
            )
        ''')
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()