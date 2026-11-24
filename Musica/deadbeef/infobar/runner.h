#pragma once
#include <glib.h>

#define TAB_LYRICS  0
#define TAB_ARTIST  1
#define TAB_ALBUM   2
#define TAB_SIMILAR 3
#define TAB_LABEL   4
#define N_TABS      5

typedef void (*RunnerCallback)(int tab_id, const char *text, gint generation);

void runner_exec_async(const char *const *argv, int tab_id,
                       gint generation, RunnerCallback callback);
