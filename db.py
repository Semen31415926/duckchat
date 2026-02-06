from flask import Flask, request, jsonify, render_template_string, send_from_directory
from datetime import datetime
import sqlite3
from sqlite import init_db as init_chat_db
from LoginDB import init_db as init_login_db
import logging
from werkzeug.utils import secure_filename
import os
import uuid
from configForServer import UPLOAD_FOLDER

file_log = logging.FileHandler('chat.log')
console_log = logging.StreamHandler()

logging.basicConfig(handlers=(file_log, console_log), format='[%(asctime)s | %(levelname)s: %(message)s]', datefmt='%Y.%m.%d %H:%M:%S', level = logging.INFO)

app = Flask(__name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

#logger = logging.getLogger(__name__)

init_chat_db()
init_login_db()

def get_db_connection():
    try:
        conn = sqlite3.connect('chat.db')
        conn.row_factory = sqlite3.Row
        logging.debug("Successfully connected to the database")
        return conn
    except Exception as e:
        logging.error(f"Error connecting to the database: {e}")
        raise

def personal_data_db_connection():
    connect = sqlite3.connect('login.db')
    connect.row_factory = sqlite3.Row
    return connect

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/upload_image', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        unique_filename = str(uuid.uuid4()) + "_" + secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)

        image_url = f"http://192.168.42.21:5000/uploads/{unique_filename}"
        return jsonify({'status': 'success', 'image_url': image_url}), 200

    return jsonify({'status': 'error', 'message': 'File type not allowed'}), 400

@app.route('/')
def index():
    return render_template_string('''
        <h1>Чат</h1>
        <form action="/send_message" method="post">
            <label for="chat_id">Chat ID:</label><br>
            <input type="text" id="chat_id" name="chat_id"><br>
            <label for="login">Login:</label><br>
            <input type="text" id="login" name="login"><br>
            <label for="message">Message:</label><br>
            <textarea id="message" name="message"></textarea><br>
            <input type="submit" value="Отправить">
        </form>
        <h2>Сообщения</h2>
        <a href="/get_messages">Получить сообщения</a>
    ''')

@app.route('/create_chat', methods=['POST'])
def create_chat():
    try:
        if request.is_json:
            data = request.json
            chat_name = data.get('name')
        else:
            chat_name = request.form.get('name')

        if not chat_name:
            return jsonify({'status': 'error', 'message': 'No chat name provided'}), 400

        created_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        conn = get_db_connection()

        cursor = conn.execute('INSERT INTO chats (name, created_at) VALUES (?, ?)',
                             (chat_name, created_at))
        chat_id = cursor.lastrowid

        welcome_message = "Это новый чат"
        conn.execute('INSERT INTO messages (chat_id, message, timestamp, login) VALUES (?, ?, ?, ?)',
                     (chat_id, welcome_message, created_at, 'system'))

        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': 'Chat created', 'chat_id': chat_id}), 200
    except Exception as e:
        logging.error(f"Error creating chat: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/mark_messages_as_read', methods=['POST'])
def mark_messages_as_read():
    try:
        if request.is_json:
            data = request.json
            chat_id = data.get('chat_id')
            user_id = data.get('user_id')
        else:
            chat_id = request.form.get('chat_id')
            user_id = request.form.get('user_id')

        if chat_id:
            conn = get_db_connection()
            conn.execute('UPDATE messages SET is_read = 1 WHERE chat_id = ?', (chat_id,))
            conn.commit()
            conn.close()
            return jsonify({'status': 'success', 'message': 'Messages marked as read'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'No chat_id provided'}), 400
    except Exception as e:
        logging.error(f"Error marking messages as read: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get_chats', methods=['GET'])
def get_chats():
    user_id = request.args.get('user_id')
    try:
        conn = get_db_connection()
        logging.debug("Connected to the database")

        query = '''
            SELECT chats.*, 
                   COUNT(CASE WHEN messages.is_read = 0 THEN 1 END) AS unread_count
            FROM chats
            LEFT JOIN messages ON chats.id = messages.chat_id
            GROUP BY chats.id
        '''
        cursor = conn.execute(query)

        chats = cursor.fetchall()
        logging.debug(f"Fetched chats: {chats}")

        conn.close()

        chats_list = [dict(chat) for chat in chats]
        logging.debug(f"Chats list: {chats_list}")

        return jsonify({'chats': chats_list}), 200
    except Exception as e:
        logging.error(f"Error fetching chats: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/send_message', methods=['POST'])
def send_message():
    if request.is_json:
        data = request.json
        message = data.get('message')
        chat_id = data.get('chat_id')
        login = data.get('login')
        image_url = data.get('image_url')
    else:
        message = request.form.get('message')
        chat_id = request.form.get('chat_id')
        login = request.form.get('login')
        image_url = request.form.get('image_url')

    if (message or image_url) and chat_id and login:
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO messages (chat_id, message, timestamp, login, image_url)
            VALUES (?, ?, ?, ?, ?)
        ''', (chat_id, message, timestamp, login, image_url))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': 'Message received'}), 200
    else:
        return jsonify({'status': 'error', 'message': 'No message, chat_id, or login provided'}), 400

@app.route('/get_messages', methods=['GET'])
def get_messages():
    chat_id = request.args.get('chat_id')
    conn = get_db_connection()

    if chat_id:
        messages = conn.execute('SELECT * FROM messages WHERE chat_id = ?', (chat_id,)).fetchall()
    else:
        messages = conn.execute('SELECT * FROM messages').fetchall()

    conn.close()

    messages_list = [dict(msg) for msg in messages]
    print("Messages with image URLs:", messages_list)
    return jsonify({'messages': messages_list}), 200

@app.route('/set_personal_date', methods=['POST'])
def set_date():
    try:
        if request.is_json:
            data = request.json
            login = data.get('login')
            password = data.get('password')
        else:
            login = request.form.get('login')
            password = request.form.get('password')

        if login and password:
            connect = personal_data_db_connection()
            connect.execute('INSERT INTO personal_date (login, password) VALUES (?, ?)',
                        (login, password))
            connect.commit()
            connect.close()
            return jsonify({'status': 'success'}), 200
        else:
            return jsonify({'status': 'error'}), 400
    except Exception as e:
        logging.error(e)


@app.route('/get_personal_date', methods=['GET'])
def get_date():
    loginN = request.args.get('login')
    connect = personal_data_db_connection()

    if loginN:
        data = connect.execute('SELECT * FROM personal_date WHERE login = ?', (loginN,)).fetchall()
    else:
        data = connect.execute('SELECT * FROM personal_date').fetchall()

    connect.close()

    data_list = [dict(row) for row in data]
    return jsonify({'data': data_list}), 200

@app.route('/login', methods=['POST'])
def login():
    if request.is_json:
        data = request.json
        login = data.get('login')
        password = data.get('password')
    else:
        login = request.form.get('login')
        password = request.form.get('password')

    if login and password:
        connect = personal_data_db_connection()
        user = connect.execute('SELECT * FROM personal_date WHERE login = ? AND password = ?', (login, password)).fetchone()
        connect.close()

        if user:
            return jsonify({'status': 'success', 'message': 'Login successful'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Invalid login or password'}), 401
    else:
        return jsonify({'status': 'error', 'message': 'No login or password provided'}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)