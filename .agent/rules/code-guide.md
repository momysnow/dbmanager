---
trigger: always_on
---

# DBManager Code Guide

## Project Overview

DBManager è un tool CLI per la gestione di backup database multi-provider (PostgreSQL, MySQL, SQL Server) con supporto S3.

## Coding Standards

### File Size
- **Max 500 linee** per file Python
- Se supera, splitta in moduli separati

### Naming Conventions
- File: `snake_case.py`
- Classi: `PascalCase`
- Funzioni: `snake_case`
- Costanti: `UPPER_SNAKE_CASE`

### CLI Menu Pattern
```python
def some_menu():
    while True:
        print_header()
        console.print("\n[bold cyan]═══ Title ═══[/bold cyan]\n")
        
        choices = [
            Choice(value="action", name="Do Something"),
            Separator(),
            Choice(value="back", name="← Back"),
        ]
        
        action = get_selection("Menu Name", choices)
        
        if action == "back":
            break
        elif action == "action":
            do_something()
            get_input("Press Enter...")
```

### Menu Rules
- **Sempre includere "← Back"** in ogni sub-menu
- Usare `Separator()` per raggruppare opzioni
- `get_input("Press Enter...")` dopo azioni completate

### Wizard Pattern
```python
def add_something_wizard():
    print_header()
    console.print("\n[bold cyan]═══ Add Something ═══[/bold cyan]\n")
    
    # Input con validazione
    name = get_input("Name:")
    if not name:
        print_info("Cancelled")
        get_input("Press Enter...")
        return
    
    # Selezione con back option
    choices = [
        Choice(value="back", name="← Back"),
        Separator(),
        Choice(value="option1", name="Option 1"),
    ]
    selected = get_selection("Choose", choices)
    if selected == "back":
        return
    
    # Esegui azione
    try:
        result = do_action(name, selected)
        print_success(f"Created: {result}")
    except Exception as e:
        print_error(f"Failed: {e}")
    
    get_input("Press Enter...")
```

## Docker

### Build & Run
```bash
docker compose up -d --build
```

## Git Workflow

### Commit Messages
```
type: Short description

Longer explanation if needed.
```

Types:
- `feat:` - Nuova funzionalità
- `fix:` - Bug fix
- `refactor:` - Refactoring senza cambi funzionali
- `test:` - Test infrastructure
- `docs:` - Documentazione

### Commit Granularity
- Un commit per feature/fix logico
- Non mescolare refactoring con nuove feature

## Error Handling

```python
try:
    result = risky_operation()
    print_success("Done!")
except SpecificError as e:
    print_error(f"Specific issue: {e}")
except Exception as e:
    print_error(f"Unexpected error: {e}")
```

## UI Helpers (utils/ui.py)

| Function | Usage |
|----------|-------|
| `print_header()` | Clear screen + app banner |
| `print_success(msg)` | Green success message |
| `print_error(msg)` | Red error message |
| `print_info(msg)` | Yellow info message |
| `get_input(prompt, default)` | Text input |
| `get_confirm(prompt, default)` | Yes/No prompt |
| `get_selection(prompt, choices)` | Selection menu |