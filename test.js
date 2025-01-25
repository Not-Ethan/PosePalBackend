// tests/app.test.js

const request = require('supertest');
const mongoose = require('mongoose');
const { MongoMemoryServer } = require('mongodb-memory-server');
const jwt = require('jsonwebtoken');
require('dotenv').config();

const app = require('./main'); // Adjust the path if your app file is located elsewhere

const User = mongoose.model('User');

let mongoServer;

beforeAll(async () => {
    // Initialize in-memory MongoDB server
    mongoServer = await MongoMemoryServer.create();
    const uri = mongoServer.getUri();

    // Connect to in-memory MongoDB
    await mongoose.connect(uri, {
        useNewUrlParser: true,
        useUnifiedTopology: true,
    });
});

afterAll(async () => {
    // Close MongoDB connection and stop server
    await mongoose.connection.dropDatabase();
    await mongoose.connection.close();
    await mongoServer.stop();
});

beforeEach(async () => {
    // Clear all collections before each test
    const collections = mongoose.connection.collections;
    for (const key in collections) {
        await collections[key].deleteMany({});
    }
});

describe('Authentication API', () => {
    const userData = {
        username: 'testuser',
        password: 'Test@1234',
    };

    describe('POST /register', () => {
        it('should register a new user successfully', async () => {
            const res = await request(app)
                .post('/register')
                .send(userData);
            
            expect(res.statusCode).toEqual(201);
            expect(res.body).toHaveProperty('message', 'User registered successfully');

            // Verify user is saved in the database
            const user = await User.findOne({ username: userData.username });
            expect(user).toBeTruthy();
            expect(user.username).toBe(userData.username);
            // Password should be hashed
            expect(user.password).not.toBe(userData.password);
        });

        it('should not register a user with an existing username', async () => {
            // First registration
            await request(app)
                .post('/register')
                .send(userData);
            
            // Attempt duplicate registration
            const res = await request(app)
                .post('/register')
                .send(userData);
            
            expect(res.statusCode).toEqual(400);
            expect(res.body).toHaveProperty('message', 'Username already exists');
        });

        it('should not register a user without username', async () => {
            const res = await request(app)
                .post('/register')
                .send({ password: 'password123' });
            
            expect(res.statusCode).toEqual(500); // Since validation is handled by Mongoose
            expect(res.body).toHaveProperty('message', 'Server Error');
        });

        it('should not register a user without password', async () => {
            const res = await request(app)
                .post('/register')
                .send({ username: 'userwithoutpassword' });
            
            expect(res.statusCode).toEqual(500);
            expect(res.body).toHaveProperty('message', 'Server Error');
        });
    });

    describe('POST /login', () => {
        beforeEach(async () => {
            // Register a user before testing login
            const salt = await bcrypt.genSalt(10);
            const hashedPassword = await bcrypt.hash(userData.password, salt);
            const newUser = new User({ username: userData.username, password: hashedPassword });
            await newUser.save();
        });

        it('should login successfully with correct credentials', async () => {
            const res = await request(app)
                .post('/login')
                .send(userData);
            
            expect(res.statusCode).toEqual(200);
            expect(res.body).toHaveProperty('token');
            expect(res.body).toHaveProperty('message', 'Login successful');

            // Verify JWT
            const decoded = jwt.verify(res.body.token, process.env.JWT_SECRET);
            expect(decoded).toHaveProperty('userId');
        });

        it('should not login with incorrect password', async () => {
            const res = await request(app)
                .post('/login')
                .send({ username: userData.username, password: 'WrongPassword' });
            
            expect(res.statusCode).toEqual(400);
            expect(res.body).toHaveProperty('message', 'Invalid username or password');
        });

        it('should not login with non-existing username', async () => {
            const res = await request(app)
                .post('/login')
                .send({ username: 'nonexistentuser', password: 'SomePassword' });
            
            expect(res.statusCode).toEqual(400);
            expect(res.body).toHaveProperty('message', 'Invalid username or password');
        });

        it('should not login without username', async () => {
            const res = await request(app)
                .post('/login')
                .send({ password: 'password123' });
            
            expect(res.statusCode).toEqual(500);
            expect(res.body).toHaveProperty('message', 'Server Error');
        });

        it('should not login without password', async () => {
            const res = await request(app)
                .post('/login')
                .send({ username: userData.username });
            
            expect(res.statusCode).toEqual(500);
            expect(res.body).toHaveProperty('message', 'Server Error');
        });
    });

    describe('GET /protected', () => {
        let token;

        beforeEach(async () => {
            // Register and login to get a valid token
            await request(app)
                .post('/register')
                .send(userData);
            
            const res = await request(app)
                .post('/login')
                .send(userData);
            
            token = res.body.token;
        });

        it('should access protected route with valid token', async () => {
            const res = await request(app)
                .get('/protected')
                .set('Authorization', `Bearer ${token}`);
            
            expect(res.statusCode).toEqual(200);
            expect(res.body).toHaveProperty('message', 'Welcome to the protected route!');
            expect(res.body).toHaveProperty('userId');
        });

        it('should not access protected route without token', async () => {
            const res = await request(app)
                .get('/protected');
            
            expect(res.statusCode).toEqual(401);
            expect(res.body).toHaveProperty('message', 'Access Denied');
        });

        it('should not access protected route with invalid token', async () => {
            const res = await request(app)
                .get('/protected')
                .set('Authorization', 'Bearer InvalidToken');
            
            expect(res.statusCode).toEqual(401);
            expect(res.body).toHaveProperty('message', 'Invalid Token');
        });

        it('should not access protected route with expired token', async () => {
            // Create a token that expires immediately
            const expiredToken = jwt.sign({ userId: 'dummyid' }, process.env.JWT_SECRET, { expiresIn: '1ms' });
            // Wait for token to expire
            await new Promise(resolve => setTimeout(resolve, 10));

            const res = await request(app)
                .get('/protected')
                .set('Authorization', `Bearer ${expiredToken}`);
            
            expect(res.statusCode).toEqual(401);
            expect(res.body).toHaveProperty('message', 'Invalid Token');
        });
    });
});
