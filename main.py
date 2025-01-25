import os
import base64
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
import jwt
from openai import OpenAI
from dotenv import load_dotenv
import hashlib

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('MONGO_URI', 'sqlite:///posepal.db')
app.config['SECRET_KEY'] = os.getenv('JWT_SECRET')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
CORS(app)

# Omnistack OpenAI Client
omnistack_client = OpenAI(
    base_url="https://api.omnistack.sh/openai/v1", 
    api_key=""
)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    score = db.Column(db.Integer, default=0)


# Authentication Middleware
def token_required(f):
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]
        
        if not token:
            return jsonify({'message': 'Access Denied: No Token Provided'}), 401
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.filter_by(id=data['user_id']).first()
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid Token'}), 401
        
        return f(current_user, *args, **kwargs)
    return decorated

# Route Handlers
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': 'Username and password are required'}), 400

    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({'message': 'Username already exists'}), 400

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    new_user = User(username=username, password=hashed_password)
    
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()
    if not user or not bcrypt.check_password_hash(user.password, password):
        return jsonify({'message': 'Invalid username or password'}), 400

    token = jwt.encode({
        'user_id': user.id, 
        'exp': datetime.utcnow() + timedelta(hours=1)
    }, app.config['SECRET_KEY'], algorithm='HS256')

    return jsonify({'token': token, 'message': 'Login successful'})

@app.route('/score', methods=['GET'])
@token_required
def get_score(current_user):
    return jsonify({'score': current_user.score})

@app.route('/score', methods=['POST'])
@token_required
def update_score(current_user):
    data = request.json
    score = data.get('score')

    if not isinstance(score, int):
        return jsonify({'message': 'Score must be a number'}), 400

    current_user.score = score
    db.session.commit()

    return jsonify({'score': current_user.score})

@app.route('/upload', methods=['POST'])
@token_required
def upload_image(current_user):
    data = request.json
    image = data.get('image')
    title = data.get('title', 'Untitled')

    if not image:
        return jsonify({'message': 'Image data is required'}), 400

    # Validate Base64 format
    try:
        header, encoded = image.split(";base64,")
        content_type = header.split(":")[1]
        
        # Validate file size
        decoded = base64.b64decode(encoded)
        size_mb = len(decoded) / (1024 * 1024)
        if size_mb > 5:
            return jsonify({'message': 'Image size exceeds 5MB limit'}), 400

        new_image = Image(
            user_id=current_user.id, 
            title=title, 
            data=encoded, 
            content_type=content_type
        )
        
        db.session.add(new_image)
        db.session.commit()

        return jsonify({
            'message': 'Image uploaded successfully', 
            'image': {
                'id': new_image.id, 
                'title': new_image.title
            }
        }), 201

    except Exception as e:
        return jsonify({'message': 'Invalid image format'}), 400

@app.route('/prompt', methods=['GET'])
@token_required
def get_prompt(current_user):
    try:
        # Generate daily prompt based on current date
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Use hash to deterministically generate a daily prompt
        daily_prompt_seed = hashlib.md5(today.encode()).hexdigest()
        
        # Generate daily prompt using Omnistack
        daily_prompt_response = omnistack_client.chat.completions.create(
            model="belle_belle_concepcion",
            messages=[
                {"role": "system", "content": "Generate a unique daily photo pose suggestion based on a seed."},
                {"role": "user", "content": f"Create a creative pose suggestion using this seed: {daily_prompt_seed}"}
            ]
        )
        
        daily_prompt = daily_prompt_response.choices[0].message.content

        # Generate random prompts
        random_prompts_response = omnistack_client.chat.completions.create(
            model="belle_belle_concepcion",
            messages=[
                {"role": "system", "content": "Generate 3 unique, fun photo pose suggestions."},
                {"role": "user", "content": "Suggest some creative and engaging photo poses."}
            ]
        )
        
        random_prompts = [
            choice.message.content 
            for choice in random_prompts_response.choices 
            if choice.message.content
        ]
        
        return jsonify({
            'daily_prompt': daily_prompt,
            'random_prompts': random_prompts
        })
    
    except Exception as e:
        return jsonify({'message': 'Error generating prompts', 'error': str(e)}), 500

# Create tables
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(port=8000, debug=True)
