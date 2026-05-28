# env-to-ini

Convert .env files to INI format from the command line.

## Features

- Parse .env files with KEY=VALUE format
- Strip quotes and export prefix
- Optional section header with `-s` flag
- Read from file or stdin
- Single binary, no dependencies

## Install

```bash
go install github.com/TataneSan/env-to-ini@latest
```

Or build from source:

```bash
git clone https://github.com/TataneSan/env-to-ini.git
cd env-to-ini
go build -o env-to-ini .
```

## Usage

```bash
env-to-ini [file.env] [-s SECTION]
```

Reads from stdin if no file provided.

### Examples

Convert a .env file:
```bash
env-to-ini config.env
```

From stdin:
```bash
cat config.env | env-to-ini
```

With section header:
```bash
env-to-ini -s database config.env
```

### Input (.env)

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME="myapp"
export DEBUG=true
```

### Output (INI)

```
DB_HOST = localhost
DB_PORT = 5432
DB_NAME = myapp
DEBUG = true
```

With `-s database`:
```
[database]
DB_HOST = localhost
DB_PORT = 5432
DB_NAME = myapp
DEBUG = true
```

## Exit Codes

| Code | Meaning                    |
|------|----------------------------|
| 0    | Success                    |
| 1    | File or parse error        |

## License

MIT
