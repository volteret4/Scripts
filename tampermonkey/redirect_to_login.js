// ==UserScript==
// @name         Auto Redirect to Login (One-Time)
// @namespace    http://tampermonkey.net/
// @version      1.1
// @description  Redirige al login automáticamente si no estás logueado en ciertos sitios web, pero solo una vez por sesión.
// @author       volteret4
// @match        https://www.last.fm/*
// @match        https://github.com/*
// @match        https://chat.openai.com/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // Definir las reglas de redirección para cada sitio
    const rules = [
        {
            site: 'last.fm',
            check: () => !document.querySelector('.auth-link'), // Si no hay enlace de login
            redirect: 'https://www.last.fm/login'
        },
        {
            site: 'github.com',
            check: () => !document.querySelector('header nav a[href="/logout"]'), // Si no aparece el enlace de logout
            redirect: 'https://github.com/login'
        },
        {
            site: 'chat.openai.com',
            check: () => document.body.innerText.includes('Log in') || document.body.innerText.includes('Sign up'), // Detectar textos típicos de no estar logueado
            redirect: 'https://chat.openai.com/auth/login'
        }
    ];

    // Obtener la URL actual
    const currentURL = window.location.href;

    // Revisar si la redirección ya se realizó en esta sesión
    const redirectedKey = 'redirectedToLogin';
    const redirectedSites = JSON.parse(localStorage.getItem(redirectedKey)) || {};

    for (const rule of rules) {
        if (currentURL.includes(rule.site)) {
            // Si no está logueado y no se ha redirigido antes
            if (rule.check() && !redirectedSites[rule.site]) {
                redirectedSites[rule.site] = true; // Marcar como redirigido
                localStorage.setItem(redirectedKey, JSON.stringify(redirectedSites)); // Guardar en localStorage
                window.location.href = rule.redirect; // Redirigir
                break;
            }
        }
    }
})();
