require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 8000;
const JWT_SECRET = process.env.JWT_SECRET;
const MONGO_URI = process.env.MONGO_URI || "mongodb://localhost:27017/PostPal";

// Middleware
app.use(express.json({ limit: '10mb' })); // Increase payload limit if necessary
app.use(cors());

// MongoDB Connection
mongoose.connect(MONGO_URI, {
    useNewUrlParser: true,
    useUnifiedTopology: true,
}).then(() => console.log('MongoDB Connected ✅'))
  .catch(err => console.error('MongoDB Connection Error:', err));

// User Schema & Model
const userSchema = new mongoose.Schema({
    username: { type: String, required: true, unique: true },
    password: { type: String, required: true },
    score: { type: Number, default: 0 } // Added score field
});
const User = mongoose.model('User', userSchema);

// Image Schema & Model
const imageSchema = new mongoose.Schema({
    user: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
    title: { type: String },
    data: { type: String, required: true }, // Base64 encoded string
    contentType: { type: String, required: true }, // MIME type
    createdAt: { type: Date, default: Date.now }
});
const Image = mongoose.model('Image', imageSchema);

// REGISTER Route
app.post('/register', async (req, res) => {
    try {
        const { username, password } = req.body;
        if (!username || !password) {
            return res.status(400).json({ message: 'Username and password are required' });
        }

        const existingUser = await User.findOne({ username });
        if (existingUser) return res.status(400).json({ message: 'Username already exists' });

        // Hash password with salting
        const salt = await bcrypt.genSalt(10);
        const hashedPassword = await bcrypt.hash(password, salt);

        const newUser = new User({ username, password: hashedPassword });
        await newUser.save();
        res.status(201).json({ message: 'User registered successfully' });
    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Server Error' });
    }
});

// LOGIN Route
app.post('/login', async (req, res) => {
    try {
        const { username, password } = req.body;
        if (!username || !password) {
            return res.status(400).json({ message: 'Username and password are required' });
        }

        const user = await User.findOne({ username });
        if (!user) return res.status(400).json({ message: 'Invalid username or password' });

        // Compare hashed password
        const isMatch = await bcrypt.compare(password, user.password);
        if (!isMatch) return res.status(400).json({ message: 'Invalid username or password' });

        // Generate JWT Token
        const token = jwt.sign({ userId: user._id }, JWT_SECRET, { expiresIn: '1h' });
        res.json({ token, message: 'Login successful' });
    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Server Error' });
    }
});

// Middleware to protect routes
const authMiddleware = (req, res, next) => {
    const authHeader = req.header('Authorization');
    if (!authHeader) return res.status(401).json({ message: 'Access Denied: No Token Provided' });

    const token = authHeader.split(" ")[1]; // Assuming "Bearer <token>"
    if (!token) return res.status(401).json({ message: 'Access Denied: Malformed Token' });

    try {
        const verified = jwt.verify(token, JWT_SECRET);
        req.user = verified;
        next();
    } catch (err) {
        res.status(401).json({ message: 'Invalid Token' });
    }
};

// GET /gallery - Retrieve all images for the authenticated user
app.get('/gallery', authMiddleware, async (req, res) => {
    try {
        const images = await Image.find({ user: req.user.userId }).sort({ createdAt: -1 });
        res.json({ images });
    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Server Error' });
    }
});

// GET /score - Retrieve the current score for the authenticated user
app.get('/score', authMiddleware, async (req, res) => {
    try {
        const user = await User.findById(req.user.userId).select('score');
        if (!user) return res.status(404).json({ message: 'User not found' });
        res.json({ score: user.score });
    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Server Error' });
    }
});

// POST /score - Update the score for the authenticated user
app.post('/score', authMiddleware, async (req, res) => {
    try {
        const { score } = req.body;
        
        // Validate the score
        if (typeof score !== 'number') {
            return res.status(400).json({ message: 'Score must be a number' });
        }
        
        // Update the user's score
        const user = await User.findByIdAndUpdate(
            req.user.userId,
            { score },
            { new: true, runValidators: true }
        ).select('score');
        
        if (!user) return res.status(404).json({ message: 'User not found' });
        
        res.json({ score: user.score });
    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Server Error' });
    }
});

// POST /upload - Upload an image as a Base64 encoded string
app.post('/upload', authMiddleware, async (req, res) => {
    try {
        const { title, image } = req.body; // Expecting 'image' to be a Base64 string with MIME type

        if (!image) {
            return res.status(400).json({ message: 'Image data is required' });
        }

        // Validate Base64 string format
        const matches = image.match(/^data:(image\/\w+);base64,(.+)$/);
        if (!matches || matches.length !== 3) {
            return res.status(400).json({ message: 'Invalid image format' });
        }

        const contentType = matches[1];
        const data = matches[2];

        // Optionally, you can limit the size of the Base64 string to prevent excessive data storage
        const buffer = Buffer.from(data, 'base64');
        const fileSizeInMB = buffer.length / (1024 * 1024);
        if (fileSizeInMB > 5) { // Example: limit to 5MB
            return res.status(400).json({ message: 'Image size exceeds 5MB limit' });
        }

        const newImage = new Image({
            user: req.user.userId,
            title: title || 'Untitled',
            data: data,
            contentType
        });

        await newImage.save();
        res.status(201).json({ message: 'Image uploaded successfully', image: newImage });
    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Server Error' });
    }
});

// Start Server
app.listen(PORT, () => console.log(`Server running on port ${PORT} 🚀`));

module.exports = app;
