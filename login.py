import sqlite3

def init_db():
    con = sqlite3.connect('login.db')
    connect = con.cursor()
    connect.execute('''CREATE TABLE IF NOT EXISTS personal_date
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     login TEXT NOT NULL,
                     password TEXT NOT NULL)''')
    con.commit()
    con.close()

if __name__ == '__main__':
    init_db()