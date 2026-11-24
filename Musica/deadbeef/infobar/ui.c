#include "ui.h"
#include "runner.h"
#include <gtk/gtk.h>
#include <string.h>
#include <stdlib.h>
#include <glib/gstdio.h>

extern DB_functions_t *deadbeef;

static ddb_gtkui_t *g_gtkui      = NULL;
static gint         g_generation = 0;

static const char *TAB_LABELS[] = { "Letras", "Artista", "Álbum", "Similares", "Sello" };
/* orden de las pestañas en el notebook */
static const int TAB_ORDER[] = { TAB_LYRICS, TAB_ARTIST, TAB_ALBUM, TAB_LABEL, TAB_SIMILAR };

typedef struct {
    ddb_gtkui_widget_t  base;
    GtkWidget          *header_label;
    GtkWidget          *spinner;
    GtkTextBuffer      *buffers[N_TABS];
    int                 active_runners;
} InfobarWidget;

static InfobarWidget *g_infobar = NULL;

/* qué artista / álbum están mostrados en sus pestañas (para no recargarlos
 * si la siguiente canción es del mismo artista o del mismo disco) */
static gchar *g_shown_artist = NULL;
static gchar *g_shown_album  = NULL;   /* "artista\x1fálbum" */

static void forget_shown(void) {
    g_free(g_shown_artist); g_shown_artist = NULL;
    g_free(g_shown_album);  g_shown_album  = NULL;
}

/* ---------- helpers ---------- */

static void set_rich_text(GtkTextBuffer *buf, const char *text);


static void set_tab_text(int tab_id, const char *text, gint gen, const char *key) {
    if (!g_infobar || gen != g_generation)
        return;

    if (tab_id == TAB_ARTIST) { g_free(g_shown_artist); g_shown_artist = g_strdup(key); }
    if (tab_id == TAB_ALBUM)  { g_free(g_shown_album);  g_shown_album  = g_strdup(key); }

    set_rich_text(g_infobar->buffers[tab_id], (text && *text) ? text : "(sin datos)");

    g_infobar->active_runners--;
    if (g_infobar->active_runners <= 0) {
        gtk_spinner_stop(GTK_SPINNER(g_infobar->spinner));
        gtk_widget_hide(g_infobar->spinner);
        g_infobar->active_runners = 0;
    }
}

static void clear_all_tabs(void) {
    forget_shown();
    if (!g_infobar) return;
    for (int i = 0; i < N_TABS; i++)
        gtk_text_buffer_set_text(g_infobar->buffers[i], "", -1);
    gtk_label_set_text(GTK_LABEL(g_infobar->header_label), "");
    gtk_spinner_stop(GTK_SPINNER(g_infobar->spinner));
    gtk_widget_hide(g_infobar->spinner);
}

static void get_scripts_dir(char *buf, size_t sz) {
    char tmp[512] = "";
    deadbeef->conf_get_str("infobar_ng.scripts_dir", "", tmp, sizeof(tmp));
    if (*tmp) {
        g_strlcpy(buf, tmp, sz);
        return;
    }
    snprintf(buf, sz, "%s/.config/deadbeef/infobar_scripts", g_get_home_dir());
}

static void get_python_cmd(char *buf, size_t sz) {
    char tmp[512] = "";
    deadbeef->conf_get_str("infobar_ng.python_cmd", "", tmp, sizeof(tmp));
    if (*tmp) {
        g_strlcpy(buf, tmp, sz);
        return;
    }
    snprintf(buf, sz, "%s/Scripts/python_venv/bin/python", g_get_home_dir());
}


/* ---------- texto enriquecido: «## título», [texto](url) y URLs sueltas ---------- */

static GtkTextBuffer *g_lyrics_buffer = NULL;   /* compartido con el widget «Letras» */

static void ensure_tags(GtkTextBuffer *buf) {
    GtkTextTagTable *tt = gtk_text_buffer_get_tag_table(buf);
    if (gtk_text_tag_table_lookup(tt, "link"))
        return;
    /* el color lo pone apply_theme_color() con el acento del tema */
    gtk_text_buffer_create_tag(buf, "link", "foreground", "#3b9be8",
                               "underline", PANGO_UNDERLINE_SINGLE, NULL);
    gtk_text_buffer_create_tag(buf, "h", "foreground", "#3b9be8",
                               "weight", PANGO_WEIGHT_BOLD,
                               "pixels-above-lines", 8, NULL);
    /* «Clave:» en negrita */
    gtk_text_buffer_create_tag(buf, "k", "weight", PANGO_WEIGHT_BOLD, NULL);
}

/* acento del tema activo: @d1_accent del skin DarkOne4Mod (cambia en caliente
 * con Ver → Colores DarkOne…) o, con otro tema, el color de selección */
static void apply_theme_color(GtkWidget *tv, gpointer unused) {
    (void)unused;
    GtkStyleContext *sc = gtk_widget_get_style_context(tv);
    GdkRGBA c;
    if (!gtk_style_context_lookup_color(sc, "d1_accent", &c) &&
        !gtk_style_context_lookup_color(sc, "theme_selected_bg_color", &c))
        gdk_rgba_parse(&c, "#3b9be8");
    GtkTextBuffer *buf = gtk_text_view_get_buffer(GTK_TEXT_VIEW(tv));
    ensure_tags(buf);
    GtkTextTagTable *tt = gtk_text_buffer_get_tag_table(buf);
    g_object_set(gtk_text_tag_table_lookup(tt, "link"), "foreground-rgba", &c, NULL);
    g_object_set(gtk_text_tag_table_lookup(tt, "h"), "foreground-rgba", &c, NULL);
}

static GtkTextBuffer *lyrics_buffer(void) {
    if (!g_lyrics_buffer) {
        g_lyrics_buffer = gtk_text_buffer_new(NULL);
        ensure_tags(g_lyrics_buffer);
    }
    return g_lyrics_buffer;
}

static void clear_url_tags(GtkTextBuffer *buf) {
    GSList *tags = g_object_steal_data(G_OBJECT(buf), "url-tags");
    GtkTextTagTable *tt = gtk_text_buffer_get_tag_table(buf);
    for (GSList *l = tags; l; l = l->next)
        gtk_text_tag_table_remove(tt, GTK_TEXT_TAG(l->data));
    g_slist_free(tags);
}

static void insert_link(GtkTextBuffer *buf, GtkTextIter *end,
                        const char *label, gssize len, const char *url) {
    GtkTextTag *t = gtk_text_buffer_create_tag(buf, NULL, NULL);
    g_object_set_data_full(G_OBJECT(t), "url", g_strdup(url), g_free);
    GSList *tags = g_object_steal_data(G_OBJECT(buf), "url-tags");
    g_object_set_data(G_OBJECT(buf), "url-tags", g_slist_prepend(tags, t));
    gtk_text_buffer_insert_with_tags_by_name(buf, end, label, len, "link", NULL);
    GtkTextIter start = *end;
    gtk_text_iter_backward_chars(&start, g_utf8_strlen(label, len));
    gtk_text_buffer_apply_tag(buf, t, &start, end);
}

/* línea de imágenes: «![](ruta) ![](ruta) …» → carrusel: una foto cada vez,
 * ‹ › (o desplazamiento horizontal) para pasar, clic: abrir la imagen */
#define PHOTO_H 260
#define PHOTO_MAX_W 420

typedef struct {
    GPtrArray *pix;     /* GdkPixbuf* */
    GPtrArray *uris;    /* gchar* */
    guint      idx;
    gdouble    acc;     /* desplazamiento horizontal acumulado */
    GtkWidget *image, *count;
} Carousel;

static void carousel_free(gpointer data) {
    Carousel *c = data;
    g_ptr_array_unref(c->pix);
    g_ptr_array_unref(c->uris);
    g_free(c);
}

static void carousel_show(Carousel *c) {
    gtk_image_set_from_pixbuf(GTK_IMAGE(c->image), g_ptr_array_index(c->pix, c->idx));
    gchar *t = g_strdup_printf("%u / %u", c->idx + 1, c->pix->len);
    gtk_label_set_text(GTK_LABEL(c->count), t);
    g_free(t);
}

static void carousel_step(Carousel *c, int d) {
    guint n = c->pix->len;
    c->idx = (c->idx + n + d) % n;
    carousel_show(c);
}

static void carousel_prev(GtkButton *b, gpointer data) { (void)b; carousel_step(data, -1); }
static void carousel_next(GtkButton *b, gpointer data) { (void)b; carousel_step(data, +1); }

static gboolean carousel_scroll(GtkWidget *w, GdkEventScroll *ev, gpointer data) {
    (void)w;
    Carousel *c = data;
    if (c->pix->len < 2) return FALSE;
    switch (ev->direction) {
    case GDK_SCROLL_LEFT:  carousel_step(c, -1); return TRUE;
    case GDK_SCROLL_RIGHT: carousel_step(c, +1); return TRUE;
    case GDK_SCROLL_SMOOTH:
        if (ev->delta_x == 0) return FALSE;     /* vertical: que baje el texto */
        c->acc += ev->delta_x;
        if (c->acc <= -1.0) { c->acc = 0; carousel_step(c, -1); }
        else if (c->acc >= 1.0) { c->acc = 0; carousel_step(c, +1); }
        return TRUE;
    default:
        return FALSE;
    }
}

static gboolean carousel_click(GtkWidget *w, GdkEventButton *ev, gpointer data) {
    Carousel *c = data;
    if (ev->button == 1) {
        gtk_show_uri_on_window(GTK_WINDOW(gtk_widget_get_toplevel(w)),
                               g_ptr_array_index(c->uris, c->idx), ev->time, NULL);
        return TRUE;
    }
    if (ev->button == 8) { carousel_step(c, -1); return TRUE; }   /* botones atrás/adelante del ratón */
    if (ev->button == 9) { carousel_step(c, +1); return TRUE; }
    return FALSE;
}

static void carousel_realize(GtkWidget *w, gpointer unused) {
    (void)unused;
    GdkCursor *hand = gdk_cursor_new_from_name(gtk_widget_get_display(w), "pointer");
    gdk_window_set_cursor(gtk_widget_get_window(w), hand);
    g_object_unref(hand);
}

/* botones y contador translúcidos (fondo negro semiopaco), sea cual sea el tema */
static void carousel_style(GtkWidget *w) {
    static GtkCssProvider *css = NULL;
    if (!css) {
        css = gtk_css_provider_new();
        gtk_css_provider_load_from_data(css,
            "button.carousel { background: rgba(0,0,0,0.45); color: #fff; border: none;"
            " box-shadow: none; border-radius: 50%; min-width: 34px; min-height: 34px; padding: 2px; }"
            "button.carousel:hover { background: rgba(0,0,0,0.65); }"
            "button.carousel:active { background: rgba(0,0,0,0.8); }"
            "label.carousel { background: rgba(0,0,0,0.45); color: #fff; border-radius: 8px; padding: 1px 6px; }",
            -1, NULL);
    }
    GtkStyleContext *sc = gtk_widget_get_style_context(w);
    gtk_style_context_add_provider(sc, GTK_STYLE_PROVIDER(css), GTK_STYLE_PROVIDER_PRIORITY_APPLICATION + 1);
    gtk_style_context_add_class(sc, "carousel");
}

static GtkWidget *carousel_button(const char *icon, GtkAlign al, GCallback cb, Carousel *c) {
    GtkWidget *b = gtk_button_new_from_icon_name(icon, GTK_ICON_SIZE_LARGE_TOOLBAR);
    carousel_style(b);
    gtk_widget_set_halign(b, al);
    gtk_widget_set_valign(b, GTK_ALIGN_CENTER);
    gtk_widget_set_margin_start(b, 4);
    gtk_widget_set_margin_end(b, 4);
    gtk_widget_set_can_focus(b, FALSE);
    g_signal_connect(b, "clicked", cb, c);
    return b;
}

static GtkWidget *carousel_new(Carousel *c) {
    int maxw = 0, maxh = 0;
    for (guint i = 0; i < c->pix->len; i++) {
        GdkPixbuf *pb = g_ptr_array_index(c->pix, i);
        maxw = MAX(maxw, gdk_pixbuf_get_width(pb));
        maxh = MAX(maxh, gdk_pixbuf_get_height(pb));
    }
    GtkWidget *ev = gtk_event_box_new();
    gtk_widget_add_events(ev, GDK_SCROLL_MASK | GDK_SMOOTH_SCROLL_MASK | GDK_BUTTON_RELEASE_MASK);
    c->image = gtk_image_new();
    gtk_widget_set_size_request(c->image, maxw, maxh);   /* tamaño fijo: no salta al cambiar */
    gtk_container_add(GTK_CONTAINER(ev), c->image);
    g_signal_connect(ev, "button-release-event", G_CALLBACK(carousel_click), c);
    g_signal_connect(ev, "scroll-event", G_CALLBACK(carousel_scroll), c);
    g_signal_connect(ev, "realize", G_CALLBACK(carousel_realize), NULL);

    GtkWidget *ov = gtk_overlay_new();
    gtk_container_add(GTK_CONTAINER(ov), ev);
    c->count = gtk_label_new("");
    carousel_style(c->count);
    gtk_widget_set_halign(c->count, GTK_ALIGN_END);
    gtk_widget_set_valign(c->count, GTK_ALIGN_END);
    gtk_widget_set_margin_end(c->count, 6);
    gtk_widget_set_margin_bottom(c->count, 6);
    if (c->pix->len > 1) {
        gtk_overlay_add_overlay(GTK_OVERLAY(ov), carousel_button("go-previous-symbolic", GTK_ALIGN_START, G_CALLBACK(carousel_prev), c));
        gtk_overlay_add_overlay(GTK_OVERLAY(ov), carousel_button("go-next-symbolic", GTK_ALIGN_END, G_CALLBACK(carousel_next), c));
        gtk_overlay_add_overlay(GTK_OVERLAY(ov), c->count);
    }
    g_object_set_data_full(G_OBJECT(ov), "carousel", c, carousel_free);
    carousel_show(c);
    gtk_widget_show_all(ov);
    return ov;
}

static gboolean insert_images(GtkTextBuffer *buf, GtkTextIter *end, const char *ln) {
    static GRegex *img = NULL;
    if (!img) img = g_regex_new("^\\s*(!\\[[^\\]]*\\]\\(([^)]+)\\)\\s*)+$", 0, 0, NULL);
    if (!g_regex_match(img, ln, 0, NULL)) return FALSE;
    static GRegex *one = NULL;
    if (!one) one = g_regex_new("!\\[[^\\]]*\\]\\(([^)]+)\\)", 0, 0, NULL);
    Carousel *c = g_new0(Carousel, 1);
    c->pix  = g_ptr_array_new_with_free_func(g_object_unref);
    c->uris = g_ptr_array_new_with_free_func(g_free);
    GMatchInfo *mi = NULL;
    g_regex_match(one, ln, 0, &mi);
    while (g_match_info_matches(mi)) {
        gchar *path = g_match_info_fetch(mi, 1);
        GdkPixbuf *pb = gdk_pixbuf_new_from_file_at_scale(path, PHOTO_MAX_W, PHOTO_H, TRUE, NULL);
        if (pb) {
            g_ptr_array_add(c->pix, pb);
            g_ptr_array_add(c->uris, g_filename_to_uri(path, NULL, NULL));
        }
        g_free(path);
        g_match_info_next(mi, NULL);
    }
    g_match_info_free(mi);
    GtkTextView *tv = g_object_get_data(G_OBJECT(buf), "infobar-view");
    if (!c->pix->len || !tv) {     /* sin fotos legibles o buffer sin vista propia */
        carousel_free(c);
        return TRUE;
    }
    GtkTextTagTable *tt = gtk_text_buffer_get_tag_table(buf);
    if (!gtk_text_tag_table_lookup(tt, "center"))
        gtk_text_buffer_create_tag(buf, "center", "justification", GTK_JUSTIFY_CENTER, NULL);
    GtkTextMark *m = gtk_text_buffer_create_mark(buf, NULL, end, TRUE);
    GtkTextChildAnchor *a = gtk_text_buffer_create_child_anchor(buf, end);
    gtk_text_view_add_child_at_anchor(tv, carousel_new(c), a);
    GtkTextIter start;
    gtk_text_buffer_get_iter_at_mark(buf, &start, m);
    gtk_text_buffer_apply_tag_by_name(buf, "center", &start, end);
    gtk_text_buffer_delete_mark(buf, m);
    return TRUE;
}

static void set_rich_text(GtkTextBuffer *buf, const char *text) {
    static GRegex *re = NULL;
    if (!re)
        re = g_regex_new("\\[([^\\]\\n]+)\\]\\(((?:https?|ddbpl):[^)\\s]+)\\)|(https?://[^\\s<>()\\]]+)",
                         0, 0, NULL);
    ensure_tags(buf);
    gtk_text_buffer_set_text(buf, "", -1);
    clear_url_tags(buf);

    GtkTextIter end;
    gtk_text_buffer_get_end_iter(buf, &end);
    gchar **lines = g_strsplit(text, "\n", -1);
    for (int i = 0; lines[i]; i++) {
        const char *ln = lines[i];
        if (i > 0)
            gtk_text_buffer_insert(buf, &end, "\n", 1);
        if (ln[0] == '!' || ln[0] == ' ') {
            if (insert_images(buf, &end, ln)) continue;
        }
        /* título: «## texto» y, opcionalmente, un enlace detrás («## AudioMuse · Mix  [▶ crear lista](ddbpl:…)») */
        if (g_str_has_prefix(ln, "## ")) {
            const char *h = ln + 3;
            const char *lk = strstr(h, "  [");
            if (lk && strstr(lk, "](") && g_str_has_suffix(lk, ")")) {
                gtk_text_buffer_insert_with_tags_by_name(buf, &end, h, lk - h, "h", NULL);
                gtk_text_buffer_insert(buf, &end, "   ", -1);
                ln = lk + 2;      /* el resto (el enlace) sigue por el camino normal */
            } else {
                gtk_text_buffer_insert_with_tags_by_name(buf, &end, h, -1, "h", NULL);
                continue;
            }
        }
        /* «Clave: valor» → clave en negrita (no en las letras: ahí sería prosa).
         * Clave corta (≤ 5 palabras, sin comas ni corchetes) para no tocar frases. */
        if (buf != g_lyrics_buffer) {
            static GRegex *kv = NULL;
            if (!kv)
                kv = g_regex_new("^(\\s*(?:[-*•·]\\s+)?)"
                                 "((?!https?\\b)[^\\s:\\[\\]—,][^:\\[\\]—,\\s]*(?: [^:\\[\\]—,\\s]+){0,4}:)"
                                 "(?=\\s|$)", 0, 0, NULL);
            GMatchInfo *km = NULL;
            int ps, pe, ks, ke, bal = 0;
            if (g_regex_match(kv, ln, 0, &km)) {
                g_match_info_fetch_pos(km, 1, &ps, &pe);
                g_match_info_fetch_pos(km, 2, &ks, &ke);
                for (int j = ks; j < ke; j++) bal += (ln[j] == '(') - (ln[j] == ')');
            }
            if (g_match_info_matches(km) && bal == 0) {   /* «Coisas Naturais (English:» no */
                gtk_text_buffer_insert(buf, &end, ln + ps, pe - ps);
                gtk_text_buffer_insert_with_tags_by_name(buf, &end, ln + ks, ke - ks, "k", NULL);
                ln += ke;
            }
            g_match_info_free(km);
        }
        GMatchInfo *mi = NULL;
        const char *pos = ln;
        g_regex_match(re, ln, 0, &mi);
        while (g_match_info_matches(mi)) {
            int ms, me;
            g_match_info_fetch_pos(mi, 0, &ms, &me);
            gtk_text_buffer_insert(buf, &end, pos, (ln + ms) - pos);
            gchar *label = g_match_info_fetch(mi, 1);
            gchar *url   = g_match_info_fetch(mi, 2);
            if (!url || !*url) {
                g_free(url);
                g_free(label);
                url   = g_match_info_fetch(mi, 3);
                label = g_strdup(url);
            }
            insert_link(buf, &end, label, -1, url);
            g_free(label);
            g_free(url);
            pos = ln + me;
            g_match_info_next(mi, NULL);
        }
        g_match_info_free(mi);
        gtk_text_buffer_insert(buf, &end, pos, -1);
    }
    g_strfreev(lines);
}

static const char *url_at(GtkTextView *tv, gdouble wx, gdouble wy) {
    gint bx, by;
    gtk_text_view_window_to_buffer_coords(tv, GTK_TEXT_WINDOW_WIDGET, (gint)wx, (gint)wy, &bx, &by);
    GtkTextIter it;
    if (!gtk_text_view_get_iter_at_location(tv, &it, bx, by))
        return NULL;
    const char *url = NULL;
    GSList *tags = gtk_text_iter_get_tags(&it);
    for (GSList *l = tags; l && !url; l = l->next)
        url = g_object_get_data(G_OBJECT(l->data), "url");
    g_slist_free(tags);
    return url;
}

static gboolean tv_release(GtkWidget *w, GdkEventButton *ev, gpointer unused) {
    (void)unused;
    if (ev->button != 1)
        return FALSE;
    GtkTextBuffer *buf = gtk_text_view_get_buffer(GTK_TEXT_VIEW(w));
    if (gtk_text_buffer_get_has_selection(buf))
        return FALSE;
    const char *url = url_at(GTK_TEXT_VIEW(w), ev->x, ev->y);
    if (url && g_str_has_prefix(url, "ddbpl:")) {
        /* lista de recomendaciones: la crea el plugin DarkOne4Mod (busca en la biblioteca) */
        deadbeef->conf_set_str("darkone.playlist_request", url + 6);
        DB_plugin_t **plugs = deadbeef->plug_get_list();
        for (int i = 0; plugs[i]; i++) {
            if (!plugs[i]->get_actions) continue;
            for (DB_plugin_action_t *a = plugs[i]->get_actions(NULL); a; a = a->next) {
                if (a->name && !strcmp(a->name, "darkone_similar_playlist") && a->callback2) {
                    a->callback2(a, DDB_ACTION_CTX_MAIN);
                    return TRUE;
                }
            }
        }
        return TRUE;
    }
    if (url) {
        gtk_show_uri_on_window(GTK_WINDOW(gtk_widget_get_toplevel(w)), url, ev->time, NULL);
        return TRUE;
    }
    return FALSE;
}

static gboolean tv_motion(GtkWidget *w, GdkEventMotion *ev, gpointer unused) {
    (void)unused;
    static GdkCursor *hand = NULL, *text = NULL;
    if (!hand) {
        hand = gdk_cursor_new_from_name(gdk_display_get_default(), "pointer");
        text = gdk_cursor_new_from_name(gdk_display_get_default(), "text");
    }
    GdkWindow *win = gtk_text_view_get_window(GTK_TEXT_VIEW(w), GTK_TEXT_WINDOW_TEXT);
    gdk_window_set_cursor(win, url_at(GTK_TEXT_VIEW(w), ev->x, ev->y) ? hand : text);
    return FALSE;
}

static GtkWidget *make_text_view(GtkTextBuffer *shared) {
    GtkWidget *scroll = gtk_scrolled_window_new(NULL, NULL);
    gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll),
                                   GTK_POLICY_AUTOMATIC, GTK_POLICY_AUTOMATIC);
    GtkWidget *tv = shared ? gtk_text_view_new_with_buffer(shared) : gtk_text_view_new();
    if (!shared)    /* buffer con una sola vista: ahí se pueden poner widgets (carrusel de fotos) */
        g_object_set_data(G_OBJECT(gtk_text_view_get_buffer(GTK_TEXT_VIEW(tv))), "infobar-view", tv);
    gtk_text_view_set_editable(GTK_TEXT_VIEW(tv), FALSE);
    gtk_text_view_set_wrap_mode(GTK_TEXT_VIEW(tv), GTK_WRAP_WORD_CHAR);
    gtk_text_view_set_cursor_visible(GTK_TEXT_VIEW(tv), FALSE);
    gtk_text_view_set_left_margin(GTK_TEXT_VIEW(tv), 6);
    gtk_text_view_set_right_margin(GTK_TEXT_VIEW(tv), 6);
    gtk_text_view_set_top_margin(GTK_TEXT_VIEW(tv), 4);
    ensure_tags(gtk_text_view_get_buffer(GTK_TEXT_VIEW(tv)));
    g_signal_connect(tv, "style-updated", G_CALLBACK(apply_theme_color), NULL);
    gtk_widget_add_events(tv, GDK_POINTER_MOTION_MASK | GDK_BUTTON_RELEASE_MASK);
    g_signal_connect(tv, "button-release-event", G_CALLBACK(tv_release), NULL);
    g_signal_connect(tv, "motion-notify-event", G_CALLBACK(tv_motion), NULL);
    gtk_container_add(GTK_CONTAINER(scroll), tv);
    return scroll;
}

/* ---------- consultas: con retraso, de una en una, con caché y prioridad baja ----------
 *
 * La reproducción va primero: la música llega por NFS (a menudo por wifi) y las
 * consultas web compiten por la red. Por eso:
 *   - se espera INFOBAR_DELAY_MS tras el cambio de canción (si se cambia antes, nada);
 *   - un solo hilo ejecuta los scripts en serie y abandona si cambia la canción;
 *   - los resultados se guardan en ~/.cache/darkone4mod/infobar/ (por script + argumentos);
 *   - los scripts corren con nice 19 / ionice idle.
 */

#define INFOBAR_DELAY_MS 3000

typedef struct {
    gchar *python;
    gchar *scripts_dir;
    gchar *artist;
    gchar *title;
    gchar *album;
    gint   generation;
    gboolean do_artist;
    gboolean do_album;
} FetchArgs;

typedef struct {
    int    tab_id;
    gchar *text;
    gint   generation;
    gchar *key;
} FetchResult;

static guint      g_fetch_timer = 0;
static FetchArgs *g_pending     = NULL;

static void fetch_args_free(FetchArgs *a) {
    if (!a) return;
    g_free(a->python); g_free(a->scripts_dir);
    g_free(a->artist); g_free(a->title); g_free(a->album);
    g_free(a);
}

static gboolean fetch_result_idle(gpointer data) {
    FetchResult *res = data;
    set_tab_text(res->tab_id, res->text, res->generation, res->key);
    g_free(res->text);
    g_free(res->key);
    g_free(res);
    return G_SOURCE_REMOVE;
}

static void post_result(int tab, const char *text, gint gen, const char *key) {
    FetchResult *res = g_new(FetchResult, 1);
    res->tab_id = tab;
    res->text = g_strdup(text ? text : "");
    res->generation = gen;
    res->key = g_strdup(key);
    g_idle_add(fetch_result_idle, res);
}

static gchar *cache_path(const char *script, const char *a1, const char *a2) {
    gchar *key = g_strdup_printf("%s\x1f%s\x1f%s", script, a1 ? a1 : "", a2 ? a2 : "");
    gchar *sum = g_compute_checksum_for_string(G_CHECKSUM_SHA1, key, -1);
    gchar *dir = g_build_filename(g_get_user_cache_dir(), "darkone4mod", "infobar", NULL);
    g_mkdir_with_parents(dir, 0700);
    gchar *path = g_build_filename(dir, sum, NULL);
    g_free(key); g_free(sum); g_free(dir);
    return path;
}

static gchar *cache_get(const char *path, gint64 ttl_s) {
    GStatBuf st;
    if (ttl_s <= 0 || g_stat(path, &st) != 0) return NULL;
    if ((g_get_real_time() / G_USEC_PER_SEC) - st.st_mtime > ttl_s) return NULL;
    gchar *txt = NULL;
    if (!g_file_get_contents(path, &txt, NULL, NULL)) return NULL;
    return txt;
}

/* ejecuta  python script a1 [a2]  con prioridad baja; devuelve stdout o NULL */
static gchar *run_script(const FetchArgs *a, const char *script, const char *a1, const char *a2) {
    gchar *path = g_build_filename(a->scripts_dir, script, NULL);
    if (!g_file_test(path, G_FILE_TEST_EXISTS)) { g_free(path); return NULL; }
    const char *argv[12];
    int n = 0;
    gchar *timeout_bin = g_find_program_in_path("timeout");
    gchar *nice_bin = g_find_program_in_path("nice");
    gchar *ionice_bin = g_find_program_in_path("ionice");
    if (timeout_bin) { argv[n++] = timeout_bin; argv[n++] = "25"; }   /* ningún script se queda colgado */
    if (nice_bin)   { argv[n++] = nice_bin; argv[n++] = "-n19"; }
    if (ionice_bin) { argv[n++] = ionice_bin; argv[n++] = "-c3"; }
    argv[n++] = a->python; argv[n++] = path; argv[n++] = a1;
    if (a2) argv[n++] = a2;
    argv[n] = NULL;
    gchar *out = NULL;
    gint status = 1;
    g_spawn_sync(NULL, (gchar **)argv, NULL, G_SPAWN_STDERR_TO_DEV_NULL,
                 NULL, NULL, &out, NULL, &status, NULL);
    g_free(path); g_free(timeout_bin); g_free(nice_bin); g_free(ionice_bin);
    if (status != 0 || !out || !*out) { g_free(out); return NULL; }
    return out;
}

#define PARCIAL "<!--parcial-->\n"

/* script con caché; ttl en segundos. Si la salida empieza por <!--parcial--> (el script
 * sigue bajando datos) no se guarda, se quita la marca y *partial = TRUE */
static gchar *cached_script_p(const FetchArgs *a, const char *script, const char *a1, const char *a2,
                              gint64 ttl, gboolean *partial) {
    if (partial) *partial = FALSE;
    gchar *cp = cache_path(script, a1, a2);
    gchar *txt = cache_get(cp, ttl);
    if (!txt) {
        txt = run_script(a, script, a1, a2);
        if (txt && g_str_has_prefix(txt, PARCIAL)) {
            memmove(txt, txt + strlen(PARCIAL), strlen(txt) - strlen(PARCIAL) + 1);
            if (partial) *partial = TRUE;
        }
        else if (txt) g_file_set_contents(cp, txt, -1, NULL);
    }
    g_free(cp);
    return txt;
}

static gchar *cached_script(const FetchArgs *a, const char *script, const char *a1, const char *a2, gint64 ttl) {
    return cached_script_p(a, script, a1, a2, ttl, NULL);
}

#define STALE(a) (g_atomic_int_get(&g_generation) != (a)->generation)

static gpointer fetch_thread(gpointer data) {
    FetchArgs *a = data;
    const gint64 DAY = 24 * 3600;

    /* letras: lyrics.ovh y, si no, genius */
    if (!STALE(a)) {
        gchar *t = cached_script(a, "letras_ovh.py", a->artist, a->title, 30 * DAY);
        if (!t && !STALE(a)) t = cached_script(a, "letras_genius.py", a->artist, a->title, 30 * DAY);
        post_result(TAB_LYRICS, t, a->generation, NULL);
        g_free(t);
    }
    if (a->do_album && !STALE(a)) {
        gchar *t = a->album[0] ? cached_script(a, "info_album.py", a->artist, a->album, 7 * DAY) : NULL;
        gchar *key = g_strdup_printf("%s\x1f%s", a->artist, a->album);
        post_result(TAB_ALBUM, t, a->generation, key);
        g_free(key);
        g_free(t);
    }
    if (a->do_artist && !STALE(a)) {
        gchar *t = cached_script(a, "bio_artista.py", a->artist, NULL, 7 * DAY);
        post_result(TAB_ARTIST, t, a->generation, a->artist);
        g_free(t);
    }
    if (!STALE(a)) {
        gchar *t = cached_script(a, "similares.py", a->artist, a->title, DAY);
        post_result(TAB_SIMILAR, t, a->generation, NULL);
        g_free(t);
    }
    /* sello: puede tardar en completarse (baja créditos de Discogs en segundo plano);
     * mientras sea parcial, se vuelve a pedir cada 20 s (hasta ~3 min) */
    if (a->do_album && !STALE(a)) {
        gboolean partial = FALSE;
        for (int tries = 0; tries < 10 && !STALE(a); tries++) {
            gchar *t = a->album[0] ? cached_script_p(a, "sello.py", a->artist, a->album, 7 * DAY, &partial) : NULL;
            if (!STALE(a)) post_result(TAB_LABEL, t, a->generation, NULL);
            g_free(t);
            if (!partial) break;
            for (int s = 0; s < 20 && !STALE(a); s++) g_usleep(G_USEC_PER_SEC);
        }
    }
    fetch_args_free(a);
    return NULL;
}

static gboolean fetch_timer_cb(gpointer unused) {
    (void)unused;
    g_fetch_timer = 0;
    FetchArgs *a = g_pending;
    g_pending = NULL;
    if (!a || STALE(a)) { fetch_args_free(a); return G_SOURCE_REMOVE; }
    GThread *th = g_thread_new("infobar_fetch", fetch_thread, a);
    g_thread_unref(th);
    return G_SOURCE_REMOVE;
}

/* ---------- public update functions ---------- */

gboolean infobar_update_for_track(DB_playItem_t *track) {
    if (!g_infobar || !track) {
        if (track) deadbeef->pl_item_unref(track);
        return G_SOURCE_REMOVE;
    }

    deadbeef->pl_lock();
    const char *r_artist = deadbeef->pl_find_meta(track, "artist");
    const char *r_title  = deadbeef->pl_find_meta(track, "title");
    const char *r_album  = deadbeef->pl_find_meta(track, "album");
    gchar *artist = g_strdup(r_artist ? r_artist : "");
    gchar *title  = g_strdup(r_title  ? r_title  : "");
    gchar *album  = g_strdup(r_album  ? r_album  : "");
    deadbeef->pl_unlock();
    deadbeef->pl_item_unref(track);

    /* SONGCHANGED y SONGSTARTED llegan los dos: no repetir para la misma canción */
    gchar *header = g_strdup_printf("%s — %s", artist, title);
    const char *cur = gtk_label_get_text(GTK_LABEL(g_infobar->header_label));
    static gint64 last_req = 0;
    gint64 now = g_get_monotonic_time();
    if (cur && !strcmp(cur, header) && (g_pending || now - last_req < 600 * G_USEC_PER_SEC)) {
        g_free(header); g_free(artist); g_free(title); g_free(album);
        return G_SOURCE_REMOVE;
    }
    gtk_label_set_text(GTK_LABEL(g_infobar->header_label), header);
    g_free(header);
    last_req = now;

    g_atomic_int_inc(&g_generation);
    gint gen = g_atomic_int_get(&g_generation);

    /* mismo artista / mismo disco que lo ya mostrado: esas pestañas no se tocan */
    gchar *album_key = g_strdup_printf("%s\x1f%s", artist, album);
    gboolean do_artist = !g_shown_artist || strcmp(g_shown_artist, artist) != 0;
    gboolean do_album  = !g_shown_album  || strcmp(g_shown_album, album_key) != 0;
    g_free(album_key);

    int runners = 0;
    for (int i = 0; i < N_TABS; i++) {
        if ((i == TAB_ARTIST && !do_artist) || ((i == TAB_ALBUM || i == TAB_LABEL) && !do_album)) continue;
        gtk_text_buffer_set_text(g_infobar->buffers[i], "Cargando…", -1);
        if (i == TAB_ARTIST) { g_free(g_shown_artist); g_shown_artist = NULL; }
        if (i == TAB_ALBUM)  { g_free(g_shown_album);  g_shown_album  = NULL; }
        runners++;
    }
    gtk_widget_show(g_infobar->spinner);
    gtk_spinner_start(GTK_SPINNER(g_infobar->spinner));
    g_infobar->active_runners = runners;

    char scripts_dir[512], python[512];
    get_scripts_dir(scripts_dir, sizeof(scripts_dir));
    get_python_cmd(python, sizeof(python));

    fetch_args_free(g_pending);
    g_pending = g_new0(FetchArgs, 1);
    g_pending->python      = g_strdup(python);
    g_pending->scripts_dir = g_strdup(scripts_dir);
    g_pending->artist      = artist;
    g_pending->title       = title;
    g_pending->album       = album;
    g_pending->generation  = gen;
    g_pending->do_artist   = do_artist;
    g_pending->do_album    = do_album;

    if (g_fetch_timer) g_source_remove(g_fetch_timer);
    g_fetch_timer = g_timeout_add(INFOBAR_DELAY_MS, fetch_timer_cb, NULL);
    return G_SOURCE_REMOVE;
}

gboolean infobar_clear(gpointer unused) {
    (void)unused;
    g_atomic_int_inc(&g_generation);
    clear_all_tabs();
    return G_SOURCE_REMOVE;
}

/* ---------- widget lifecycle ---------- */

static void infobar_widget_destroy(ddb_gtkui_widget_t *w);

static ddb_gtkui_widget_t *infobar_widget_create(void) {
    InfobarWidget *w = calloc(1, sizeof(InfobarWidget));
    g_infobar = w;
    forget_shown();

    GtkWidget *vbox = gtk_box_new(GTK_ORIENTATION_VERTICAL, 2);
    w->base.widget = vbox;

    /* header: spinner + "Artist — Title" label */
    GtkWidget *hbox = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 4);
    w->spinner = gtk_spinner_new();
    gtk_widget_set_no_show_all(w->spinner, TRUE);
    w->header_label = gtk_label_new("");
    gtk_label_set_ellipsize(GTK_LABEL(w->header_label), PANGO_ELLIPSIZE_END);
    gtk_label_set_xalign(GTK_LABEL(w->header_label), 0.0f);
    gtk_box_pack_start(GTK_BOX(hbox), w->spinner, FALSE, FALSE, 2);
    gtk_box_pack_start(GTK_BOX(hbox), w->header_label, TRUE, TRUE, 4);
    gtk_box_pack_start(GTK_BOX(vbox), hbox, FALSE, FALSE, 0);

    /* notebook */
    GtkWidget *nb = gtk_notebook_new();
    gtk_notebook_set_tab_pos(GTK_NOTEBOOK(nb), GTK_POS_TOP);

    for (int k = 0; k < N_TABS; k++) {
        int i = TAB_ORDER[k];
        /* las letras tienen su propio widget («Infobar NG: letras»): aquí no va pestaña,
         * pero el buffer compartido se sigue rellenando */
        if (i == TAB_LYRICS) { w->buffers[i] = lyrics_buffer(); continue; }
        GtkWidget *scroll = make_text_view(NULL);
        GtkWidget *tv = gtk_bin_get_child(GTK_BIN(scroll));
        w->buffers[i] = gtk_text_view_get_buffer(GTK_TEXT_VIEW(tv));
        gtk_notebook_append_page(GTK_NOTEBOOK(nb), scroll, gtk_label_new(TAB_LABELS[i]));
    }

    gtk_box_pack_start(GTK_BOX(vbox), nb, TRUE, TRUE, 0);
    gtk_widget_show_all(vbox);
    gtk_widget_hide(w->spinner);

    w->base.destroy = infobar_widget_destroy;
    g_gtkui->w_override_signals(vbox, w);
    return (ddb_gtkui_widget_t *)w;
}

static void infobar_widget_destroy(ddb_gtkui_widget_t *w) {
    if (g_infobar == (InfobarWidget *)w)
        g_infobar = NULL;
    /* gtkui libera la estructura con free() en w_destroy: no liberar aquí */
}

/* ---------- widget «Letras NG» (comparte el buffer de letras) ---------- */

static ddb_gtkui_widget_t *lyrics_widget_create(void) {
    ddb_gtkui_widget_t *w = calloc(1, sizeof(ddb_gtkui_widget_t));
    w->widget = make_text_view(lyrics_buffer());
    gtk_widget_show_all(w->widget);
    g_gtkui->w_override_signals(w->widget, w);
    return w;
}

/* ---------- register / unregister ---------- */

void infobar_widget_register(ddb_gtkui_t *gtkui) {
    g_gtkui = gtkui;
    gtkui->w_reg_widget("Infobar NG", DDB_WF_SINGLE_INSTANCE,
                        infobar_widget_create, "infobar_ng", NULL);
    gtkui->w_reg_widget("Infobar NG: letras", 0,
                        lyrics_widget_create, "infobar_lyrics", NULL);
}

void infobar_widget_unregister(ddb_gtkui_t *gtkui) {
    gtkui->w_unreg_widget("infobar_ng");
    gtkui->w_unreg_widget("infobar_lyrics");
    g_gtkui = NULL;
}
