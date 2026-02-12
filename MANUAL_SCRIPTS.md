# Manual de Scripts de Versionado y Empaquetado

## Indice

1. [Estructura de Versiones](#1-estructura-de-versiones)
2. [bump_version.sh - Gestor de Versiones](#2-bump_versionsh---gestor-de-versiones)
3. [build_module_zip.sh - Empaquetador del Modulo](#3-build_module_zipsh---empaquetador-del-modulo)
4. [Flujos de Trabajo Comunes](#4-flujos-de-trabajo-comunes)
5. [Referencia Rapida](#5-referencia-rapida)

---

## 1. Estructura de Versiones

El proyecto maneja **dos versiones independientes** porque el servidor Django y el modulo Dolibarr son componentes separados que pueden evolucionar a ritmos distintos.

```
employees_overtime/
├── VERSION                          <- Version del servidor Django
├── salary_management/__init__.py    <- __version__ (Django)
│
├── dolibarr_module/
│   ├── VERSION                      <- Version del modulo Dolibarr
│   └── payroll_connect/
│       ├── core/modules/modPayrollConnect.class.php   <- $this->version (PHP)
│       └── core/triggers/interface_99_...Trigger.class.php  <- $this->version (PHP)
│
└── scripts/
    ├── bump_version.sh              <- Incrementar versiones
    └── build_module_zip.sh          <- Generar ZIP del modulo
```

### Formato de Version

Se usa **Semantic Versioning** (semver): `MAJOR.MINOR.PATCH`

| Tipo | Cuando usarlo | Ejemplo |
|---|---|---|
| `patch` | Correccion de bugs, ajustes menores | 1.1.0 -> 1.1.1 |
| `minor` | Nueva funcionalidad, compatible hacia atras | 1.1.0 -> 1.2.0 |
| `major` | Cambios que rompen compatibilidad | 1.1.0 -> 2.0.0 |

### Independencia de Versiones

Ejemplo real: puedes tener el servidor en version 2.3.1 y el modulo en 1.5.0 si el modulo no ha tenido tantos cambios.

```
Server (Django):  2.3.1
Module (Dolibarr): 1.5.0
```

---

## 2. bump_version.sh - Gestor de Versiones

### Ubicacion

```
scripts/bump_version.sh
```

### Sintaxis

```bash
./scripts/bump_version.sh <componente> <comando> [opciones]
```

### Componentes

| Componente | Archivos que modifica |
|---|---|
| `server` | `VERSION` + `salary_management/__init__.py` |
| `module` | `dolibarr_module/VERSION` + `modPayrollConnect.class.php` + trigger PHP |
| `status` | No modifica nada, solo muestra el estado actual |

### Comandos

| Comando | Descripcion | Ejemplo |
|---|---|---|
| `patch` | Incrementar version de parche | 1.1.0 -> 1.1.1 |
| `minor` | Incrementar version menor | 1.1.0 -> 1.2.0 |
| `major` | Incrementar version mayor | 1.1.0 -> 2.0.0 |
| `set <v>` | Establecer version exacta | set 3.0.0 |

### Opciones

| Opcion | Descripcion |
|---|---|
| `--no-commit` | No crear commit de git automaticamente |
| `--no-tag` | No crear tag de git automaticamente |
| `--help` | Mostrar ayuda |

### Ejemplos de Uso

#### Ver estado actual de ambas versiones

```bash
./scripts/bump_version.sh status
```

Salida esperada:

```
Project Versions

Server (Django):
  1.1.0   VERSION (source of truth)
  1.1.0   salary_management/__init__.py

Module (Dolibarr):
  1.1.0   dolibarr_module/VERSION (source of truth)
  1.1.0   modPayrollConnect.class.php
  1.1     interface_99_...Trigger.class.php
```

Si hay desincronizacion, mostrara una alerta `[DESYNC]`.

#### Incrementar version del servidor (bug fix)

```bash
./scripts/bump_version.sh server patch
```

Esto:
1. Cambia `VERSION` de 1.1.0 a 1.1.1
2. Cambia `__version__` en `salary_management/__init__.py` a `'1.1.1'`
3. Crea un commit: `chore(server): bump version to 1.1.1`
4. Crea un tag: `server/v1.1.1`

El modulo Dolibarr **no se ve afectado**.

#### Incrementar version del modulo (nueva funcionalidad)

```bash
./scripts/bump_version.sh module minor
```

Esto:
1. Cambia `dolibarr_module/VERSION` de 1.1.0 a 1.2.0
2. Cambia `$this->version` en `modPayrollConnect.class.php` a `'1.2.0'`
3. Cambia `$this->version` en el trigger a `'1.2'`
4. Crea un commit: `chore(module): bump version to 1.2.0`
5. Crea un tag: `module/v1.2.0`

El servidor Django **no se ve afectado**.

#### Establecer version exacta

```bash
./scripts/bump_version.sh module set 2.0.0
```

#### Incrementar sin commit ni tag (para revision antes de confirmar)

```bash
./scripts/bump_version.sh server minor --no-commit
```

Los archivos se modifican pero no se crea commit. Util para revisar los cambios antes de confirmar manualmente.

#### Incrementar sin tag (si no deseas marcar release aun)

```bash
./scripts/bump_version.sh module patch --no-tag
```

Se crea el commit pero sin tag de git.

### Que hace el script automaticamente

Cuando se ejecuta **sin** `--no-commit`:

1. Modifica los archivos de version del componente seleccionado
2. Ejecuta `git add` de los archivos modificados
3. Crea un commit con mensaje estandarizado: `chore(<componente>): bump version to X.Y.Z`
4. Crea un tag de git: `<componente>/vX.Y.Z` (a menos que uses `--no-tag`)

### Tags de Git

Los tags se crean con el formato `<componente>/vX.Y.Z`:

```
server/v1.1.1    <- Tag del servidor
module/v1.2.0    <- Tag del modulo
```

Para publicar los tags al remoto:

```bash
git push origin server/v1.1.1
git push origin module/v1.2.0

# O todos los tags a la vez:
git push origin --tags
```

---

## 3. build_module_zip.sh - Empaquetador del Modulo

### Ubicacion

```
scripts/build_module_zip.sh
```

### Sintaxis

```bash
./scripts/build_module_zip.sh [opciones]
```

### Opciones

| Opcion | Descripcion |
|---|---|
| `--check` | Validar archivos antes de construir el ZIP |
| `--help` | Mostrar ayuda |

### Salida

El ZIP se genera en:

```
dist/module_payroll_connect-<version>.zip
```

Donde `<version>` se lee de `dolibarr_module/VERSION`.

### Ejemplos de Uso

#### Generar ZIP directamente

```bash
./scripts/build_module_zip.sh
```

#### Validar y luego generar

```bash
./scripts/build_module_zip.sh --check
```

La validacion con `--check` verifica:

| Verificacion | Descripcion |
|---|---|
| Archivos requeridos | Los 4 archivos PHP principales deben existir |
| Archivos esperados | COPYING, langs, retry_queue, etc. (advertencia si faltan) |
| Sintaxis PHP | Ejecuta `php -l` en cada archivo PHP (requiere PHP instalado) |
| Consistencia de version | Compara version en el PHP vs `dolibarr_module/VERSION` |

### Estructura del ZIP

El ZIP generado contiene la estructura estandar de Dolibarr:

```
payroll_connect/
├── COPYING
├── admin/
│   ├── setup.php
│   └── retry_queue.php
├── core/
│   ├── boxes/
│   │   └── box_payroll_connect_status.php
│   ├── modules/
│   │   └── modPayrollConnect.class.php
│   └── triggers/
│       └── interface_99_modPayrollConnect_MyTrigger.class.php
├── img/
├── langs/
│   ├── en_US/payroll_connect.lang
│   └── es_ES/payroll_connect.lang
└── lib/
    └── payroll_connect.lib.php
```

### Instalar en Dolibarr

1. Abra Dolibarr como administrador.
2. Vaya a **Inicio > Admin > Modulos/Aplicaciones**.
3. Clic en **Desplegar/instalar un modulo externo**.
4. Suba el archivo `module_payroll_connect-X.Y.Z.zip`.
5. Active el modulo en la lista de modulos.

---

## 4. Flujos de Trabajo Comunes

### 4.1. Correccion de bug en el servidor

```bash
# 1. Hacer los cambios en el codigo
# 2. Probar los tests
python3 manage.py test

# 3. Bump version del servidor
./scripts/bump_version.sh server patch

# 4. Push
git push origin main
git push origin server/v1.1.1
```

### 4.2. Nueva funcionalidad en el modulo Dolibarr

```bash
# 1. Hacer los cambios en los archivos PHP
# 2. Bump version del modulo
./scripts/bump_version.sh module minor

# 3. Generar el ZIP
./scripts/build_module_zip.sh --check

# 4. Push + instalar ZIP en Dolibarr
git push origin main
git push origin module/v1.2.0
```

### 4.3. Release completa (servidor + modulo)

```bash
# 1. Verificar estado actual
./scripts/bump_version.sh status

# 2. Bump servidor
./scripts/bump_version.sh server minor

# 3. Bump modulo
./scripts/bump_version.sh module minor

# 4. Generar ZIP del modulo
./scripts/build_module_zip.sh --check

# 5. Push todo
git push origin main --tags
```

### 4.4. Hotfix urgente solo en servidor

```bash
# 1. Fix rapido en el codigo
# 2. Bump patch sin tag (para no marcar release formal)
./scripts/bump_version.sh server patch --no-tag

# 3. Push
git push origin main
```

### 4.5. Preparar version beta

```bash
# Establecer version beta manualmente
./scripts/bump_version.sh module set 2.0.0-beta.1

# Generar ZIP de prueba
./scripts/build_module_zip.sh
# Salida: dist/module_payroll_connect-2.0.0-beta.1.zip
```

---

## 5. Referencia Rapida

```bash
# ---- VERSION STATUS ----
./scripts/bump_version.sh status               # Ver ambas versiones

# ---- SERVIDOR DJANGO ----
./scripts/bump_version.sh server patch          # Bug fix:      1.1.0 -> 1.1.1
./scripts/bump_version.sh server minor          # Feature:      1.1.0 -> 1.2.0
./scripts/bump_version.sh server major          # Breaking:     1.1.0 -> 2.0.0
./scripts/bump_version.sh server set 3.0.0      # Set exacto

# ---- MODULO DOLIBARR ----
./scripts/bump_version.sh module patch          # Bug fix:      1.1.0 -> 1.1.1
./scripts/bump_version.sh module minor          # Feature:      1.1.0 -> 1.2.0
./scripts/bump_version.sh module major          # Breaking:     1.1.0 -> 2.0.0
./scripts/bump_version.sh module set 2.0.0      # Set exacto

# ---- OPCIONES ----
./scripts/bump_version.sh server patch --no-commit   # Sin commit
./scripts/bump_version.sh module minor --no-tag      # Sin tag git

# ---- GENERAR ZIP ----
./scripts/build_module_zip.sh                   # Generar ZIP
./scripts/build_module_zip.sh --check           # Validar + generar ZIP
```

### Archivos por Componente

| Componente | Archivo VERSION | Archivos actualizados |
|---|---|---|
| `server` | `VERSION` | `salary_management/__init__.py` |
| `module` | `dolibarr_module/VERSION` | `modPayrollConnect.class.php`, trigger PHP |

### Tags de Git

| Componente | Formato del tag | Ejemplo |
|---|---|---|
| `server` | `server/vX.Y.Z` | `server/v1.2.0` |
| `module` | `module/vX.Y.Z` | `module/v1.5.0` |
