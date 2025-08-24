const express = require('express');
const fetch = require('node-fetch');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

async function getTheme() {
  try {
    const res = await fetch(`${BACKEND_URL}/ajustes/theming`);
    if (!res.ok) throw new Error('bad status');
    return await res.json();
  } catch (err) {
    return { primary: '#0ea5e9', secondary: '#64748b', topbar: '#64748b', accent: '#22c55e' };
  }
}

app.get('/', async (req, res) => {
  const theme = await getTheme();
  res.render('login', { theme, backend: BACKEND_URL });
});

app.get('/dashboard', async (req, res) => {
  const theme = await getTheme();
  res.render('dashboard', { theme, backend: BACKEND_URL });
});

app.get('/asistencias', async (req, res) => {
  const theme = await getTheme();
  res.render('asistencias', { theme, backend: BACKEND_URL });
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
  console.log(`Frontend running on http://localhost:${PORT}`);
});
