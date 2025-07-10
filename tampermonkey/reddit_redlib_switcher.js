// ==UserScript==
// @name         Reddit to Redlib Redirect
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Redirige automáticamente Reddit a Redlib
// @author       volteret4
// @match        *://www.reddit.com/*
// @match        *://reddit.com/*
// @match        *://old.reddit.com/*
// @match        *://new.reddit.com/*
// @match        *://np.reddit.com/*
// @match        *://amp.reddit.com/*
// @match        *://i.reddit.com/*
// @grant        none
// @run-at       document-start
// ==/UserScript==

(function() {
    'use strict';

    const REDLIB_INSTANCE = 'redlib.pollete.duckdns.org';

    function redirectToRedlib() {
        const currentUrl = window.location.href;
        const currentHost = window.location.host;

        // Verificar si estamos en algún dominio de Reddit
        if (currentHost.includes('reddit.com')) {
            // Obtener el path actual (todo después del dominio)
            const path = window.location.pathname + window.location.search + window.location.hash;

            // Construir la nueva URL con Redlib
            const newUrl = `https://${REDLIB_INSTANCE}${path}`;

            console.log(`Redirigiendo de ${currentUrl} a ${newUrl}`);

            // Realizar la redirección
            window.location.replace(newUrl);
        }
    }

    // Ejecutar la redirección inmediatamente
    redirectToRedlib();

    // También verificar si la URL cambia dinámicamente (por si acaso)
    let lastUrl = location.href;
    new MutationObserver(() => {
        const url = location.href;
        if (url !== lastUrl) {
            lastUrl = url;
            redirectToRedlib();
        }
    }).observe(document, {subtree: true, childList: true});

})();