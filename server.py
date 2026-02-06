from flask import Flask, request, jsonify, render_template_string, send_from_directory
from datetime import datetime
import sqlite3
from chat import init_db as init_chat_db
from login import init_db as init_login_db
import logging
from werkzeug.utils import secure_filename
import os
import uuid
from configForServer import UPLOAD_FOLDER

file_log = logging.FileHandler('chat.log')
console_log = logging.StreamHandler()

logging.basicConfig(handlers=(file_log, console_log), format='[%(asctime)s | %(levelname)s: %(message)s]',
                    datefmt='%Y.%m.%d %H:%M:%S', level=logging.INFO)

app = Flask(__name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# logger = logging.getLogger(__name__)

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
    logging.error(f"Start upload image")

    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        unique_filename = str(uuid.uuid4()) + "_" + secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)

        image_url = f"{request.host_url}/uploads/{unique_filename}"
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


@app.route('/create_group_chat', methods=['POST'])
def create_group_chat():
    try:
        data = request.get_json()
        if not data:
            logging.error("No JSON data received in create_group_chat")
            return jsonify({'status': 'error', 'message': 'No JSON data provided'}), 400

        logging.info(f"Received data: {data}")

        group_name = data.get('name')
        creator_id = data.get('creator_id')
        user_ids = data.get('user_ids', [])

        if not group_name or not creator_id or not isinstance(user_ids, list):
            logging.error(f"Missing required fields. name={group_name}, creator_id={creator_id}, user_ids={user_ids}")
            return jsonify({'status': 'error', 'message': 'Missing or invalid required fields'}), 400

        if creator_id not in user_ids:
            user_ids.append(creator_id)

        created_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        conn = get_db_connection()

        try:
            cursor = conn.execute(
                'INSERT INTO chats (name, created_at, is_private, creator_id) VALUES (?, ?, 0, ?)',
                (group_name, created_at, creator_id)
            )
            chat_id = cursor.lastrowid

            for user_id in user_ids:
                conn.execute('INSERT INTO chat_members (chat_id, user_id) VALUES (?, ?)',
                             (chat_id, str(user_id)))

            welcome_message = f"Группа '{group_name}' создана"
            conn.execute(
                'INSERT INTO messages (chat_id, message, timestamp, login) VALUES (?, ?, ?, ?)',
                (chat_id, welcome_message, created_at, 'system')
            )

            conn.commit()
            return jsonify({
                'status': 'success',
                'chat_id': chat_id,
                'group_name': group_name,
                'members': user_ids
            }), 200
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    except Exception as e:
        logging.error(f"Error creating group chat: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/get_all_users', methods=['GET'])
def get_all_users():
    try:
        conn = personal_data_db_connection()
        cursor = conn.execute('SELECT id, login FROM personal_date')
        users = cursor.fetchall()
        conn.close()

        users_list = [dict(user) for user in users]
        return jsonify({'users': users_list}), 200
    except Exception as e:
        logging.error(f"Error fetching users: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/get_user_id', methods=['GET'])
def get_user_id():
    login = request.args.get('login')
    if not login:
        return jsonify({'status': 'error', 'message': 'No login provided'}), 400

    try:
        conn = personal_data_db_connection()
        cursor = conn.execute('SELECT id FROM personal_date WHERE login = ?', (login,))
        user = cursor.fetchone()
        conn.close()

        if user:
            return jsonify({'status': 'success', 'user_id': user['id']}), 200
        else:
            return jsonify({'status': 'error', 'message': 'User not found'}), 404
    except Exception as e:
        logging.error(f"Error fetching user ID: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/create_chat', methods=['POST'])
def create_chat():
    try:
        logging.info(f"Headers: {request.headers}")
        logging.info(f"Content-Type: {request.content_type}")

        if request.is_json:
            data = request.get_json()
            logging.info(f"JSON data received: {data}")
            chat_name = data.get('name')
        else:
            chat_name = request.form.get('name')
            logging.info(f"Form data received: {request.form}")

        if not chat_name:
            logging.error("No chat name provided in create_chat request")
            return jsonify({'status': 'error', 'message': 'No chat name provided'}), 400

        created_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        conn = get_db_connection()

        try:
            logging.info(f"Attempting to create chat: {chat_name}")
            cursor = conn.execute('INSERT INTO chats (name, created_at) VALUES (?, ?)',
                                  (chat_name, created_at))
            chat_id = cursor.lastrowid

            welcome_message = "Это новый чат"
            conn.execute('INSERT INTO messages (chat_id, message, timestamp, login) VALUES (?, ?, ?, ?)',
                         (chat_id, welcome_message, created_at, 'system'))

            conn.commit()
            logging.info(f"Successfully created chat {chat_id}: {chat_name}")
            return jsonify({'status': 'success', 'message': 'Chat created', 'chat_id': chat_id}), 200
        except sqlite3.Error as e:
            conn.rollback()
            logging.error(f"Database error creating chat {chat_name}: {str(e)}")
            return jsonify({'status': 'error', 'message': 'Database error'}), 500
        except Exception as e:
            conn.rollback()
            logging.error(f"Unexpected error creating chat {chat_name}: {str(e)}", exc_info=True)
            return jsonify({'status': 'error', 'message': 'Unexpected error'}), 500
        finally:
            conn.close()
    except Exception as e:
        logging.error(f"Error in create_chat endpoint: {str(e)}", exc_info=True)
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
    if not user_id:
        return jsonify({'status': 'error', 'message': 'No user_id provided'}), 400

    try:
        conn = get_db_connection()

        query = '''
            SELECT chats.*, 
                   COUNT(CASE WHEN messages.is_read = 0 AND messages.login != ? THEN 1 END) AS unread_count
            FROM chats
            JOIN chat_members ON chats.id = chat_members.chat_id
            LEFT JOIN messages ON chats.id = messages.chat_id
            WHERE chat_members.user_id = ?
            GROUP BY chats.id
        '''
        cursor = conn.execute(query, (user_id, user_id))
        chats = cursor.fetchall()

        conn.close()

        chats_list = [dict(chat) for chat in chats]
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
    user_id = request.args.get('user_id')

    if not chat_id or not user_id:
        return jsonify({'status': 'error', 'message': 'No chat_id or user_id provided'}), 400

    try:
        conn = get_db_connection()

        member = conn.execute(
            'SELECT 1 FROM chat_members WHERE chat_id = ? AND user_id = ?',
            (chat_id, user_id)
        ).fetchone()

        if not member:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Access denied'}), 403

        messages = conn.execute(
            'SELECT * FROM messages WHERE chat_id = ? ORDER BY timestamp',
            (chat_id,)
        ).fetchall()

        conn.close()

        messages_list = [dict(msg) for msg in messages]
        return jsonify({'messages': messages_list}), 200

    except Exception as e:
        logging.error(f"Error fetching messages: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


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


@app.route('/get_user_chats', methods=['GET'])
def get_user_chats():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'status': 'error', 'message': 'No user_id provided'}), 400

    try:
        conn = get_db_connection()
        query = '''
            SELECT chats.*, COUNT(CASE WHEN messages.is_read = 0 AND messages.login != ? THEN 1 END) AS unread_count
            FROM chats
            JOIN chat_members ON chats.id = chat_members.chat_id
            LEFT JOIN messages ON chats.id = messages.chat_id
            WHERE chat_members.user_id = ?
            GROUP BY chats.id
        '''
        cursor = conn.execute(query, (user_id, user_id))
        chats = cursor.fetchall()
        conn.close()

        chats_list = [dict(chat) for chat in chats]
        return jsonify({'chats': chats_list}), 200
    except Exception as e:
        logging.error(f"Error fetching user chats: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/add_user_to_chat', methods=['POST'])
def add_user_to_chat():
    try:
        data = request.json
        chat_id = data.get('chat_id')
        user_id = data.get('user_id')
        adder_id = data.get('adder_id')

        if not all([chat_id, user_id, adder_id]):
            return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

        conn = get_db_connection()

        cursor = conn.execute('SELECT creator_id FROM chats WHERE id = ?', (chat_id,))
        chat = cursor.fetchone()

        if not chat or chat['creator_id'] != adder_id:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Not authorized to add users to this chat'}), 403

        cursor = conn.execute('SELECT id FROM chat_members WHERE chat_id = ? AND user_id = ?', (chat_id, user_id))
        if cursor.fetchone():
            conn.close()
            return jsonify({'status': 'error', 'message': 'User is already in the chat'}), 400

        conn.execute('INSERT INTO chat_members (chat_id, user_id) VALUES (?, ?)', (chat_id, user_id))
        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'message': 'User added to chat'}), 200
    except Exception as e:
        logging.error(f"Error adding user to chat: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/create_private_chat', methods=['POST'])
def create_private_chat():
    try:
        data = request.get_json()
        logging.info(f"Received data for private chat: {data}")

        user1_id = str(data.get('user1_id'))
        user2_id = str(data.get('user2_id'))
        logging.info(f"User IDs received: {user1_id} (user1), {user2_id} (user2)")

        login_conn = personal_data_db_connection()
        all_users = login_conn.execute('SELECT id, login FROM personal_date').fetchall()
        logging.info(f"All users in DB: {[dict(u) for u in all_users]}")
        user1_exists = login_conn.execute('SELECT 1 FROM personal_date WHERE id = ?', (user1_id,)).fetchone()
        user2_exists = login_conn.execute('SELECT 1 FROM personal_date WHERE id = ?', (user2_id,)).fetchone()
        login_conn.close()

        if not user1_exists or not user2_exists:
            return jsonify({
                'status': 'error',
                'message': 'One or both users not found',
                'user1_exists': bool(user1_exists),
                'user2_exists': bool(user2_exists)
            }), 404

        chat_conn = get_db_connection()
        existing_chat = chat_conn.execute('''
            SELECT c.id FROM chats c
            JOIN chat_members cm1 ON c.id = cm1.chat_id AND cm1.user_id = ?
            JOIN chat_members cm2 ON c.id = cm2.chat_id AND cm2.user_id = ?
            WHERE c.is_private = 1
        ''', (user1_id, user2_id)).fetchone()

        if existing_chat:
            chat_conn.close()
            return jsonify({
                'status': 'success',
                'chat_id': existing_chat['id'],
                'message': 'Chat already exists'
            }), 200

        created_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        chat_name = f"Private chat {user1_id}-{user2_id}"

        cursor = chat_conn.execute(
            'INSERT INTO chats (name, created_at, is_private, creator_id) VALUES (?, ?, 1, ?)',
            (chat_name, created_at, user1_id)
        )
        chat_id = cursor.lastrowid

        chat_conn.execute('INSERT INTO chat_members (chat_id, user_id) VALUES (?, ?)', (chat_id, user1_id))
        chat_conn.execute('INSERT INTO chat_members (chat_id, user_id) VALUES (?, ?)', (chat_id, user2_id))

        chat_conn.execute(
            'INSERT INTO messages (chat_id, message, timestamp, login) VALUES (?, ?, ?, ?)',
            (chat_id, f"Приватный чат создан", created_at, 'system')
        )

        chat_conn.commit()
        chat_conn.close()

        return jsonify({
            'status': 'success',
            'chat_id': chat_id,
            'chat_name': chat_name
        }), 200

    except Exception as e:
        logging.error(f"Error creating private chat: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.before_request
def log_request_info():
    logging.info(f"Request: {request.method} {request.path}")
    if request.method == 'POST' and request.content_type == 'application/json':
        logging.debug(f"Request data: {request.get_json()}")


@app.after_request
def log_response_info(response):
    logging.info(f"Response: {response.status}")
    return response


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
        user = connect.execute('SELECT * FROM personal_date WHERE login = ? AND password = ?',
                               (login, password)).fetchone()
        connect.close()

        if user:
            return jsonify({
                'status': 'success',
                'message': 'Login successful',
                'user_id': user['id']
            }), 200
        else:
            return jsonify({'status': 'error', 'message': 'Invalid login or password'}), 401
    else:
        return jsonify({'status': 'error', 'message': 'No login or password provided'}), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)