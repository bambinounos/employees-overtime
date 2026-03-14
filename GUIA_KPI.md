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
`IPAC = (Tareas completadas x Factor puntualidad x Factor calidad) / Promedio horas ejecucion`

| Campo | Valor |
|-------|-------|
| Measurement Type | Composite IPAC |
| Internal Code | (vacio) |
| Target Value | 5 |

Este KPI se calcula automaticamente desde las tareas del tablero.

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
