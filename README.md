# env-to-ini

Convertisseur de fichiers `.env` vers le format INI en ligne de commande.

Transforme les variables d'environnement au format `KEY=VALUE` en format INI classique `key = value`.

## Installation

```bash
go install github.com/TataneSan/env-to-ini@latest
```

Ou compiler directement :

```bash
git clone https://github.com/TataneSan/env-to-ini.git
cd env-to-ini
go build -o env-to-ini .
```

## Usage

```bash
# Entrée fichier, sortie stdout
env-to-ini -i .env

# Entrée fichier, sortie fichier
env-to-ini -i .env -o config.ini

# Entrée stdin (pipe)
cat .env | env-to-ini
```

## Exemples

### Fichier .env d'entrée

```
# Base de données
DB_HOST=localhost
DB_PORT=5432
DB_NAME="myapp"
DB_USER='admin'
API_KEY=sk-123456789
DEBUG=true
```

### Commande

```bash
env-to-ini -i .env
```

### Fichier INI de sortie

```
# Base de données
DB_HOST = localhost
DB_PORT = 5432
DB_NAME = myapp
DB_USER = admin
API_KEY = sk-123456789
DEBUG = true
```

## Options

| Option | Description | Défaut |
|--------|-------------|--------|
| `-i` | Fichier .env d'entrée (vide pour stdin) | `""` (stdin) |
| `-o` | Fichier INI de sortie (vide pour stdout) | `""` (stdout) |

## Comportement

- Les lignes de commentaire (`#`) sont conservées
- Les lignes vides sont conservées
- Les guillemets simples et doubles autour des valeurs sont retirés
- Les clés et valeurs sont trimmées des espaces superflus

## Cas d'utilisation

- Convertir des fichiers `.env` pour des outils qui n'acceptent que le format INI
- Migrer des configurations entre formats
- Générer des fichiers de configuration INI à partir de variables d'environnement

## Licence

MIT
