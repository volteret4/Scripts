#pragma once
#include <gtk/gtk.h>
#include <deadbeef/deadbeef.h>
#include <deadbeef/gtkui_api.h>

void infobar_widget_register(ddb_gtkui_t *gtkui);
void infobar_widget_unregister(ddb_gtkui_t *gtkui);
gboolean infobar_update_for_track(DB_playItem_t *track);
gboolean infobar_clear(gpointer unused);
