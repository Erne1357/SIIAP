// app/static/js/utils/api.js

/**
 * Utilitarios para hacer peticiones API de forma consistente
 */

class ApiClient {
    constructor() {
        this.baseUrl = `${window.location.protocol}//${window.location.host}`;
    }

    /**
     * Construye una URL absoluta desde una ruta relativa
     * @param {string} path - Ruta relativa (ej: '/api/v1/notifications')
     * @returns {string} URL absoluta
     */
    url(path) {
        // Remover slash inicial si existe para evitar doble slash
        const cleanPath = path.startsWith('/') ? path.slice(1) : path;
        return `${this.baseUrl}/${cleanPath}`;
    }

    /**
     * Obtiene el token CSRF actual
     * @returns {string} Token CSRF
     */
    getCsrf() {
        const el = document.querySelector('meta[name="csrf-token"]');
        return el ? el.getAttribute('content') : '';
    }

    /**
     * Headers por defecto para peticiones
     * @returns {Object} Headers
     */
    getDefaultHeaders() {
        return {
            'X-CSRF-Token': this.getCsrf(),
            'X-Requested-With': 'XMLHttpRequest'
        };
    }

    /**
     * Realiza una petición GET
     * @param {string} path - Ruta de la API
     * @param {Object} options - Opciones adicionales de fetch
     * @returns {Promise<Response>}
     */
    async get(path, options = {}) {
        return fetch(this.url(path), {
            method: 'GET',
            credentials: 'same-origin',
            headers: {
                ...this.getDefaultHeaders(),
                ...options.headers
            },
            ...options
        });
    }

    /**
     * Realiza una petición POST
     * @param {string} path - Ruta de la API
     * @param {Object} data - Datos a enviar
     * @param {Object} options - Opciones adicionales
     * @returns {Promise<Response>}
     */
    async post(path, data = null, options = {}) {
        const headers = { ...this.getDefaultHeaders() };
        let body = data;

        if (data && !(data instanceof FormData)) {
            headers['Content-Type'] = 'application/json';
            body = JSON.stringify(data);
        }

        return fetch(this.url(path), {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                ...headers,
                ...options.headers
            },
            body,
            ...options
        });
    }

    /**
     * Realiza una petición PATCH
     * @param {string} path - Ruta de la API
     * @param {Object} data - Datos a enviar
     * @param {Object} options - Opciones adicionales
     * @returns {Promise<Response>}
     */
    async patch(path, data = null, options = {}) {
        const headers = { ...this.getDefaultHeaders() };
        let body = data;

        if (data && !(data instanceof FormData)) {
            headers['Content-Type'] = 'application/json';
            body = JSON.stringify(data);
        }

        return fetch(this.url(path), {
            method: 'PATCH',
            credentials: 'same-origin',
            headers: {
                ...headers,
                ...options.headers
            },
            body,
            ...options
        });
    }

    /**
     * Realiza una petición DELETE
     * @param {string} path - Ruta de la API
     * @param {Object} options - Opciones adicionales
     * @returns {Promise<Response>}
     */
    async delete(path, options = {}) {
        return fetch(this.url(path), {
            method: 'DELETE',
            credentials: 'same-origin',
            headers: {
                ...this.getDefaultHeaders(),
                ...options.headers
            },
            ...options
        });
    }
}

// Instancia global
window.apiClient = new ApiClient();

// Para compatibilidad con código existente, exportar también funciones individuales
window.getApiUrl = (path) => window.apiClient.url(path);
window.getCsrfToken = () => window.apiClient.getCsrf();