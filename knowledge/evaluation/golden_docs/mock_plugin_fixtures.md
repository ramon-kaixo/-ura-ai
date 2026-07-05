# Mock Plugins for Testing

Creating mock plugins for tests follows a standard pattern.

## Basic Mock Plugin

```python
class _SimplePlugin(PluginBase):
    def __init__(self, name: str = "simple"):
        super().__init__()
        self.manifest = PluginManifest(name=name, version="1.0.0")
        self.executed = False
    
    def execute(self, context=None):
        self.executed = True
        return {"result": "ok"}
```

## Mock with Hooks

```python
class _HookablePlugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.manifest = PluginManifest(
            name="hookable", hooks=["pre_ingest"]
        )
    
    def execute(self, context=None):
        return {}
    
    def on_pre_ingest(self, event):
        return event
```

## Failing Mock

```python
class _FailingPlugin(PluginBase):
    def execute(self, context=None):
        raise RuntimeError("intentional failure")
```

## Cancelling Mock

```python
class _CancellingPlugin(PluginBase):
    def on_pre_ingest(self, event):
        return None  # cancels the operation
```
