# Guia de Configuracion de KPIs

## Tipos de KPI

Hay dos formas de evaluar un KPI:

1. **Por Internal Code** — logica especial conectada a datos de Dolibarr
2. **Por Measurement Type** — logica generica basada en tareas o entradas manuales

Si un KPI tiene `internal_code`, este tiene **prioridad** sobre el `measurement_type`.

---

## KPIs con Internal Code

### SALES_EFFECTIVENESS (Efectividad de Ventas)

**Que mide:** Porcentaje de proformas que se convirtieron en facturas en el mes.

**Formula:** `(Facturas con proforma / Total proformas del mes) x 100`

**Datos:** Viene automaticamente de Dolibarr via webhooks (PROPAL_VALIDATE y BILL_VALIDATE).

**Configuracion en Admin:**

| Campo | Valor | Explicacion |
|-------|-------|-------------|
| Name | Efectividad de Ventas | Nombre descriptivo |
| Measurement Type | Percentage | Resultado es un porcentaje |
| Internal Code | SALES_EFFECTIVENESS | Activa la logica especial |
| Target Value | 35 | Meta: 35% de conversion |
| Min Volume Threshold | 30 | Minimo 30 proformas para que el KPI se active |
| Is Warning KPI | No | No es disciplinario |

**Ejemplo practico:**

```
Empleado Juan en Marzo 2026:
- Creo 40 proformas en Dolibarr
- De esas, 20 se convirtieron en facturas (con origin_proforma_id)

Calculo:
1. total_proformas = 40 (>= threshold de 30) ✓ Se activa
2. invoices_count = 20
3. actual_value = (20 / 40) x 100 = 50%
4. 50% >= target 35% → META CUMPLIDA
5. Se busca el tier de bono mas alto alcanzado
```

**Si Juan solo hubiera hecho 10 proformas:**
```
total_proformas = 10 (< threshold de 30) → actual_value = 0%
El KPI no se activa. Esto previene fraude: 1 proforma + 1 factura = 100%
pero no es significativo.
```

**Tiers de bono (ejemplo):**

| Threshold | Bono | Descripcion |
|-----------|------|-------------|
| 35 | $100 | Conversion basica |
| 50 | $200 | Buena conversion |
| 75 | $400 | Excelente conversion |
| 90 | $700 | Conversion excepcional |

Si Juan tiene 50% → alcanza el tier de 50 → gana **$200** (no acumulativo, toma el mas alto).

**Nota importante:** Este KPI solo mide el flujo Proforma → Factura. Las ventas directas
(Pedido → Factura sin proforma) no afectan este KPI — se cuentan solo en comisiones.

---

### PRODUCT_CREATION (Creacion de Productos)

**Que mide:** Cantidad de productos unicos creados en Dolibarr este mes.

**Formula:** `Conteo de ProductCreationLog donde is_suspect_duplicate = False`

**Datos:** Viene automaticamente de Dolibarr via webhook (PRODUCT_CREATE).

**Anti-fraude:** Si un empleado crea el mismo SKU dos veces en el mismo mes,
la segunda creacion se marca como `is_suspect_duplicate = True` y NO cuenta para el bono.

**Configuracion en Admin:**

| Campo | Valor | Explicacion |
|-------|-------|-------------|
| Name | Creacion de Productos | Nombre descriptivo |
| Measurement Type | Count (Greater Than) | Mas productos = mejor |
| Internal Code | PRODUCT_CREATION | Activa la logica especial |
| Target Value | 5 | Meta: 5 productos/mes |
| Min Volume Threshold | 0 | No aplica para este KPI |
| Is Warning KPI | No | No es disciplinario |

**Ejemplo practico:**

```
Empleada Maria en Marzo 2026:
- Creo 12 productos en Dolibarr
- 2 tenian el mismo SKU que otro producto del mismo mes → marcados como duplicados

Calculo:
1. Total creados = 12
2. Duplicados excluidos = 2
3. actual_value = 10 productos validos
4. 10 >= target 5 → META CUMPLIDA
5. Se busca el tier de bono mas alto alcanzado
```

**Tiers de bono (ejemplo):**

| Threshold | Bono | Descripcion |
|-----------|------|-------------|
| 5 | $20 | Meta basica |
| 10 | $40 | Buena produccion |
| 20 | $60 | Alta produccion |

Maria con 10 productos → alcanza tier de 10 → gana **$40**.

---

## KPIs sin Internal Code (por Measurement Type)

Estos KPIs usan logica generica. No se conectan a Dolibarr.

### Percentage (Porcentaje)

**Ejemplo:** Productividad General

**Que mide:** `(Tareas completadas en "Hecho" / Total tareas asignadas) x 100`

**Fuente de datos:** Tablero de tareas (`Task` con `kpi` asignado).

| Campo | Valor |
|-------|-------|
| Measurement Type | Percentage |
| Internal Code | (vacio) |
| Target Value | 95 |

```
Empleado tiene 20 tareas asignadas en marzo
18 estan en lista "Hecho" con completed_at
actual_value = (18/20) x 100 = 90%
90% < 95% → META NO CUMPLIDA
```

---

### Count (Less Than) — Menos es mejor

**Ejemplo:** Calidad Administrativa, Disciplina, Puntualidad

**Que mide:** Conteo de errores/faltas. El empleado debe tener MENOS que el target.

**Fuente de datos:** Entradas manuales (`ManualKpiEntry`). Un supervisor registra errores.

| Campo | Valor |
|-------|-------|
| Measurement Type | Count (Less Than) |
| Internal Code | (vacio) |
| Target Value | 3 |

```
Empleado tuvo 2 errores administrativos en marzo
actual_value = 2
2 < 3 → META CUMPLIDA (menos errores que el maximo permitido)
```

**Para Puntualidad:**

| Campo | Valor |
|-------|-------|
| Target Value | 1 |

```
0 llegadas tarde → 0 < 1 → META CUMPLIDA
2 llegadas tarde → 2 >= 1 → META NO CUMPLIDA
```

---

### Count (Greater Than) — Mas es mejor

**Ejemplo:** Gestion Comercial Publica, Envio de estados en redes sociales, E-commerce

**Que mide:** Conteo de tareas completadas. El empleado debe tener MAS que el target.

**Fuente de datos:** Tareas completadas (`Task` con `completed_at` en el mes).

| Campo | Valor |
|-------|-------|
| Measurement Type | Count (Greater Than) |
| Internal Code | (vacio) |
| Target Value | 2 |

```
Empleado completo 3 ofertas publicas en marzo
actual_value = 3
3 >= 2 → META CUMPLIDA
```

---

### Composite IPAC

**Ejemplo:** Indice de Productividad Ajustado por Calidad

**Que mide:** Formula compuesta:
`IPAC = (Tareas completadas x Factor puntualidad x Factor calidad) / Dias habiles del mes`

El resultado son **tareas efectivas por dia habil**: cuantas tareas
completadas a tiempo y sin errores entrega el empleado por cada dia laboral.
El factor puntualidad solo considera tareas con fecha de vencimiento
(`completada el mismo dia o antes`), y el factor calidad descuenta los
errores registrados en KPIs count_lt.

**Nota (2026-09):** solo cuentan las tareas **con fecha de vencimiento**.
Una tarea sin `due_date` no acredita productividad: antes contaba en el
numerador pero se excluia del factor puntualidad, inflando el indice sin
riesgo de atraso. Completa siempre la fecha de vencimiento al crear
tareas.

**Nota (2026-09):** la version original dividia por el tiempo promedio
creado->completado en horas. Eso media tiempo de cola (la tarea esperando
en el tablero), castigaba crear tareas con anticipacion y hacia el target
inalcanzable (maximo historico 0.46 contra target 5). Ahora divide por
dias habiles; para el mes en curso usa los dias habiles transcurridos a
la fecha, de modo que el indice sea legible a mitad de mes.

**Control anti-gaming (2026-09):** crear, editar o eliminar tareas esta
reservado a supervisores (superusers, ej. RH desde el admin de Django).
Los empleados solo pueden mover tareas dentro de su tablero (asi las
completan). Esto evita que un empleado se auto-asigne tareas triviales
para inflar su IPAC o que edite la fecha de vencimiento de una tarea ya
completada tarde.

| Campo | Valor |
|-------|-------|
| Measurement Type | Composite IPAC |
| Internal Code | (vacio) |
| Target Value | calibrar segun escala nueva (ver abajo) |

Este KPI se calcula automaticamente desde las tareas del tablero.

**Calibracion del target:** con la formula nueva, un empleado que completa
~1 tarea efectiva por dia habil ronda IPAC 1.0. Fija el target en funcion
de la distribucion real de tu equipo (ej: 1.20 hace que solo los mejores
meses cobren).

---

## Como asignar KPIs a empleados

Los KPIs se asignan a traves de **Job Profiles** (Perfiles de Puesto):

1. Ve a `/admin/employees/jobprofile/`
2. Crea o edita un perfil (ej: "Vendedor", "Administrativo", "Digitalizador")
3. En el campo **KPIs**, selecciona los KPIs que aplican a ese perfil
4. Marca **Earns Commissions** si el perfil gana comisiones por ventas
5. Asigna el perfil al empleado en `/admin/employees/employee/`

**Ejemplo de perfiles:**

| Perfil | KPIs asignados | Comisiones |
|--------|---------------|:---:|
| Vendedor | Efectividad de Ventas, Productividad, Puntualidad | Si |
| Digitalizador | Creacion de Productos, Productividad, Calidad | No |
| Administrativo | Productividad, Calidad Administrativa, Puntualidad | No |
| Comercial | Gestion Comercial, E-commerce, Redes Sociales, Productividad | Si |

---

## Tiers de Bono vs BonusRule

Hay dos formas de configurar el bono por KPI:

### BonusRule (simple — todo o nada)
- Si cumple el target → gana el bono fijo
- Si no cumple → $0

### KPI Bonus Tiers (escalonado — recomendado)
- Multiples niveles de bono segun el valor alcanzado
- El sistema toma el **tier mas alto alcanzado**, no los acumula
- Si ambos existen (BonusRule + Tiers), toma el **mayor** de los dos

**Ejemplo con tiers:**
```
Target Value: 5
Tiers:
  5 productos → $20
  10 productos → $40
  20 productos → $60

Si empleado crea 15 productos:
  Alcanza tier 5 ($20) ✓
  Alcanza tier 10 ($40) ✓
  No alcanza tier 20
  → Gana $40 (el mas alto alcanzado)
```

### Como se comparan los umbrales

- KPIs "mas es mejor" (percentage, count_gt, internal codes): el tier se alcanza
  con valor **igual o mayor** al threshold. Con exactamente 10 productos ya se
  gana el tier de 10.
- KPIs "menos es mejor" (count_lt): el tier se alcanza con valor **igual o
  menor** al threshold (premia a los que cometen menos errores).

### Solo tiers, sin BonusRule (configuracion valida)

Si un KPI tiene tiers pero **ninguna BonusRule**, el `Target Value` no paga
dinero por si solo — el bono lo deciden unicamente los tiers. El campo sigue
siendo obligatorio en el formulario; se recomienda ponerle el mismo valor del
tier mas bajo, para que el "✓ meta cumplida" del dashboard coincida con los
meses en que si hay bono.

**Advertencia:** nunca configures `Target Value = 0` en un KPI "mas es mejor"
que SI tenga BonusRule: la condicion `valor >= 0` se cumple siempre y pagaria
el bono todos los meses, aun sin actividad.

**Nota sobre `Min Volume Threshold`:** solo tiene efecto en el KPI con internal
code `SALES_EFFECTIVENESS`. En cualquier otro KPI se guarda pero se ignora —
dejalo en 0.

---

## Cuando se recalculan los bonos

Los reportes y dashboards muestran la **foto del ultimo calculo** guardado
(`EmployeePerformanceRecord`). Guardar o editar un KPI, sus tiers o sus
BonusRules **no recalcula nada** por si solo.

El recalculo de un mes ocurre cuando:

1. Un admin consulta el salario del empleado:
   `/employees/<id>/salary/?year=YYYY&month=M`
2. El empleado abre **Mi Panel** en ese mes.
3. Se generan los recibos de nomina del mes.
4. Corre el cron nocturno (si esta instalado segun `scripts/crontab.example`).

Detalles a tener en cuenta:

- La pagina `/reports/` resume el **mes anterior**, no el actual. Si cambiaste
  la configuracion y quieres ver el efecto ahi, recalcula ese mes (punto 1) y
  recarga el reporte.
- Los **recibos de nomina ya emitidos quedan congelados** y no cambian aunque
  se recalcule — es intencional, son el registro de lo realmente pagado.

---

## Comisiones (independiente de KPIs)

Las comisiones se configuran por empleado, no por KPI:

1. Ve a `/admin/employees/employee/`
2. Edita el empleado
3. Pon el **Commission Percentage** (ej: 5.00 = 5%)
4. Maximo permitido: 100%

La comision se calcula sobre ventas netas **cobradas**:
```
Comision = (Facturas cobradas este mes - Notas de credito) x Porcentaje / 100
```

Las facturas sin cobrar aparecen como **comision provisional** (informativa, no se paga).

---

## Resumen de fuentes de datos

| KPI / Concepto | Fuente | Automatico |
|---------------|--------|:---:|
| SALES_EFFECTIVENESS | Dolibarr → webhooks | Si |
| PRODUCT_CREATION | Dolibarr → webhooks | Si |
| Comisiones | Dolibarr → webhooks + pagos | Si |
| Productividad General | Tablero de tareas | Si |
| IPAC | Tablero de tareas | Si |
| Gestion Comercial | Tareas completadas | Si |
| Calidad Administrativa | ManualKpiEntry | Manual |
| Puntualidad | ManualKpiEntry | Manual |
| Disciplina | ManualKpiEntry | Manual |
