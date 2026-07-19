SYSTEM_STARTED = "system.started"
SYSTEM_SHUTDOWN = "system.shutdown"
SYSTEM_DEGRADED = "system.degraded"
SYSTEM_RESTORED = "system.restored"

PIPELINE_STARTED = "pipeline.started"
PIPELINE_COMPLETED = "pipeline.completed"
PIPELINE_FAILED = "pipeline.failed"
PIPELINE_BEFORE_PIPELINE = "pipeline.before_pipeline"
PIPELINE_AFTER_PIPELINE = "pipeline.after_pipeline"
PIPELINE_BEFORE_STAGE = "pipeline.before_stage"
PIPELINE_AFTER_STAGE = "pipeline.after_stage"

PLUGIN_LOADED = "plugin.loaded"
PLUGIN_UNLOADED = "plugin.unloaded"
PLUGIN_ERROR = "plugin.error"

EXECUTOR_STARTED = "executor.started"
EXECUTOR_COMPLETED = "executor.completed"

CONFIG_CHANGED = "config.changed"

HOOK_PREFIX = "plugin.hook."

HOOK_PIPELINE = frozenset(
    {
        "pre_ingest",
        "post_ingest",
        "pre_search",
        "post_search",
        "pre_index",
        "post_index",
    },
)

HOOK_SYSTEM = frozenset(
    {
        "on_startup",
        "on_shutdown",
        "on_degraded",
        "on_restore",
    },
)

HOOK_CLI = frozenset(
    {
        "pre_command",
        "post_command",
    },
)

ALL_HOOKS = HOOK_PIPELINE | HOOK_SYSTEM | HOOK_CLI
