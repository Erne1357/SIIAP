// Tiempo total para la sesión (solo para pruebas, puedes ajustarlo para producción)
const warningTime = 1 * 60 * 1000;  // Tiempo para mostrar el modal (1 minuto)
const autoLogoutDelay = 1 * 60 * 1000; // Tiempo adicional (1 minuto) para auto-logout

let autoLogoutTimer;  // Referencia para el timer del auto-logout

function showSessionModal() {
    let modal = document.getElementById('sessionModal');
    if (modal) {
        modal.style.display = 'flex';
        // Inicia el timer para auto-logout
        autoLogoutTimer = setTimeout(function(){
            window.location.href = sessionLogoutUrl;
        }, autoLogoutDelay);
    }
}

function hideSessionModal() {
    let modal = document.getElementById('sessionModal');
    if (modal) {
        modal.style.display = 'none';
    }
    // Cancelar el timer de auto logout si se toma acción
    clearTimeout(autoLogoutTimer);
}

document.addEventListener('DOMContentLoaded', function() {
    const continueBtn = document.getElementById('continueBtn');
    const logoutBtn = document.getElementById('logoutBtn');

    if (continueBtn) {
        continueBtn.addEventListener('click', function() {
            // Cancelar auto logout al hacer clic en "Continuar"
            hideSessionModal();
            fetch(sessionKeepaliveUrl, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            })
            .then(response => {
                if (response.ok){
                    location.reload(); // Se actualiza la marca de actividad y se oculta el modal
                }
            })
            .catch(err => {
                console.error("Error en keepalive:", err);
            });
        });
    }

    if (logoutBtn) {
        logoutBtn.addEventListener('click', function() {
            // Cancelar auto logout y redirigir inmediatamente
            hideSessionModal();
            window.location.href = sessionLogoutUrl;
        });
    }

    // Programa la aparición del modal tras warningTime
    setTimeout(function() {
        showSessionModal();
    }, warningTime);
});
