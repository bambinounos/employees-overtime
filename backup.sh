#!/bin/bash

# ==============================================================================
# Script para la Creación de Copias de Seguridad
# ==============================================================================
#
# Descripción:
# Este script automatiza la creación de copias de seguridad para la aplicación
# de gestión de salarios. Realiza las siguientes acciones:
# 1. Crea un volcado (dump) de la base de datos PostgreSQL.
# 2. Comprime el volcado de la base de datos junto con los archivos de
#    configuración críticos en un único archivo .tar.gz.
# 3. Asigna un nombre al archivo de copia de seguridad con la fecha y hora.
# 4. Elimina las copias de seguridad con más de 7 días de antigüedad.
#
# Requisitos:
# - Estar ubicado en el directorio raíz del proyecto.
# - El usuario que ejecuta el script debe tener permisos para ejecutar `pg_dump`.
# - Se recomienda configurar un archivo ~/.pgpass para evitar ingresar la
#   contraseña de la base de datos de forma interactiva.
#
# ==============================================================================

# --- Variables de Configuración ---

# Nombre de la base de datos
DB_NAME="salary_management"

# Usuario de la base de datos
DB_USER="salary_manager"

# Directorio donde se guardarán las copias de seguridad
BACKUP_DIR="backups"

# Formato de fecha para el nombre del archivo de backup
DATE_FORMAT=$(date +"%Y-%m-%d_%H-%M-%S")

# Nombre del archivo de la copia de seguridad
BACKUP_FILENAME="backup_${DATE_FORMAT}.tar.gz"

# Ruta completa del archivo de copia de seguridad
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILENAME}"

# Archivo temporal para el volcado de la base de datos
DB_DUMP_FILE="${BACKUP_DIR}/db_dump.sql"

# Días a retener las copias de seguridad
RETENTION_DAYS=7

# Archivos de configuración a incluir en el backup
CONFIG_FILES=(
    "salary_management/settings.py"
    "wsgidav.conf"
)

# --- Lógica del Script ---

echo "--- Iniciando el proceso de copia de seguridad (${DATE_FORMAT}) ---"

# 1. Verificar que el directorio de backups existe
if [ ! -d "$BACKUP_DIR" ]; then
    echo "Error: El directorio de backups '$BACKUP_DIR' no existe."
    echo "Por favor, cree el directorio e intente de nuevo."
    exit 1
fi

# 2. Crear el volcado de la base de datos
echo "1. Creando volcado de la base de datos '${DB_NAME}'..."
pg_dump -U "${DB_USER}" -d "${DB_NAME}" -F c -b -v -f "${DB_DUMP_FILE}"

# Verificar si pg_dump tuvo éxito
if [ $? -ne 0 ]; then
    echo "Error: Falló la creación del volcado de la base de datos."
    rm -f "${DB_DUMP_FILE}" # Limpiar el archivo de volcado si falló
    exit 1
fi
echo "Volcado de la base de datos creado exitosamente en '${DB_DUMP_FILE}'."

# 3. Comprimir los archivos en un solo paquete
echo "2. Comprimiendo el volcado de la base de datos y los archivos de configuración..."
tar -czf "${BACKUP_PATH}" "${DB_DUMP_FILE}" "${CONFIG_FILES[@]}"

# Verificar si tar tuvo éxito
if [ $? -ne 0 ]; then
    echo "Error: Falló la compresión de los archivos de backup."
    rm -f "${DB_DUMP_FILE}" # Limpiar
    exit 1
fi
echo "Copia de seguridad creada exitosamente en '${BACKUP_PATH}'."

# 4. Limpiar el archivo de volcado temporal
rm -f "${DB_DUMP_FILE}"
echo "3. Archivo de volcado temporal eliminado."

# 5. Eliminar copias de seguridad antiguas
echo "4. Eliminando copias de seguridad con más de ${RETENTION_DAYS} días de antigüedad..."
find "${BACKUP_DIR}" -type f -name "backup_*.tar.gz" -mtime +${RETENTION_DAYS} -exec rm {} \;

echo "Proceso de limpieza completado."
echo "--- Proceso de copia de seguridad finalizado ---"

exit 0