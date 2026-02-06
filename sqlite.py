import sqlite3

def init_db():
    conn = sqlite3.connect('chat.db')
    con = conn.cursor()
    con.execute('''CREATE TABLE IF NOT EXISTS messages
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     chat_id TEXT NOT NULL,
                     message TEXT NOT NULL,
                     timestamp TEXT NOT NULL)''')
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()