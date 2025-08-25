const express = require('express');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

// Default settings for the frontend views
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';
const DEFAULT_THEME = {
  primary: '#ffffff',
  secondary: '#1e90ff',
  topbar: '#343a40',
  accent: '#ffc107'
};

// Configure view engine
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Expose shared template variables
app.use((req, res, next) => {
  res.locals.backend = BACKEND_URL;
  res.locals.theme = DEFAULT_THEME;
  next();
});

// Serve static assets
app.use(express.static(path.join(__dirname, 'public')));

// Routes
app.get('/', (req, res) => {
  res.redirect('/login');
});

app.get('/login', (req, res) => {
  res.render('login');
});

app.get('/dashboard', (req, res) => {
  res.render('dashboard');
});

app.get('/participantes', (req, res) => {
  res.render('participantes');
});

app.get('/asistencias', (req, res) => {
  res.render('asistencias');
});

app.listen(PORT, () => {
  console.log(`Frontend server running on http://localhost:${PORT}`);
});
