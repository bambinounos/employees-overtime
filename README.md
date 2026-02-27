# Employees & Overtime Management System

Sistema integral basado en Django para la gestión de recursos humanos, seguimiento de tareas y evaluación del desempeño mediante KPIs y bonificaciones.

## Descripción General

Este proyecto es una solución completa para administrar empleados, calcular salarios (incluyendo horas extra), gestionar tareas diarias a través de un tablero Kanban, y medir el rendimiento del personal mediante indicadores clave (KPIs) y el Índice de Productividad Ajustado por Calidad (IPAC).

El sistema permite automatizar cálculos de bonos basados en reglas configurables y generar reportes estratégicos para la toma de decisiones.

## Funcionalidades Principales

### 1. Gestión de Empleados y Salarios
*   **Perfil del Empleado:** Gestión de información personal, fechas de contratación y terminación.
*   **Estado Activo/Inactivo:** Los empleados se desactivan automáticamente al establecer una fecha de fin de contrato (`end_date`), conservando su historial.
*   **Cálculo de Nómina:**
    *   Salario base configurable.
    *   Registro diario de horas trabajadas y horas extra (`WorkLog`).
    *   Cálculo automático de pagos basado en horas, horas extra (x1.5) y bonificaciones por desempeño.
    *   Soporte para bases de cálculo mensual, semanal o diaria.

### 2. Gestión de Tareas (Tablero Kanban)
*   **Tableros Personales:** Cada empleado tiene su propio tablero de tareas.
*   **Flujo de Trabajo:** Listas predeterminadas: "Pendiente", "En Progreso", "Hecho".
*   **Gestión de Tarjetas:**
    *   Creación de tareas con título, descripción, fecha de vencimiento y prioridad.
    *   **Subtareas (Checklist):** Listas de verificación dentro de cada tarea.
    *   **Comentarios:** Hilo de conversación en cada tarea.
    *   Movimiento de tareas entre listas (Drag & Drop en la UI, API `move` en el backend).
*   **Tareas Recurrentes:**
    *   Generación automática de instancias de tareas basadas en una plantilla (padre).
    *   Frecuencias soportadas: Diaria, Semanal, Mensual, Anual.
    *   Lógica inteligente que genera las tareas faltantes al visualizar el tablero.

### 3. Gestión del Rendimiento (KPIs y Bonos)
*   **Indicadores Clave (KPIs):**
    *   **Tipos de Medición:** Porcentaje, Conteo (Menor que), Conteo (Mayor que) y Compuesto (IPAC).
    *   **Metas:** Definición de valores objetivo para cada KPI.
    *   **KPIs de Advertencia:** Envío automático de correos electrónicos al registrar incidencias en KPIs marcados como disciplinarios.
*   **Índice IPAC (Índice de Productividad Ajustado por Calidad):**
    *   Fórmula compleja que evalúa:
        *   Volumen de tareas completadas.
        *   Factor de Puntualidad (tareas a tiempo vs. total con vencimiento).
        *   Factor de Calidad (basado en errores registrados manualmente).
        *   Tiempo promedio de ejecución.
*   **Sistema de Bonificaciones:**
    *   Reglas configurables (`BonusRule`) que asignan montos monetarios al cumplir metas de KPIs específicos.
    *   Cálculo mensual automático reflejado en la nómina.
*   **Registros Manuales:** Bitácora para registrar eventos puntuales (ej. errores administrativos) que afectan los KPIs.

### 4. Reportes y Dashboards
*   **Dashboard Estratégico:**
    *   Visión global del mes anterior.
    *   KPIs agregados (Tareas completadas, % Puntualidad, IPAC promedio).
    *   Ranking de mejores empleados.
    *   Listado de empleados con advertencias.
    *   Gráfico de tendencia histórica del IPAC.
*   **Reporte de Rendimiento:**
    *   Vista detallada del desempeño por empleado.
    *   Exportación a CSV.
*   **Ranking de Empleados:** Tabla comparativa ordenada por cualquier KPI seleccionado.

### 5. Módulo de Evaluación Psicológica (PsicoEval v2)
*   **Batería Psicométrica Completa:** 343 preguntas distribuidas en 11 pruebas:
    *   Big Five (OCEAN) — 120 ítems
    *   Compromiso Organizacional (Allen & Meyer) — 48 ítems
    *   Escala de Obediencia/Conformidad — 40 ítems
    *   Prueba Situacional — 30 escenarios
    *   Frases Incompletas (Sacks) — 50 frases
    *   Matrices Progresivas — 30 patrones
    *   Test de Memoria de Trabajo — 10 niveles
    *   Escala de Deseabilidad Social — 12 ítems (detección de falseo)
    *   Pruebas proyectivas: Árbol (Koch), Persona bajo la Lluvia, Colores (Lüscher)
*   **Banco Ampliado + Selección Aleatoria:** Cada evaluación selecciona un subconjunto balanceado por dimensión, impidiendo filtración de respuestas entre candidatos.
*   **Control de Confiabilidad:**
    *   Escala de Deseabilidad Social para detectar respuestas socialmente deseables.
    *   Pares de consistencia (8 pares) para detectar respuestas aleatorias o incongruentes.
    *   Veredicto automático forzado a REVISION cuando la evaluación no es confiable.
*   **Evaluación Automatizada:** Cálculo de puntajes por dimensión, índices compuestos (responsabilidad, lealtad, obediencia) y veredicto automático (APTO / NO APTO / REVISION) basado en perfiles objetivo configurables.
*   **Pruebas Proyectivas:** Soporte para dibujos en canvas con datos de trazo y texto libre, con revisión manual del evaluador.
*   **Gestión de Sesiones:** Links de evaluación con token, expiración configurable, seguimiento de progreso y control de IP/user agent.

### 6. Configuración y Administración
*   **Panel de Administración (Django Admin):** Interfaz completa para gestionar todos los modelos.
*   **Configuración de Empresa:** Ajuste de horas base y modalidad de cálculo (Mensual/Semanal/Diaria).
*   **Personalización del Sitio:** Carga de Favicon personalizado.

## Instalación y Configuración

### Requisitos Previos (Ubuntu 24.04 Server)
Para desplegar la aplicación en un entorno de producción o desarrollo:

1.  **Actualizar el sistema:**
    ```bash
    sudo apt update && sudo apt upgrade -y
    ```

2.  **Instalar dependencias del sistema:**
    ```bash
    sudo apt install python3 python3-pip python3-venv postgresql postgresql-contrib gettext -y
    ```
    *Nota: `gettext` es necesario para compilar las traducciones.*

3.  **Configurar PostgreSQL:**
    ```bash
    sudo -u postgres psql
    ```
    Dentro de la consola `psql`:
    ```sql
    CREATE DATABASE salary_management;
    CREATE USER salary_manager WITH PASSWORD 'tu_contraseña';
    ALTER ROLE salary_manager SET client_encoding TO 'utf8';
    ALTER ROLE salary_manager SET default_transaction_isolation TO 'read committed';
    ALTER ROLE salary_manager SET timezone TO 'UTC';
    GRANT ALL PRIVILEGES ON DATABASE salary_management TO salary_manager;
    \q
    ```

### Despliegue del Código

1.  **Clonar el repositorio:**
    ```bash
    git clone <URL_DEL_REPOSITORIO>
    cd <NOMBRE_DEL_DIRECTORIO>
    ```

2.  **Configurar entorno virtual:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Configurar Base de Datos:**
    Edita `salary_management/settings.py` con tus credenciales:
    ```python
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': 'salary_management',
            'USER': 'salary_manager',
            'PASSWORD': 'tu_contraseña',
            'HOST': 'localhost',
            'PORT': '',
        }
    }
    ```

4.  **Migraciones y Usuario Administrador:**
    ```bash
    python3 manage.py migrate
    python3 manage.py createsuperuser
    ```

5.  **Compilar Traducciones:**
    ```bash
    python3 manage.py compilemessages
    ```
    *Si obtienes un error relacionado con `msgfmt`, asegúrate de haber instalado `gettext` como se indicó en los requisitos.*

6.  **Cargar Banco de Pruebas Psicológicas:**
    ```bash
    python3 manage.py seed_pruebas
    ```
    *Idempotente: se puede ejecutar múltiples veces sin duplicar datos.*

7.  **Ejecutar Servidor:**
    ```bash
    python3 manage.py runserver 0.0.0.0:8000
    ```
    Accede a `http://<IP_DE_TU_SERVIDOR>:8000`.

## API REST
El sistema expone una API REST para integración y operaciones del frontend:
*   `/api/tasks/`: CRUD de tareas.
*   `/api/boards/`: Acceso a tableros.
*   `/api/worklogs/`: Registro de horas.
*   `/api/kpi-history/<employee_id>/`: Historial de rendimiento para gráficos.
