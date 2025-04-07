// app/static/js/session.js
// Tiempo de la sesión en milisegundos (15 minutos)
const sessionLifetime = 15 * 60 * 1000;
// Tiempo para mostrar la advertencia (por ejemplo, a los 14 minutos)
const warningTime = 14 * 60 * 1000;

setTimeout(function() {
    if (confirm("Tu sesión expirará en 1 minuto. ¿Deseas continuar conectado?")) {
        // Llama a la ruta keepalive para renovar la sesión
        fetch(sessionKeepaliveUrl)
            .then(response => {
                if(response.ok){
                    location.reload();
                }
            });
    } else {
        window.location.href = sessionLogoutUrl;
    }
}, warningTime);
