const request = require('supertest');
const app = require('../app'); // Assuming your Express app is exported from app.js or index.js

let authToken = '';

describe('Authentication API', () => {
  
  test('POST /register - should register a new user', async () => {
    const res = await request(app)
      .post('/register')
      .send({ username: 'testuser', password: 'securepassword' });
    
    expect(res.statusCode).toBe(201);
    expect(res.body).toHaveProperty('message', 'User registered successfully');
  });

  test('POST /register - should not allow duplicate usernames', async () => {
    const res = await request(app)
      .post('/register')
      .send({ username: 'testuser', password: 'securepassword' });
    
    expect(res.statusCode).toBe(400);
    expect(res.body).toHaveProperty('error', 'Username already exists');
  });

  test('POST /login - should log in an existing user and return a token', async () => {
    const res = await request(app)
      .post('/login')
      .send({ username: 'testuser', password: 'securepassword' });
    
    expect(res.statusCode).toBe(200);
    expect(res.body).toHaveProperty('token');
    authToken = res.body.token;
  });

  test('POST /login - should reject invalid credentials', async () => {
    const res = await request(app)
      .post('/login')
      .send({ username: 'testuser', password: 'wrongpassword' });
    
    expect(res.statusCode).toBe(401);
    expect(res.body).toHaveProperty('error', 'Invalid credentials');
  });

  test('GET /protected - should reject requests without a token', async () => {
    const res = await request(app).get('/protected');
    expect(res.statusCode).toBe(401);
    expect(res.body).toHaveProperty('error', 'Unauthorized');
  });

  test('GET /protected - should allow access with valid token', async () => {
    const res = await request(app)
      .get('/protected')
      .set('Authorization', `Bearer ${authToken}`);
    
    expect(res.statusCode).toBe(200);
    expect(res.body).toHaveProperty('secretData');
  });

  test('GET /protected - should reject requests with an invalid token', async () => {
    const res = await request(app)
      .get('/protected')
      .set('Authorization', 'Bearer invalidtoken');
    
    expect(res.statusCode).toBe(403);
    expect(res.body).toHaveProperty('error', 'Invalid token');
  });
});
