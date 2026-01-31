---
trigger: always_on
---

# DBManager Code Guide

## Project Overview

DBManager è un tool CLI per la gestione di backup database multi-provider (PostgreSQL, MySQL, SQL Server) con supporto S3.

## Project Structure

```
dbmanager/
├── main.py              # Entry point CLI (minimale)
├── config.py            # Gestione config.json
├── cli/                 # Moduli CLI (max 500 linee per file)
│   ├── __init__.py      # Shared state (console, manager)
│   ├── database.py      # Menu e wizard database
│   ├── s3.py            # Menu e wizard S3
│   ├── schedule.py      # Menu scheduling
│   └── settings.py      # Menu settings
├── core/                # Business logic
│   ├── manager.py       # DBManager principale
│   ├── bucket_manager.py
│   ├── bucket_migrator.py
│   ├── config_sync.py
│   ├── s3_storage.py
│   ├── cron.py
│   └── providers/       # Provider database
│       ├── base.py      # Abstract base class
│       ├── postgres.py
│       ├── mysql.py
│       └── sqlserver.py
├── utils/
│   └── ui.py            # Helper UI (print_*, get_*)
├── data/                # Volume persistente
│   ├── config.json      # Configurazione
│   └── backups/         # Backup locali
└── test/                # Test infrastructure
    └── s3/              # Docker compose per Minio/Garage
```

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

## Dependencies

### Core
- `typer` - CLI framework
- `rich` - Console output formatting
- `InquirerPy` - Interactive prompts
- `boto3` - S3 storage

### Database Clients
- `psycopg2-binary` - PostgreSQL
- `mysql-connector-python` - MySQL  
- `pymssql` - SQL Server

## Docker

### Build & Run
```bash
docker-compose up -d --build
docker attach dbmanager
```

### Rebuild after changes
```bash
docker-compose up -d --build
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

## Testing

### S3 Testing
```bash
cd test/s3
docker-compose -f docker-compose-minio.yml up -d
```

Poi configura bucket in app:
- Endpoint: `http://host.docker.internal:9000`
- Access Key: `minioadmin`
- Secret Key: `minioadmin`

## Configuration

### config.json Structure
```json
{
  "databases": [
    {
      "id": 1,
      "name": "My DB",
      "provider": "postgres",
      "params": {...},
      "retention": 5,
      "s3_enabled": true,
      "s3_bucket_id": 1,
      "s3_retention": 10
    }
  ],
  "s3_buckets": [...],
  "config_sync_bucket_id": null
}
```

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
