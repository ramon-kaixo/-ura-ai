# `core/code_indexer.py`

- **Language:** python
- **Chunks:** 17

## Symbols

### class: `_PythonParser`
- Line: 55

class _PythonParser:
Methods: __init__, parse, _module_docstring, _classes, _functions, _imports

### class: `_GenericParser`
- Line: 97

class _GenericParser:
Methods: __init__, parse

### function: `_sha256`
- Line: 23

def _sha256(filepath):

### function: `_should_exclude`
- Line: 30

def _should_exclude(path, repo_root):

### function: `_chromadb_available`
- Line: 45

def _chromadb_available():

### function: `_get_collection`
- Line: 49

def _get_collection():

### function: `_load_manifest`
- Line: 114

def _load_manifest():

### function: `_save_manifest`
- Line: 120

def _save_manifest(manifest):

### function: `_collect_files`
- Line: 124

def _collect_files(root):

### function: `_extract_chunks`
- Line: 132

def _extract_chunks(rel_path, filepath):

### function: `index_code`
- Line: 140

def index_code(force):

### function: `query_code`
- Line: 175

def query_code(question, top_k):

### function: `get_symbol_info`
- Line: 190

def get_symbol_info(symbol):

### function: `generate_wiki`
- Line: 198

def generate_wiki(output_dir):

### function: `cli_main`
- Line: 229

def cli_main():

## Module Overview

Code Indexer — AST-based code indexer with ChromaDB for URA.

## Imports

```
argparse
ast
chromadb
contextlib
datetime.datetime
hashlib
importlib.util
json
logging
pathlib.Path
sys
time
typing.Any
typing.Optional
```
