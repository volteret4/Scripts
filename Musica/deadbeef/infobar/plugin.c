#include <stdlib.h>
#include <string.h>
#include <gtk/gtk.h>
#include <deadbeef/deadbeef.h>
#include <deadbeef/gtkui_api.h>
#include "ui.h"

DB_functions_t *deadbeef;
static ddb_gtkui_t *gtkui;

static int infobar_start(void)      { return 0; }
static int infobar_stop(void)       { return 0; }

static int infobar_connect(void) {
    gtkui = (ddb_gtkui_t *)deadbeef->plug_get_for_id(DDB_GTKUI_PLUGIN_ID);
    if (!gtkui) return -1;
    infobar_widget_register(gtkui);
    return 0;
}

static int infobar_disconnect(void) {
    if (gtkui) {
        infobar_widget_unregister(gtkui);
        gtkui = NULL;
    }
    return 0;
}

static int infobar_message(uint32_t id, uintptr_t ctx, uint32_t p1, uint32_t p2) {
    (void)p1; (void)p2;
    switch (id) {
    case DB_EV_SONGCHANGED: {
        ddb_event_trackchange_t *ev = (ddb_event_trackchange_t *)ctx;
        if (ev->to) {
            deadbeef->pl_item_ref(ev->to);
            g_idle_add((GSourceFunc)infobar_update_for_track, ev->to);
        } else {
            g_idle_add(infobar_clear, NULL);
        }
        break;
    }
    case DB_EV_SONGSTARTED: {
        ddb_event_track_t *ev = (ddb_event_track_t *)ctx;
        if (ev->track) {
            deadbeef->pl_item_ref(ev->track);
            g_idle_add((GSourceFunc)infobar_update_for_track, ev->track);
        }
        break;
    }
    }
    return 0;
}

static DB_misc_t plugin = {
    .plugin.api_vmajor    = DB_API_VERSION_MAJOR,
    .plugin.api_vminor    = DB_API_VERSION_MINOR,
    .plugin.version_major = 1,
    .plugin.version_minor = 0,
    .plugin.type          = DB_PLUGIN_MISC,
    .plugin.id            = "ddb_infobar_ng",
    .plugin.name          = "Infobar NG",
    .plugin.descr         = "Lyrics, artist bio, album info and similar tracks",
    .plugin.copyright     = "GPL-2.0",
    .plugin.start         = infobar_start,
    .plugin.stop          = infobar_stop,
    .plugin.connect       = infobar_connect,
    .plugin.disconnect    = infobar_disconnect,
    .plugin.message       = infobar_message,
};

DB_plugin_t *ddb_infobar_ng_load(DB_functions_t *api) {
    deadbeef = api;
    return DB_PLUGIN(&plugin);
}
