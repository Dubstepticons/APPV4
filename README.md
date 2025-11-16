# APPV4 Trading Application

## Environment Variables

### Logging Configuration

#### DEBUG_LOGS
Control debug log output visibility.

- **Default**: `0` (debug logs hidden)
- **Values**:
  - `0` - Show only INFO, WARNING, ERROR logs
  - `1` - Show all logs including DEBUG level

**Usage:**

Windows PowerShell:
```powershell
$env:DEBUG_LOGS=1; python main.py
```

Windows CMD:
```cmd
set DEBUG_LOGS=1 && python main.py
```

Linux/Mac:
```bash
DEBUG_LOGS=1 python main.py
```

#### QUIET_STARTUP
Suppress debug logs during startup (legacy option, use DEBUG_LOGS instead).

- **Default**: `0`
- **Values**: `0` or `1`

### Other Environment Variables

#### USE_NEW_PANEL2
Enable the new Panel2 architecture.

- **Default**: `0`
- **Values**: `0` or `1`

**Usage:**
```powershell
$env:USE_NEW_PANEL2=1; python main.py
```

#### DEBUG_DTC
Enable detailed DTC protocol debugging.

- **Default**: `0`
- **Values**: `0` or `1`

## Running the Application

Normal mode (INFO logs only):
```powershell
python main.py
```

Debug mode (all logs):
```powershell
$env:DEBUG_LOGS=1; python main.py
```

With new Panel2 architecture:
```powershell
$env:USE_NEW_PANEL2=1; python main.py
```
