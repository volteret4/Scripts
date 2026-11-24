/**
 * Album Web Generator - JavaScript Global
 * Funcionalidad compartida para todas las páginas de álbumes
 */

// =============================
// NAVEGACIÓN POR PESTAÑAS
// =============================

class TabNavigation {
  constructor() {
    this.activeTab = "comment";
    this.tabs = {};
    this.panels = {};
    this.init();
  }

  init() {
    // Obtener elementos del DOM
    this.tabs = {
      comment: document.querySelector('[data-tab="comment"]'),
      lyrics: document.querySelector('[data-tab="lyrics"]'),
      links: document.querySelector('[data-tab="links"]'),
      tracks: document.querySelector('[data-tab="tracks"]'),
    };

    this.panels = {
      comment: document.getElementById("comment"),
      lyrics: document.getElementById("lyrics"),
      links: document.getElementById("links"),
      tracks: document.getElementById("tracks"),
    };

    // Configurar eventos
    this.bindEvents();

    // Activar pestaña inicial
    this.showTab(this.getActiveTabFromURL() || "comment");
  }

  bindEvents() {
    // Eventos de clic en pestañas
    Object.keys(this.tabs).forEach((tabName) => {
      const tab = this.tabs[tabName];
      if (tab) {
        tab.addEventListener("click", (e) => {
          e.preventDefault();
          this.showTab(tabName);
          this.updateURL(tabName);
        });
      }
    });

    // Navegación con teclado
    document.addEventListener("keydown", (e) => {
      if (e.ctrlKey || e.metaKey) return;

      const tabNames = Object.keys(this.tabs);
      const currentIndex = tabNames.indexOf(this.activeTab);

      switch (e.key) {
        case "ArrowLeft":
          e.preventDefault();
          const prevTab =
            tabNames[currentIndex - 1] || tabNames[tabNames.length - 1];
          this.showTab(prevTab);
          break;
        case "ArrowRight":
          e.preventDefault();
          const nextTab = tabNames[currentIndex + 1] || tabNames[0];
          this.showTab(nextTab);
          break;
      }
    });

    // Eventos de hash change
    window.addEventListener("hashchange", () => {
      const tab = this.getActiveTabFromURL();
      if (tab && tab !== this.activeTab) {
        this.showTab(tab);
      }
    });
  }

  showTab(tabName) {
    if (!this.tabs[tabName] || !this.panels[tabName]) {
      console.warn(`Pestaña no encontrada: ${tabName}`);
      return;
    }

    // Desactivar pestañas actuales
    Object.keys(this.tabs).forEach((name) => {
      const tab = this.tabs[name];
      const panel = this.panels[name];

      if (tab && panel) {
        tab.classList.remove("active");
        panel.classList.remove("active");
      }
    });

    // Activar nueva pestaña
    this.tabs[tabName].classList.add("active");
    this.panels[tabName].classList.add("active");
    this.activeTab = tabName;

    // Ejecutar callback específico de la pestaña
    this.onTabChange(tabName);
  }

  onTabChange(tabName) {
    switch (tabName) {
      case "lyrics":
        this.initializeLyricsFeatures();
        break;
      case "links":
        this.trackLinkClicks();
        break;
      case "tracks":
        this.initializeTracksFeatures();
        break;
    }
  }

  initializeLyricsFeatures() {
    const lyricsContainer = this.panels.lyrics;
    if (!lyricsContainer) return;

    // Agregar funcionalidad de búsqueda en letras
    this.addLyricsSearch();
  }

  trackLinkClicks() {
    const linkItems = this.panels.links?.querySelectorAll(".link-item a");
    if (!linkItems) return;

    linkItems.forEach((link) => {
      link.addEventListener("click", (e) => {
        const linkText = link.textContent.trim();
        console.log(`Enlace clickeado: ${linkText}`);
        // Aquí se podría enviar analytics si fuera necesario
      });
    });
  }

  initializeTracksFeatures() {
    const trackRows = this.panels.tracks?.querySelectorAll(".track-row");
    if (!trackRows) return;

    // Agregar hover effects y funcionalidad adicional
    trackRows.forEach((row, index) => {
      row.addEventListener("mouseenter", () => {
        row.style.transform = "translateX(4px)";
      });

      row.addEventListener("mouseleave", () => {
        row.style.transform = "translateX(0)";
      });
    });
  }

  addLyricsSearch() {
    const lyricsContent = this.panels.lyrics?.querySelector(".lyrics-content");
    if (!lyricsContent) return;

    // Crear barra de búsqueda si no existe
    let searchBar = lyricsContent.querySelector(".lyrics-search");
    if (!searchBar) {
      searchBar = document.createElement("div");
      searchBar.className = "lyrics-search";
      searchBar.innerHTML = `
                <input type="text" placeholder="Buscar en las letras..." class="lyrics-search-input">
                <div class="search-results-count"></div>
            `;
      lyricsContent.insertBefore(searchBar, lyricsContent.firstChild);

      const input = searchBar.querySelector(".lyrics-search-input");
      const resultsCount = searchBar.querySelector(".search-results-count");

      input.addEventListener("input", (e) => {
        this.searchInLyrics(e.target.value, resultsCount);
      });
    }
  }

  searchInLyrics(query, resultsElement) {
    const lyricsTexts = this.panels.lyrics?.querySelectorAll(".lyrics-text");
    if (!lyricsTexts || !query.trim()) {
      // Limpiar highlights
      lyricsTexts.forEach((text) => {
        text.innerHTML = text.textContent;
      });
      resultsElement.textContent = "";
      return;
    }

    let matches = 0;
    const regex = new RegExp(
      `(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`,
      "gi",
    );

    lyricsTexts.forEach((text) => {
      const originalText = text.textContent;
      const highlightedText = originalText.replace(regex, (match) => {
        matches++;
        return `<mark class="lyrics-highlight">${match}</mark>`;
      });
      text.innerHTML = highlightedText;
    });

    resultsElement.textContent =
      matches > 0 ? `${matches} coincidencias` : "Sin resultados";
  }

  getActiveTabFromURL() {
    const hash = window.location.hash.substring(1);
    const validTabs = Object.keys(this.tabs);
    return validTabs.includes(hash) ? hash : null;
  }

  updateURL(tabName) {
    const newURL = `${window.location.pathname}${window.location.search}#${tabName}`;
    window.history.pushState({ tab: tabName }, "", newURL);
  }
}

// =============================
// FUNCIONALIDAD DE LETRAS
// =============================

class LyricsEnhancer {
  constructor() {
    this.init();
  }

  init() {
    this.addLyricsCopyButton();
    this.addFontSizeControls();
  }

  addLyricsCopyButton() {
    const lyricsSongs = document.querySelectorAll(".lyrics-song");

    lyricsSongs.forEach((song) => {
      const title = song.querySelector(".song-title");
      if (!title || title.querySelector(".copy-lyrics-btn")) return;

      const copyButton = document.createElement("button");
      copyButton.className = "copy-lyrics-btn";
      copyButton.innerHTML = "📋";
      copyButton.title = "Copiar letras";

      copyButton.addEventListener("click", () => {
        this.copyLyrics(song, copyButton);
      });

      title.appendChild(copyButton);
    });
  }

  copyLyrics(songElement, button) {
    const lyricsText = songElement.querySelector(".lyrics-text");
    const title = songElement
      .querySelector(".song-title")
      .textContent.replace("📋", "")
      .trim();

    if (!lyricsText) return;

    const text = `${title}\n\n${lyricsText.textContent.trim()}`;

    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard
        .writeText(text)
        .then(() => {
          this.showCopyFeedback(button, "✅");
        })
        .catch(() => {
          this.fallbackCopyText(text, button);
        });
    } else {
      this.fallbackCopyText(text, button);
    }
  }

  fallbackCopyText(text, button) {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.opacity = "0";
    document.body.appendChild(textArea);
    textArea.select();

    try {
      document.execCommand("copy");
      this.showCopyFeedback(button, "✅");
    } catch (err) {
      this.showCopyFeedback(button, "❌");
    }

    document.body.removeChild(textArea);
  }

  showCopyFeedback(button, emoji) {
    const originalContent = button.innerHTML;
    button.innerHTML = emoji;
    setTimeout(() => {
      button.innerHTML = originalContent;
    }, 1500);
  }

  addFontSizeControls() {
    const lyricsPanel = document.getElementById("lyrics");
    if (!lyricsPanel || lyricsPanel.querySelector(".lyrics-controls")) return;

    const controls = document.createElement("div");
    controls.className = "lyrics-controls";
    controls.style.cssText = `
            margin-bottom: 20px;
            text-align: center;
            padding: 10px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        `;

    controls.innerHTML = `
            <span>Tamaño de texto: </span>
            <button class="font-size-btn" data-size="small" style="margin: 0 5px; padding: 8px 12px; border: 2px solid var(--color-primary); background: white; color: var(--color-primary); border-radius: 4px; cursor: pointer; font-size: 14px;">A</button>
            <button class="font-size-btn active" data-size="normal" style="margin: 0 5px; padding: 8px 12px; border: 2px solid var(--color-primary); background: var(--color-primary); color: white; border-radius: 4px; cursor: pointer; font-size: 16px;">A</button>
            <button class="font-size-btn" data-size="large" style="margin: 0 5px; padding: 8px 12px; border: 2px solid var(--color-primary); background: white; color: var(--color-primary); border-radius: 4px; cursor: pointer; font-size: 18px;">A</button>
        `;

    const h3 = lyricsPanel.querySelector("h3");
    if (h3) {
      h3.insertAdjacentElement("afterend", controls);
    }

    // Eventos para botones de tamaño
    const buttons = controls.querySelectorAll(".font-size-btn");
    buttons.forEach((btn) => {
      btn.addEventListener("click", () => {
        this.changeFontSize(btn.dataset.size, buttons);
      });
    });
  }

  changeFontSize(size, allButtons) {
    const lyricsTexts = document.querySelectorAll(".lyrics-text");
    const sizeMap = {
      small: "14px",
      normal: "16px",
      large: "18px",
    };

    lyricsTexts.forEach((text) => {
      text.style.fontSize = sizeMap[size];
    });

    // Actualizar botones activos
    allButtons.forEach((btn) => {
      btn.classList.remove("active");
      btn.style.background = "white";
      btn.style.color = "var(--color-primary)";
    });

    const activeBtn = Array.from(allButtons).find(
      (btn) => btn.dataset.size === size,
    );
    if (activeBtn) {
      activeBtn.classList.add("active");
      activeBtn.style.background = "var(--color-primary)";
      activeBtn.style.color = "white";
    }
  }
}

// =============================
// UTILIDADES GENERALES
// =============================

class Utils {
  static debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  static showNotification(message, type = "info", duration = 3000) {
    const notification = document.createElement("div");
    notification.className = `notification notification--${type}`;
    notification.textContent = message;
    notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            border-radius: 8px;
            color: white;
            font-weight: 500;
            z-index: 1000;
            transform: translateX(100%);
            transition: transform 0.3s ease;
            background: ${type === "success" ? "#10b981" : type === "error" ? "#ef4444" : "#3b82f6"};
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        `;

    document.body.appendChild(notification);

    // Animar entrada
    setTimeout(() => {
      notification.style.transform = "translateX(0)";
    }, 100);

    // Animar salida
    setTimeout(() => {
      notification.style.transform = "translateX(100%)";
      setTimeout(() => {
        if (document.body.contains(notification)) {
          document.body.removeChild(notification);
        }
      }, 300);
    }, duration);
  }

  static formatDuration(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  }
}

// =============================
// MEJORAS DE ACCESIBILIDAD
// =============================

class AccessibilityEnhancer {
  constructor() {
    this.init();
  }

  init() {
    this.addKeyboardNavigation();
    this.addSkipLinks();
    this.enhanceScreenReaderSupport();
  }

  addKeyboardNavigation() {
    document.addEventListener("keydown", (e) => {
      // Alt + número para navegación rápida por pestañas
      if (e.altKey && e.key >= "1" && e.key <= "4") {
        e.preventDefault();
        const tabs = ["comment", "lyrics", "links", "tracks"];
        const tabIndex = parseInt(e.key) - 1;
        if (tabs[tabIndex] && window.tabNavigation) {
          window.tabNavigation.showTab(tabs[tabIndex]);
        }
      }
    });
  }

  addSkipLinks() {
    const skipLink = document.createElement("a");
    skipLink.href = "#main-content";
    skipLink.textContent = "Saltar al contenido principal";
    skipLink.style.cssText = `
            position: absolute;
            top: -40px;
            left: 6px;
            background: var(--color-primary);
            color: white;
            padding: 8px;
            border-radius: 4px;
            text-decoration: none;
            font-weight: bold;
            z-index: 1001;
            transition: top 0.3s ease;
        `;

    skipLink.addEventListener("focus", () => {
      skipLink.style.top = "6px";
    });

    skipLink.addEventListener("blur", () => {
      skipLink.style.top = "-40px";
    });

    document.body.insertBefore(skipLink, document.body.firstChild);

    // Agregar ID al contenido principal
    const mainContent =
      document.querySelector(".album-content") ||
      document.querySelector("main");
    if (mainContent) {
      mainContent.id = "main-content";
      mainContent.setAttribute("tabindex", "-1");
    }
  }

  enhanceScreenReaderSupport() {
    // Agregar atributos ARIA
    const tabs = document.querySelectorAll(".nav-tab");
    const panels = document.querySelectorAll(".tab-panel");

    tabs.forEach((tab, index) => {
      tab.setAttribute("role", "tab");
      tab.setAttribute("aria-controls", `panel-${index}`);
      tab.setAttribute("aria-selected", tab.classList.contains("active"));
    });

    panels.forEach((panel, index) => {
      panel.setAttribute("role", "tabpanel");
      panel.setAttribute("id", `panel-${index}`);
      panel.setAttribute("aria-hidden", !panel.classList.contains("active"));
    });
  }
}

// =============================
// GESTIÓN DEL ÍNDICE DE ÁLBUMES
// =============================

class AlbumIndexManager {
  constructor() {
    this.albums = [];
    this.init();
  }

  init() {
    this.loadAlbumsData();
    this.setupSearch();
  }

  async loadAlbumsData() {
    try {
      // Intentar cargar datos desde un archivo JSON
      const response = await fetch("./albums-data.json");
      if (response.ok) {
        this.albums = await response.json();
        this.renderAlbumsGrid();
      }
    } catch (e) {
      console.log("No se encontró archivo de datos de álbumes");
    }
  }

  addAlbum(albumData) {
    this.albums.push(albumData);
    this.saveAlbumsData();
    this.renderAlbumsGrid();
  }

  renderAlbumsGrid() {
    const grid = document.querySelector(".albums-grid");
    if (!grid) return;

    grid.innerHTML = this.albums
      .map(
        (album) => `
            <a href="albums/${album.filename}" class="album-card">
                <div class="album-card-cover">
                    <img src="${album.cover_image || this.getPlaceholderImage()}"
                         alt="Portada de ${album.title}"
                         loading="lazy">
                </div>
                <h3 class="album-card-title">${album.title}</h3>
                <p class="album-card-artist">${album.artist}</p>
                <p class="album-card-year">${album.year || ""}</p>
            </a>
        `,
      )
      .join("");
  }

  getPlaceholderImage() {
    return "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300' viewBox='0 0 300 300'%3E%3Crect width='300' height='300' fill='%23ddd'/%3E%3Ctext x='50%25' y='50%25' text-anchor='middle' dy='.3em' font-family='Arial, sans-serif' font-size='18' fill='%23999'%3EÁlbum%3C/text%3E%3C/svg%3E";
  }

  setupSearch() {
    const searchInput = document.querySelector(".search-input");
    if (!searchInput) return;

    searchInput.addEventListener(
      "input",
      Utils.debounce((e) => {
        this.filterAlbums(e.target.value);
      }, 300),
    );
  }

  filterAlbums(query) {
    const filteredAlbums = this.albums.filter(
      (album) =>
        album.title.toLowerCase().includes(query.toLowerCase()) ||
        album.artist.toLowerCase().includes(query.toLowerCase()),
    );

    const grid = document.querySelector(".albums-grid");
    if (!grid) return;

    grid.innerHTML = filteredAlbums
      .map(
        (album) => `
            <a href="albums/${album.filename}" class="album-card">
                <div class="album-card-cover">
                    <img src="${album.cover_image || this.getPlaceholderImage()}"
                         alt="Portada de ${album.title}"
                         loading="lazy">
                </div>
                <h3 class="album-card-title">${album.title}</h3>
                <p class="album-card-artist">${album.artist}</p>
                <p class="album-card-year">${album.year || ""}</p>
            </a>
        `,
      )
      .join("");
  }

  async saveAlbumsData() {
    // En un entorno real, esto haría una petición al servidor
    console.log("Datos de álbumes actualizados:", this.albums);
  }
}

// =============================
// INICIALIZACIÓN
// =============================

// Variables globales
let tabNavigation;
let lyricsEnhancer;
let accessibilityEnhancer;
let albumIndexManager;

// Inicializar cuando el DOM esté listo
document.addEventListener("DOMContentLoaded", function () {
  console.log("🎵 Album Web Generator cargando...");

  // Inicializar mejoras de accesibilidad
  accessibilityEnhancer = new AccessibilityEnhancer();

  // Inicializar según el tipo de página
  if (document.querySelector(".tab-content")) {
    // Página individual de álbum
    tabNavigation = new TabNavigation();
    lyricsEnhancer = new LyricsEnhancer();
  } else if (document.querySelector(".albums-grid")) {
    // Página índice de álbumes
    albumIndexManager = new AlbumIndexManager();
  }

  // Inicializar funciones adicionales
  initializeImageLazyLoading();

  console.log("✅ Album Web Generator inicializado correctamente");
});

// Lazy loading para imágenes
function initializeImageLazyLoading() {
  if ("IntersectionObserver" in window) {
    const imageObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const img = entry.target;
          if (img.dataset.src) {
            img.src = img.dataset.src;
            img.removeAttribute("data-src");
            imageObserver.unobserve(img);
          }
        }
      });
    });

    document.querySelectorAll("img[data-src]").forEach((img) => {
      imageObserver.observe(img);
    });
  }
}

// Funciones expuestas globalmente
window.AlbumWebGenerator = {
  showTab: (tabName) => tabNavigation?.showTab(tabName),
  searchLyrics: (query) => tabNavigation?.searchInLyrics(query),
  addAlbum: (albumData) => albumIndexManager?.addAlbum(albumData),
  utils: Utils,
};

// Manejo de errores globales
window.addEventListener("error", (e) => {
  console.error("Error en la página:", e.error);
});

console.log("🎵 Album Web Generator script cargado");
