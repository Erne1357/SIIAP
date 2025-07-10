// Solo inicia la lógica si el usuario está autenticado.
if (userLoggedIn !== 'true') {
    // Si no hay usuario, salimos sin programar el temporizador.
    console.log("No hay sesión activa, no se inicia el temporizador de sesión.");
} else {
    // Tiempo para mostrar la advertencia (por ejemplo, 1 minuto para este ejemplo)
    console.log("Usuario autenticado, se inicia el temporizador de sesión.");
    const warningTime = 15 * 60 * 1000;
    const autoLogoutDelay = 1 * 60 * 1000; // tiempo adicional para auto logout
    let autoLogoutTimer;

    function showSessionModal() {
        let modal = document.getElementById('sessionModal');
        console.log("Modal de sesión:", modal);
        if (modal) {
            modal.style.display = 'flex';
            console.log("Mostrando modal de sesión.");
            // Inicia el timer para auto-logout
            autoLogoutTimer = setTimeout(function(){
                window.location.href = sessionLogoutUrl + '?expired=1';
            }, autoLogoutDelay);
        }
    }

    function hideSessionModal() {
        let modal = document.getElementById('sessionModal');
        if (modal) {
            modal.style.display = 'none';
        }
        clearTimeout(autoLogoutTimer);
    }

    document.addEventListener('DOMContentLoaded', function() {
        const continueBtn = document.getElementById('continueBtn');
        const logoutBtn = document.getElementById('logoutBtn');

        if (continueBtn) {
            continueBtn.addEventListener('click', function() {
                hideSessionModal();
                fetch(sessionKeepaliveUrl, {
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                })
                .then(response => {
                    if (response.ok){
                        location.reload();
                    }
                })
                .catch(err => {
                    console.error("Error en keepalive:", err);
                });
            });
        }

        if (logoutBtn) {
            logoutBtn.addEventListener('click', function() {
                hideSessionModal();
                window.location.href = sessionLogoutUrl + '?expired=1';
            });
        }

        // Programa la aparición del modal tras warningTime
        setTimeout(function() {
            showSessionModal();
        }, warningTime);
    });
}

function random(){
    numero =  Math.floor(Math.random() * 100) + 1;
    if(numero === 6){
        alert("Si quieres conocer los secretos del Tec, entra al dashboard y resuelve el acertijo");
    }
}
