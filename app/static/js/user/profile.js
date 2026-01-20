// app/static/js/user/profile.js - Versión actualizada
document.addEventListener('DOMContentLoaded', () => {
  const profileForm = document.querySelector('form[data-profile-update="true"]');
  const completeProfileForm = document.querySelector('form[data-complete-profile="true"]');

  const getCsrf = () => {
    const el = document.querySelector('meta[name="csrf-token"]');
    return el ? el.getAttribute('content') : '';
  };
  const csrf = getCsrf();

  function emitFlash(level, message) {
    window.dispatchEvent(new CustomEvent('flash', { detail: { level, message } }));
  }
  
  function persistFlashes(flashes) {
    try {
      sessionStorage.setItem('flashQueue', JSON.stringify(flashes || []));
    } catch (_) {}
  }

  // ========== FORMULARIO BÁSICO DE PERFIL ==========
  if (profileForm) {
    profileForm.addEventListener('submit', async (e) => {
      e.preventDefault();

      const payload = {
        first_name: profileForm.first_name.value.trim(),
        last_name: profileForm.last_name.value.trim(),
        mother_last_name: profileForm.mother_last_name.value.trim()
      };

      try {
        const res = await fetch('/api/v1/users/me', {
          method: 'PATCH',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrf
          },
          body: JSON.stringify(payload)
        });

        const json = await res.json().catch(() => ({}));

        if (!res.ok) {
          const msg = json?.error?.message || 'No se pudo actualizar el perfil.';
          if (Array.isArray(json.flash) && json.flash.length) {
            json.flash.forEach(f => emitFlash(f.level || 'danger', f.message || msg));
          } else {
            emitFlash('danger', msg);
          }
          return;
        }

        // Cerrar modal
        const modalEl = document.getElementById('editProfileModal');
        if (modalEl) {
          let inst = bootstrap.Modal.getInstance(modalEl);
          if (!inst) inst = new bootstrap.Modal(modalEl);
          inst.hide();
        }

        const flashes = Array.isArray(json.flash) && json.flash.length
          ? json.flash
          : [{ level: 'success', message: 'Perfil actualizado correctamente.' }];

        persistFlashes(flashes);
        window.location.reload();

      } catch (err) {
        console.error('profile update error:', err);
        emitFlash('danger', 'Error de red al actualizar el perfil.');
      }
    });
  }

  // ========== FORMULARIO DE COMPLETAR PERFIL ==========
  if (completeProfileForm) {
    completeProfileForm.addEventListener('submit', async (e) => {
      e.preventDefault();

      const formData = new FormData(completeProfileForm);
      const payload = {
        phone: formData.get('phone')?.trim(),
        mobile_phone: formData.get('mobile_phone')?.trim(),
        address: formData.get('address')?.trim(),
        curp: formData.get('curp')?.trim(),
        rfc: formData.get('rfc')?.trim(),
        birth_date: formData.get('birth_date'),
        birth_place: formData.get('birth_place')?.trim(),
        cedula_profesional: formData.get('cedula_profesional')?.trim(),
        nss: formData.get('nss')?.trim(),
        emergency_contact_name: formData.get('emergency_contact_name')?.trim(),
        emergency_contact_phone: formData.get('emergency_contact_phone')?.trim(),
        emergency_contact_relationship: formData.get('emergency_contact_relationship')
      };

      // Validaciones básicas
      if (!payload.phone && !payload.mobile_phone) {
        emitFlash('warning', 'Debes proporcionar al menos un número de teléfono.');
        return;
      }

      if (!payload.emergency_contact_name || !payload.emergency_contact_phone || !payload.emergency_contact_relationship) {
        emitFlash('warning', 'La información de contacto de emergencia es obligatoria.');
        return;
      }

      // Mostrar loading
      const submitBtn = completeProfileForm.querySelector('button[type="submit"]');
      const originalText = submitBtn.innerHTML;
      submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Guardando...';
      submitBtn.disabled = true;

      try {
        const res = await fetch('/api/v1/users/me/complete-profile', {
          method: 'PATCH',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrf
          },
          body: JSON.stringify(payload)
        });

        const json = await res.json().catch(() => ({}));

        if (!res.ok) {
          const msg = json?.error?.message || 'No se pudo guardar la información.';
          if (Array.isArray(json.flash) && json.flash.length) {
            json.flash.forEach(f => emitFlash(f.level || 'danger', f.message || msg));
          } else {
            emitFlash('danger', msg);
          }
          return;
        }

        // Cerrar modal
        const modalEl = document.getElementById('completeProfileModal');
        if (modalEl) {
          let inst = bootstrap.Modal.getInstance(modalEl);
          if (!inst) inst = new bootstrap.Modal(modalEl);
          inst.hide();
        }

        const flashes = Array.isArray(json.flash) && json.flash.length
          ? json.flash
          : [{ level: 'success', message: 'Información guardada correctamente.' }];

        // Si acaba de completar el perfil, mostrar mensaje especial
        if (json.data?.newly_completed) {
          flashes.push({ 
            level: 'info', 
            message: '¡Felicidades! Tu perfil está completo y ahora eres elegible para entrevistas.' 
          });
        }

        persistFlashes(flashes);
        window.location.reload();

      } catch (err) {
        console.error('complete profile error:', err);
        emitFlash('danger', 'Error de red al guardar la información.');
      } finally {
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
      }
    });
  }

  // ========== CARGAR ESTADO DE COMPLETITUD DEL PERFIL ==========
  loadProfileCompletionStatus();

  async function loadProfileCompletionStatus() {
    try {
      const res = await fetch('/api/v1/users/me/profile-completion', {
        credentials: 'same-origin'
      });

      if (!res.ok) return;

      const json = await res.json();
      const completion = json.data;

      // Actualizar indicador de completitud en la UI
      updateProfileCompletionUI(completion);

    } catch (err) {
      
    }
  }

  function updateProfileCompletionUI(completion) {
    // Buscar elementos donde mostrar el estado
    const completionBadge = document.querySelector('.profile-completion-badge');
    const completionProgress = document.querySelector('.profile-completion-progress');
    
    if (completionBadge) {
      if (completion.profile_completed) {
        completionBadge.className = 'badge bg-success profile-completion-badge';
        completionBadge.textContent = 'Perfil Completo';
      } else {
        completionBadge.className = 'badge bg-warning profile-completion-badge';
        completionBadge.textContent = `${completion.completion_percentage.toFixed(0)}% Completo`;
      }
    }

    if (completionProgress) {
      completionProgress.style.width = `${completion.completion_percentage}%`;
      completionProgress.setAttribute('aria-valuenow', completion.completion_percentage);
    }

    // Mostrar campos faltantes en consola para debug
    if (completion.missing_fields.length > 0) {
      
    }
  }

  // ========== VALIDACIONES EN TIEMPO REAL ==========
  
  // Validar CURP
  const curpInput = document.getElementById('curp');
  if (curpInput) {
    curpInput.addEventListener('input', (e) => {
      const value = e.target.value.toUpperCase();
      e.target.value = value;
      
      // Validación básica de formato CURP (18 caracteres alfanuméricos)
      if (value.length === 18) {
        const curpRegex = /^[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d$/;
        if (curpRegex.test(value)) {
          e.target.classList.remove('is-invalid');
          e.target.classList.add('is-valid');
        } else {
          e.target.classList.remove('is-valid');
          e.target.classList.add('is-invalid');
        }
      } else {
        e.target.classList.remove('is-valid', 'is-invalid');
      }
    });
  }

  // Validar RFC
  const rfcInput = document.getElementById('rfc');
  if (rfcInput) {
    rfcInput.addEventListener('input', (e) => {
      const value = e.target.value.toUpperCase();
      e.target.value = value;
      
      // Validación básica de formato RFC (12-13 caracteres)
      if (value.length >= 12 && value.length <= 13) {
        const rfcRegex = /^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$/;
        if (rfcRegex.test(value)) {
          e.target.classList.remove('is-invalid');
          e.target.classList.add('is-valid');
        } else {
          e.target.classList.remove('is-valid');
          e.target.classList.add('is-invalid');
        }
      } else {
        e.target.classList.remove('is-valid', 'is-invalid');
      }
    });
  }
});