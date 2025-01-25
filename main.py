import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_pymongo import PyMongo
from bson import ObjectId
import bcrypt
import jwt
import base64
import datetime

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuration
app.config['MONGO_URI'] = os.getenv('MONGO_URI', 'mongodb://localhost:27017/PostPal')
app.config['SECRET_KEY'] = os.getenv('JWT_SECRET')
app.config['JSON_SORT_KEYS'] = False

# MongoDB Connection
mongo = PyMongo(app)

# User Model
class User:
    @staticmethod
    def register(username, password):
        existing_user = mongo.db.users.find_one({'username': username})
        if existing_user:
            return None

        # Hash password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        user_data = {
            'username': username,
            'password': hashed_password,
            'score': 0
        }
        return mongo.db.users.insert_one(user_data)

    @staticmethod
    def login(username, password):
        user = mongo.db.users.find_one({'username': username})
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
            token = jwt.encode(
                {'userId': str(user['_id']), 'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)}, 
                app.config['SECRET_KEY'], 
                algorithm='HS256'
            )
            return token
        return None

# Authentication Decorator
def token_required(f):
    def decorator(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]
        
        if not token:
            return jsonify({'message': 'Access Denied: No Token Provided'}), 401
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user_id = ObjectId(data['userId'])
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid Token'}), 401
        
        return f(current_user_id, *args, **kwargs)
    return decorator

# Routes
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': 'Username and password are required'}), 400

    result = User.register(username, password)
    if result:
        return jsonify({'message': 'User registered successfully'}), 201
    else:
        return jsonify({'message': 'Username already exists'}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': 'Username and password are required'}), 400

    token = User.login(username, password)
    if token:
        return jsonify({'token': token, 'message': 'Login successful'})
    else:
        return jsonify({'message': 'Invalid username or password'}), 400

@app.route('/gallery', methods=['GET'])
@token_required
def get_gallery(current_user_id):
    images = list(mongo.db.images.find({'user': current_user_id}).sort('createdAt', -1))
    for image in images:
        image['_id'] = str(image['_id'])
    return jsonify({'images': images})

@app.route('/score', methods=['GET'])
@token_required
def get_score(current_user_id):
    user = mongo.db.users.find_one({'_id': current_user_id}, {'score': 1})
    if user:
        return jsonify({'score': user['score']})
    return jsonify({'message': 'User not found'}), 404

@app.route('/score', methods=['POST'])
@token_required
def update_score(current_user_id):
    data = request.get_json()
    score = data.get('score')

    if not isinstance(score, (int, float)):
        return jsonify({'message': 'Score must be a number'}), 400

    result = mongo.db.users.update_one(
        {'_id': current_user_id},
        {'$set': {'score': score}}
    )

    if result.modified_count:
        user = mongo.db.users.find_one({'_id': current_user_id}, {'score': 1})
        return jsonify({'score': user['score']})
    
    return jsonify({'message': 'User not found'}), 404

@app.route('/upload', methods=['POST'])
@token_required
def upload_image(current_user_id):
    data = request.get_json()
    image = data.get('image')
    title = data.get('title', 'Untitled')

    if not image:
        return jsonify({'message': 'Image data is required'}), 400

    try:
        # Validate Base64 string
        header, encoded = image.split(",", 1)
        content_type = header.split(":")[1].split(";")[0]
        
        # Decode and check file size
        decoded_image = base64.b64decode(encoded)
        file_size_mb = len(decoded_image) / (1024 * 1024)
        
        if file_size_mb > 5:
            return jsonify({'message': 'Image size exceeds 5MB limit'}), 400

        # Save image
        image_data = {
            'user': current_user_id,
            'title': title,
            'data': encoded,
            'contentType': content_type,
            'createdAt': datetime.datetime.utcnow()
        }
        result = mongo.db.images.insert_one(image_data)
        
        return jsonify({
            'message': 'Image uploaded successfully', 
            'image': {
                '_id': str(result.inserted_id),
                'title': title
            }
        }), 201

    except Exception as e:
        return jsonify({'message': 'Server Error', 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port)