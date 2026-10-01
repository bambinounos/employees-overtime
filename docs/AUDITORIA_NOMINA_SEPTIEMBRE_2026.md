# Auditoría y Ajustes de Nómina - Septiembre 2026

**Fecha:** 30 de Septiembre de 2026  
**Sistema:** Employee Salary & Overtime Management (`employees-overtime`)  
**Servidor:** Producción VPS Oracle Cloud ARM (`152.70.126.0`)  

---

## 1. Resumen Ejecutivo de Intervenciones

Durante el cierre de nómina de Septiembre 2026 se detectaron y resolvieron 3 incidencias técnicas críticas:

1. **Resolución de Autor en Webhook de Facturación Dolibarr (`BILL_VALIDATE`)**:
   - **Problema:** Dolibarr enviaba `fk_user_author: null` en facturas generadas a partir de pedidos o proformas previas, dejando las facturas sin vendedor asignado (`employee: null`). Esto provocaba que los vendedores no recibieran sus comisiones de ventas devengadas.
   - **Solución implementada:** Parche en `employees/api_views.py` para consultar la API REST de Dolibarr (`/orders/{fk_commande}` y `/proposals/{fk_propal}`) y heredar el autor original del documento comercial.
   - **Commit:** `fb9a8db`.
   - **Resultado:** Se reconciliaron las facturas huérfanas en el VPS, acreditando a Ángel Vega **$51.23** de comisiones de ventas netas.

2. **Aclaración en Visualización de Reglas de Puntualidad y KPIs `count_lt`**:
   - **Problema:** En el dashboard del empleado y en las sugerencias automáticas de bonos, los KPIs de tipo "menor que" (`count_lt`), como Puntualidad (meta < 2 atrasos), mostraban el texto confuso `"menos de 2"`, generando dudas sobre si se permitían 1 o 2 atrasos.
   - **Solución implementada:** Modificación en `employees/views.py` y `employees/sugerencias.py` para formatear la condición como `"máximo 1"` (es decir, `meta - 1`).
   - **Commit:** `ef39d51`.

3. **Depuración de Tareas Duplicadas de Redes Sociales (KPI 7) y Auditoría del IPAC (KPI 8)**:
   - **Problema:** Una duplicación de recurrencias (plantilla antigua `ID 502` y nueva `ID 740`) provocó que del 8 al 30 de septiembre se generaran dos tareas diarias de "Subir estados y publicaciones". El empleado completó ambas en el mismo minuto, inflando las tareas a tiempo de 31 a 38 y el IPAC de 1.27 a 1.59.
   - **Solución implementada:**
     - Limpieza de las 23 tareas duplicadas en PostgreSQL del VPS, conservando la tarea completada a tiempo de cada día.
     - Confirmación de que la plantilla `ID 502` está inactiva y la plantilla `ID 740` sigue activa para Octubre (1 tarea diaria sin duplicados).
     - Recálculo del IPAC real: **1.27** (supera la meta de $\ge 1.20$ de forma legítima).

---

## 2. Auditoría Detallada del IPAC (Ángel Vega)

$$\text{IPAC} = \frac{\text{Tareas a tiempo} \times \text{Factor de Calidad}}{\text{Días hábiles (22)}}$$

### Métricas de Septiembre 2026 tras depuración:
* **Días hábiles laborables:** 22 días (lunes a viernes).
* **Total de tareas completadas:** 59 tareas (34 de otros KPIs + 25 de estados).
* **Tareas completadas a tiempo:** 31 tareas (15 de otros KPIs + 16 de estados).
* **Errores de calidad registrados:** 6 errores (2 disciplina, 2 calidad de productos, 2 atrasos).
* **Factor de Calidad:** $1 - (6 / 59) = \mathbf{0.8983}$.
* **IPAC Real:**
  $$\text{IPAC} = \frac{31 \times 0.8983}{22} = \mathbf{1.27}$$
* **Meta requerida:** $\ge 1.20$.
* **Estado:** **Cumple legítimamente (Gana bono de $50.00)**.

---

## 3. Estado Final de Liquidación (Septiembre 2026)

| Concepto | Detalle | Monto ($ USD) |
| :--- | :--- | :---: |
| **Sueldo Base por Horas Trabajadas** | 24 días laborados (192 horas) | $698.40 |
| **Horas Extras** | 31.5 horas al 50% de recargo | $171.87 |
| **Comisiones de Ventas** | Facturas pagadas en Dolibarr reconciliadas | $51.23 |
| **Bono Productividad General (KPI 1)** | 96.97% cumplido (Meta $\ge 95\%$) | $50.00 |
| **Bono Estados y Redes (KPI 7)** | 25 tareas completadas (Meta $\ge 24$) | $30.00 |
| **Bono IPAC (KPI 8)** | 1.27 índice alcanzado (Meta $\ge 1.20$) | $50.00 |
| **Bono Creación de Productos (KPI 10)** | 11 productos creados (Meta $\ge 10$) | $20.00 |
| **Total Neto a Pagar** | | **$1,071.50** |

---

## 4. Estado de Producción y Git

* **Rama:** `main`
* **Último Commit:** `ef39d51` (incluye parche Dolibarr y visualización Puntualidad).
* **Servicio:** `gunicorn` reiniciado y respondiendo en `https://salarios.hellbam.com`.
* **Próxima Generación:** Octubre inicia de forma limpia con solo la recurrencia `ID 740` activa.
