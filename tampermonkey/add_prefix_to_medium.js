// ==UserScript==
// @name         Add Prefix to Medium URLs
// @namespace    http://tampermonkey.net/
// @version      0.1
// @description  Add "12ft.io/" prefix to Medium URLs
// @author       volteret4
// @downloadURL
// @updateURL
// @match        https://medium.com/*
// @match        https://*.medium.com
// @match        https://lavozdigital.es/*
// @match        https://www.elconfidencial.com/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // Obtener la URL actual
    var currentUrl = window.location.href;

    // Verificar si la URL ya contiene el prefijo "12ft.io/"
    if (!currentUrl.startsWith("https://12ft.io/")) {
        // Construir la nueva URL con el prefijo "12ft.io/"
        var newUrl = "https://12ft.io/" + currentUrl;

        // Redirigir a la nueva URL
        window.location.href = newUrl;
    }
})();