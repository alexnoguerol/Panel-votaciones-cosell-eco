const express = require('express');
const fetch = require('node-fetch');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';
const DEFAULT_THEME = {
  primary: '#0ea5e9',
  secondary: '#64748b',
  topbar: '#64748b',
  accent: '#22c55e'
};

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

app.use(express.static(path.join(__dirname, 'public')));

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

app.use(async (req, res, next) => {
  res.locals.backend = BACKEND_URL;
  try {
    const resp = await fetch(`${BACKEND_URL}/ajustes/theming`);
    if (!resp.ok) throw new Error('bad status');
    res.locals.theme = await resp.json();
  } catch (err) {
    res.locals.theme = DEFAULT_THEME;
  }
  next();
});

app.get('/', (req, res) => {
  res.redirect('/login');
});

app.get('/login', (req, res) => {
  res.render('login');
});

app.get('/dashboard', (req, res) => {
  res.render('dashboard');
});

app.get('/asistencias', (req, res) => {
  res.render('asistencias');
});

// Página de participantes de una actividad de asistencia
app.get('/asistencias/:id/participantes', (req, res) => {
  res.render('participantes', { actividadId: req.params.id });
});

app.post('/api/request-otp', async (req, res) => {
  try {
    const resp = await fetch(`${BACKEND_URL}/auth/otp/request`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: req.body.email })
    });
    const data = await resp.json();
    res.status(resp.status).json(data);
  } catch (err) {
    res.status(500).json({ detail: 'Error de conexión con backend' });
  }
});

app.post('/api/verify-otp', async (req, res) => {
  try {
    const resp = await fetch(`${BACKEND_URL}/auth/otp/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: req.body.email, otp: req.body.otp })
    });
    const data = await resp.json();
    res.status(resp.status).json(data);
  } catch (err) {
    res.status(500).json({ detail: 'Error de conexión con backend' });
  }
});

app.listen(PORT, () => {
  console.log(`Frontend server running on http://localhost:${PORT}`);
});
