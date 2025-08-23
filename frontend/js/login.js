const API = 'http://localhost:8000';   // ajusta el puerto si es otro

async function loadTheming() {
  try {
    const resp = await fetch(`${API}/ajustes/theming`);
    if (resp.ok) {
      const data = await resp.json();
      const root = document.documentElement;
      if (data.primary) root.style.setProperty('--primary', data.primary);
      if (data.secondary) root.style.setProperty('--secondary', data.secondary);
      if (data.accent) root.style.setProperty('--accent', data.accent);
    }
  } catch (err) {
    console.warn('No theming settings', err);
  }
}

async function loadLogo() {
  const logo = document.getElementById('logo');
  try {
    const resp = await fetch(`${API}/ajustes/logo`);
    if (resp.ok) {
      const blob = await resp.blob();
      logo.src = URL.createObjectURL(blob);
    } else {
      logo.src = 'img/default-logo.svg';
    }
  } catch (err) {
    logo.src = 'img/default-logo.svg';
  }
}

async function requestOtp() {
  const email = document.getElementById('email').value.trim();
  const msg = document.getElementById('message');
  msg.textContent = '';
  try {
    const resp = await fetch(`${API}/auth/otp/request`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    if (resp.ok) {
      const data = await resp.json();
      msg.textContent = data.message || 'Código enviado';
      document.getElementById('email-step').classList.add('hidden');
      document.getElementById('otp-step').classList.remove('hidden');
    } else {
      const data = await resp.json().catch(() => ({}));
      msg.textContent = data.detail || 'Error al solicitar código';
    }
  } catch (err) {
    msg.textContent = 'Error de red';
  }
}

async function verifyOtp() {
  const email = document.getElementById('email').value.trim();
  const otp = document.getElementById('otp').value.trim();
  const msg = document.getElementById('message');
  msg.textContent = '';
  try {
    const resp = await fetch(`${API}/auth/otp/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, otp })
    });
    if (resp.ok) {
      const data = await resp.json();
      msg.textContent = data.message || 'Acceso concedido';
      localStorage.setItem('access_token', data.access_token);
    } else {
      const data = await resp.json().catch(() => ({}));
      msg.textContent = data.detail || 'Error al verificar código';
    }
  } catch (err) {
    msg.textContent = 'Error de red';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadTheming();
  loadLogo();
  document.getElementById('request-otp').addEventListener('click', requestOtp);
  document.getElementById('verify-otp').addEventListener('click', verifyOtp);
});
