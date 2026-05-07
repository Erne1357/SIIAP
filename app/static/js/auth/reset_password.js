(() => {
  'use strict';

  const TOKEN = window.SIIAP_RESET_TOKEN;

  const subtitle = document.getElementById('resetSubtitle');
  const invalid = document.getElementById('resetTokenInvalid');
  const invalidTitle = document.getElementById('resetInvalidTitle');
  const invalidDesc = document.getElementById('resetInvalidDesc');
  const form = document.getElementById('resetPasswordForm');
  const newPw = document.getElementById('newPassword');
  const confirmPw = document.getElementById('confirmPassword');
  const mismatch = document.getElementById('resetMismatch');
  const submitBtn = document.getElementById('resetSubmitBtn');

  // Toggle de visibilidad de password
  function bindToggle(btnId, inputEl) {
    const btn = document.getElementById(btnId);
    if (!btn || !inputEl) return;
    btn.addEventListener('click', () => {
      const isText = inputEl.type === 'text';
      inputEl.type = isText ? 'password' : 'text';
      const icon = btn.querySelector('i');
      if (icon) icon.className = isText ? 'bi bi-eye' : 'bi bi-eye-slash';
    });
  }
  bindToggle('togglePw1', newPw);
  bindToggle('togglePw2', confirmPw);

  function showInvalid(title, desc) {
    invalid.classList.remove('d-none');
    invalidTitle.textContent = title;
    invalidDesc.textContent = desc;
    subtitle.textContent = desc;
    form.classList.add('d-none');
  }

  function showFlash(level, message) {
    if (window.showFlash) window.showFlash(level, message);
  }

  // Verificar token al cargar
  async function verifyToken() {
    if (!TOKEN) {
      showInvalid('Enlace inválido', 'No se proporcionó un token. Verifica que abriste el enlace completo enviado por correo.');
      return;
    }
    try {
      const res = await fetch(`/api/v1/auth/reset-password/${encodeURIComponent(TOKEN)}/info`);
      const json = await res.json();
      if (!res.ok || json.error) {
        const code = json.error?.code || 'TOKEN_NOT_FOUND';
        const map = {
          TOKEN_NOT_FOUND: ['Enlace inválido', 'El enlace no es válido o ya no existe.'],
          TOKEN_EXPIRED: ['Enlace expirado', 'Este enlace ha expirado. Contacta al administrador para uno nuevo.'],
          TOKEN_USED: ['Enlace ya utilizado', 'Este enlace ya fue utilizado para establecer una contraseña. Inicia sesión normalmente.'],
        };
        const [title, desc] = map[code] || ['Enlace no disponible', json.error?.message || 'No fue posible validar el enlace.'];
        showInvalid(title, desc);
        return;
      }
      const data = json.data;
      subtitle.textContent = `Hola, ${data.first_name}. Configura tu contraseña para iniciar sesión como ${data.username}.`;
      form.classList.remove('d-none');
    } catch (e) {
      showInvalid('Error de conexión', 'No se pudo verificar el enlace. Verifica tu conexión a internet e intenta de nuevo.');
    }
  }

  function passwordsMatch() {
    return newPw.value && newPw.value === confirmPw.value;
  }

  function updateMismatchHint() {
    if (confirmPw.value && !passwordsMatch()) {
      mismatch.classList.remove('d-none');
    } else {
      mismatch.classList.add('d-none');
    }
  }

  newPw.addEventListener('input', updateMismatchHint);
  confirmPw.addEventListener('input', updateMismatchHint);

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!TOKEN) {
      showInvalid('Enlace inválido', 'No se proporcionó un token.');
      return;
    }
    if (!passwordsMatch()) {
      showFlash('warning', 'Las contraseñas no coinciden.');
      return;
    }
    submitBtn.disabled = true;
    const originalLabel = submitBtn.querySelector('.btn-label').textContent;
    submitBtn.querySelector('.btn-label').textContent = 'Estableciendo…';
    try {
      const res = await fetch(`/api/v1/auth/reset-password/${encodeURIComponent(TOKEN)}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          new_password: newPw.value,
          confirm_password: confirmPw.value,
        }),
      });
      const json = await res.json();
      (json.flash || []).forEach(f => showFlash(f.level, f.message));
      if (res.ok && !json.error) {
        // Redirigir a login
        setTimeout(() => { window.location.href = '/login'; }, 1200);
        return;
      }
      // Si token ya no es válido, mostrar pantalla de error
      const code = json.error?.code;
      if (['TOKEN_NOT_FOUND', 'TOKEN_EXPIRED', 'TOKEN_USED'].includes(code)) {
        showInvalid('Enlace no disponible', json.error?.message || 'El enlace ya no es válido.');
      }
    } catch (err) {
      showFlash('danger', `Error de conexión: ${err.message}`);
    } finally {
      submitBtn.disabled = false;
      submitBtn.querySelector('.btn-label').textContent = originalLabel;
    }
  });

  // Iniciar
  verifyToken();
})();
