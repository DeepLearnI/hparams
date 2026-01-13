# HParams VSCode Extension

Syntax highlighting for `hparams.cfg` files with type hint support.

## Features

- Syntax highlighting for type-annotated configs: `batch_size: int = 32`
- Support for union types: `value: int | str | None`
- Highlighting for sections, comments, numbers, booleans, lists, dicts
- Comment toggling with `Cmd+/` (Mac) or `Ctrl+/` (Windows/Linux)

## Installation

Copy the extension to your VSCode extensions folder:

```bash
# Linux / WSL / Remote SSH
cp -r editors/vscode ~/.vscode-server/extensions/hparams-syntax

# macOS
cp -r editors/vscode ~/.vscode/extensions/hparams-syntax

# Windows (PowerShell)
Copy-Item -Recurse editors/vscode $env:USERPROFILE\.vscode\extensions\hparams-syntax
```

Then reload VSCode (`Cmd+Shift+P` → "Developer: Reload Window").

## Example

```ini
[model]
# Architecture settings
architecture: str = resnet50
num_layers: int = 50
dropout: float = 0.1
use_cuda: bool = True
layer_sizes: list[int] = [64, 128, 256]
optional_param: int | None = None
```
