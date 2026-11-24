#include "runner.h"
#include <glib.h>
#include <string.h>
#include <stdlib.h>

typedef struct {
    gchar       **argv;
    int           tab_id;
    gint          generation;
    RunnerCallback callback;
} RunnerArgs;

typedef struct {
    int           tab_id;
    gchar        *text;
    gint          generation;
    RunnerCallback callback;
} RunnerResult;

static gboolean runner_on_done_idle(gpointer data) {
    RunnerResult *res = (RunnerResult *)data;
    res->callback(res->tab_id, res->text, res->generation);
    g_free(res->text);
    g_free(res);
    return G_SOURCE_REMOVE;
}

static gpointer runner_thread_func(gpointer data) {
    RunnerArgs *args = (RunnerArgs *)data;

    gchar *out = NULL;
    gint   exit_status = 1;
    GError *gerr = NULL;

    g_spawn_sync(NULL,
                 args->argv,
                 NULL,
                 G_SPAWN_SEARCH_PATH | G_SPAWN_STDERR_TO_DEV_NULL,
                 NULL, NULL,
                 &out, NULL,
                 &exit_status, &gerr);

    const char *text = (exit_status == 0 && out && *out) ? out : "";

    RunnerResult *res = g_new(RunnerResult, 1);
    res->tab_id    = args->tab_id;
    res->text      = g_strdup(text);
    res->generation = args->generation;
    res->callback  = args->callback;

    g_idle_add(runner_on_done_idle, res);

    g_free(out);
    if (gerr) g_error_free(gerr);
    g_strfreev(args->argv);
    g_free(args);

    return NULL;
}

void runner_exec_async(const char *const *argv, int tab_id,
                       gint generation, RunnerCallback callback) {
    int argc = 0;
    while (argv[argc]) argc++;

    RunnerArgs *args = g_new(RunnerArgs, 1);
    args->argv       = g_new0(gchar *, argc + 1);
    for (int i = 0; i < argc; i++)
        args->argv[i] = g_strdup(argv[i]);
    args->tab_id    = tab_id;
    args->generation = generation;
    args->callback  = callback;

    g_thread_new("infobar_runner", runner_thread_func, args);
}
