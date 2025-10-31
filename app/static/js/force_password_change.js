// app/static/js/force_password_change.js
/**
 * Gestiona el modal de cambio de contraseña obligatorio
 * Se muestra cuando el usuario tiene must_change_password=true
 */

(function() {
    'use strict';

    // Función para obtener el CSRF token
    const getCsrf = () => {
        const el = document.querySelector('meta[name="csrf-token"]');
        return el ? el.getAttribute('content') : '';
    };

    // Función para mostrar mensajes flash desde JS
    const showFlash = (level, message) => {
        window.dispatchEvent(new CustomEvent('flash', {
            detail: { level, message }
        }));
    };

    // Clase principal para manejar el cambio de contraseña
    class ForcePasswordChange {
        constructor() {
            this.modal = null;
            this.form = null;
            this.submitBtn = null;
            this.isSubmitting = false;
            
            this.init();
        }

        init() {
            // Verificar si el usuario debe cambiar contraseña
            this.checkPasswordChangeRequired();
        }

        async checkPasswordChangeRequired() {
            try {
                const response = await fetch('/api/v1/auth/me', {
                    method: 'GET',
                    credentials: 'same-origin',
                    headers: {
                        'X-CSRF-Token': getCsrf()
                    }
                });

                const json = await response.json();
                
                if (json.data && json.data.must_change_password === true) {
                    this.showModal();
                }
            } catch (error) {
                console.error('Error verificando estado de contraseña:', error);
            }
        }

        showModal() {
            const modalElement = document.getElementById('forcePasswordChangeModal');
            
            if (!modalElement) {
                console.error('Modal de cambio de contraseña no encontrado');
                return;
            }

            this.modal = new bootstrap.Modal(modalElement, {
                backdrop: 'static',
                keyboard: false
            });

            this.form = document.getElementById('forcePasswordChangeForm');
            this.submitBtn = document.getElementById('btnChangePassword');

            if (this.form) {
                this.form.addEventListener('submit', (e) => this.handleSubmit(e));
                
                // Validación en tiempo real
                const newPassword = document.getElementById('new_password');
                const confirmPassword = document.getElementById('confirm_password');
                
                if (newPassword) {
                    newPassword.addEventListener('input', () => this.validatePasswordStrength());
                }
                
                if (confirmPassword) {
                    confirmPassword.addEventListener('input', () => this.validatePasswordMatch());
                }
            }

            this.modal.show();
        }

        validatePasswordStrength() {
            const password = document.getElementById('new_password')?.value || '';
            const feedback = document.getElementById('password_strength_feedback');
            
            if (!feedback) return true;

            const requirements = {
                length: password.length >= 8,
                uppercase: /[A-Z]/.test(password),
                lowercase: /[a-z]/.test(password),
                number: /\d/.test(password),
                special: /[!@#$%^&*(),.?":{}|<>]/.test(password)
            };

            const allValid = Object.values(requirements).every(v => v);

            // Actualizar indicadores visuales
            feedback.innerHTML = `
                <div class="small ${allValid ? 'text-success' : 'text-muted'}">
                    <strong>Requisitos de contraseña:</strong>
                    <ul class="mb-0 mt-1">
                        <li class="${requirements.length ? 'text-success' : ''}">
                            ${requirements.length ? '✓' : '○'} Mínimo 8 caracteres
                        </li>
                        <li class="${requirements.uppercase ? 'text-success' : ''}">
                            ${requirements.uppercase ? '✓' : '○'} Una letra mayúscula
                        </li>
                        <li class="${requirements.lowercase ? 'text-success' : ''}">
                            ${requirements.lowercase ? '✓' : '○'} Una letra minúscula
                        </li>
                        <li class="${requirements.number ? 'text-success' : ''}">
                            ${requirements.number ? '✓' : '○'} Un número
                        </li>
                        <li class="${requirements.special ? 'text-success' : ''}">
                            ${requirements.special ? '✓' : '○'} Un caracter especial
                        </li>
                    </ul>
                </div>
            `;

            return allValid;
        }

        validatePasswordMatch() {
            const newPassword = document.getElementById('new_password')?.value || '';
            const confirmPassword = document.getElementById('confirm_password')?.value || '';
            const feedback = document.getElementById('password_match_feedback');

            if (!feedback) return true;

            if (confirmPassword.length === 0) {
                feedback.textContent = '';
                return false;
            }

            if (newPassword === confirmPassword) {
                feedback.textContent = '✓ Las contraseñas coinciden';
                feedback.className = 'small text-success mt-1';
                return true;
            } else {
                feedback.textContent = '✗ Las contraseñas no coinciden';
                feedback.className = 'small text-danger mt-1';
                return false;
            }
        }

        async handleSubmit(e) {
            e.preventDefault();

            if (this.isSubmitting) return;

            // Validar antes de enviar
            if (!this.validatePasswordStrength()) {
                showFlash('danger', 'La contraseña no cumple con los requisitos de seguridad');
                return;
            }

            if (!this.validatePasswordMatch()) {
                showFlash('danger', 'Las contraseñas no coinciden');
                return;
            }

            this.isSubmitting = true;
            this.submitBtn.disabled = true;
            this.submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Cambiando...';

            const formData = new FormData(this.form);
            const data = {
                current_password: formData.get('current_password'),
                new_password: formData.get('new_password'),
                confirm_password: formData.get('confirm_password')
            };

            try {
                const response = await fetch('/api/v1/auth/change-password', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': getCsrf()
                    },
                    body: JSON.stringify(data)
                });

                const json = await response.json();

                // Mostrar mensajes flash
                if (json.flash && Array.isArray(json.flash)) {
                    json.flash.forEach(f => showFlash(f.level, f.message));
                }

                if (response.ok) {
                    // Contraseña cambiada exitosamente
                    this.modal.hide();
                    
                    // Recargar página después de 1 segundo para aplicar cambios
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000);
                } else {
                    // Error al cambiar contraseña
                    this.isSubmitting = false;
                    this.submitBtn.disabled = false;
                    this.submitBtn.textContent = 'Cambiar Contraseña';
                }
            } catch (error) {
                console.error('Error al cambiar contraseña:', error);
                showFlash('danger', 'Error al cambiar la contraseña. Intenta de nuevo.');
                
                this.isSubmitting = false;
                this.submitBtn.disabled = false;
                this.submitBtn.textContent = 'Cambiar Contraseña';
            }
        }
    }

    // Inicializar cuando el DOM esté listo
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            new ForcePasswordChange();
        });
    } else {
        new ForcePasswordChange();
    }

    // Reinicializar después de Swup si está presente
    if (typeof swup !== 'undefined') {
        swup.on('contentReplaced', () => {
            new ForcePasswordChange();
        });
    }
})();

function togglePasswordVisibility(fieldId) {
    const field = document.getElementById(fieldId);
    const icon = document.getElementById(fieldId + '_icon');
    
    if (field.type === 'password') {
        field.type = 'text';
        icon.classList.remove('bi-eye');
        icon.classList.add('bi-eye-slash');
    } else {
        field.type = 'password';
        icon.classList.remove('bi-eye-slash');
        icon.classList.add('bi-eye');
    }
}