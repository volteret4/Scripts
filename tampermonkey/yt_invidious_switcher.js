// ==UserScript==
// @name         YouTube/Invidious Switcher
// @namespace    http://tampermonkey.net/
// @version      0.1
// @description  Add switch button between YouTube and Invidious for embedded videos
// @author       volteret4
// @downloadURL
// @updateURL
// @match        *://*/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    const invidiousInstance = 'yt.pollete.duckdns.org';

    function createSwitchButton(iframe) {
        const button = document.createElement('button');
        button.innerHTML = 'Switch to YouTube';
        button.style.cssText = `
            position: absolute;
            top: 10px;
            right: 10px;
            z-index: 9999;
            background: rgba(0, 0, 0, 0.7);
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        `;

        // Crear contenedor para el iframe y el botón
        const container = document.createElement('div');
        container.style.position = 'relative';

        // Reemplazar el iframe con nuestro contenedor
        iframe.parentNode.replaceChild(container, iframe);
        container.appendChild(iframe);
        container.appendChild(button);

        let isInvidious = true;
        const originalYouTubeSrc = iframe.src.includes('youtube.com') ?
            iframe.src :
            `https://www.youtube.com/embed/${iframe.src.split('/embed/')[1]}`;
        const invidiousSrc = `https://${invidiousInstance}/embed/${originalYouTubeSrc.split('/embed/')[1]}`;

        button.onclick = function() {
            if (isInvidious) {
                iframe.src = originalYouTubeSrc;
                button.innerHTML = 'Switch to Invidious';
            } else {
                iframe.src = invidiousSrc;
                button.innerHTML = 'Switch to YouTube';
            }
            isInvidious = !isInvidious;
        };
    }

    function processIframes() {
        const iframes = document.getElementsByTagName('iframe');
        for (let iframe of iframes) {
            let src = iframe.src;
            if ((src.includes('youtube.com/embed/') || src.includes('youtube-nocookie.com/embed/')) && !iframe.parentNode.querySelector('button')) {
                const videoId = src.split('/embed/')[1].split('?')[0];
                iframe.src = `https://${invidiousInstance}/embed/${videoId}`;
                createSwitchButton(iframe);
            } else if (src.includes(`${invidiousInstance}/embed/`) && !iframe.parentNode.querySelector('button')) {
                createSwitchButton(iframe);
            }
        }
    }

    // Ejecutar al cargar la página
    processIframes();

    // Observar cambios en el DOM
    const observer = new MutationObserver(function(mutations) {
        processIframes();
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
})();