# Plan (para construcción futura): Nómina legal ecuatoriana conviviendo con contratistas por factura

> **Estado**: planificación. NO se construye ahora. Este documento queda listo para
> arrancar la siguiente fase y para revisarlo con el contador. Todas las tasas legales
> (SBU, porcentajes IESS, retenciones, IVA) van **configurables**, nunca fijas en código,
> y deben validarse con el contador antes de usarse en producción.

## Context

Hoy el sistema (`employees-overtime`, Django 4.2 en prod) calcula una nómina **gerencial/variable**: sueldo base prorrateado por horas + horas extra (1.5× plano) + bono KPI + comisiones. No existe **nada** de la legislación laboral ecuatoriana (verificado: cero coincidencias de `decimo/iess/aporte/fondos/sbu/retencion` en todo el repo). Los empleados actuales de Hellbam son **por prestación de servicios (factura)**, por eso no ha hecho falta.

La empresa quiere estar lista para incorporar empleados en **relación de dependencia** (con IESS, décimos, fondos de reserva, horas extra legales) **sin dejar de manejar a los contratistas por factura**. Ambos regímenes deben convivir: cada persona se marca con su tipo de relación y el motor de nómina se ramifica.

Decisiones de negocio ya tomadas:
- **Décimos (13º y 14º)**: soportar **mensualizado y acumulado**, elegible por empleado.
- **Contratistas por factura**: la retención en la fuente es **configurable por contratista** (algunos aplican, otros no); modelar retención + IVA opcionales.
- **Horas extra (dependencia)**: recargos legales — suplementarias **25%** (diurnas) / **50%** (nocturnas), extraordinarias **100%** (fines de semana y feriados).

**Principio de diseño transversal**: se reutiliza el patrón de **snapshot inmutable** ya existente (`ReciboNomina.datos` congela el dict de `calculate_salary` vía `nomina.py::_jsonable`, y el PDF/planilla se renderizan del JSON congelado). Al añadir conceptos legales, el histórico queda protegido automáticamente. Todas las migraciones son **aditivas** (modelos nuevos + columnas nullable/con default), dependientes de `0029`, de bajo riesgo.

---

## Modelo de datos (transversal a las etapas)

### Discriminador y datos legales en `Employee` (models.py:57)
Campos nuevos (migración aditiva; los empleados actuales se marcan `servicios` por defecto → nada se rompe):
- `tipo_relacion` — choices `('dependencia','Relación de dependencia')`, `('servicios','Prestación de servicios')`; default `servicios`.
- `cedula` — `CharField` (validación de cédula ecuatoriana opcional).
- **Dependencia**: `region` (`sierra_amazonia` / `costa_galapagos`, define el mes del 14º), `numero_afiliacion_iess`, `aporta_iess` (bool, default True), `decimo_tercero_mensualizado` (bool), `decimo_cuarto_mensualizado` (bool). Fondos de reserva se derivan por antigüedad (helper, no campo).
- **Servicios/factura**: `ruc`, `aplica_retencion` (bool), `porcentaje_retencion_fuente` (Decimal, p.ej. 8/10/2 según código), `cobra_iva` (bool, default True).

### Nuevo modelo `ParametrosLegales` (por año)
`CompanySettings` es singleton sin dimensión temporal → no sirve. Se crea un modelo indexado por año:
- `year` (unique), `sbu` (salario básico unificado del año), `aporte_personal_pct` (9.45), `aporte_patronal_pct` (11.15), `fondos_reserva_pct` (8.33), `iva_pct` (15), `recargo_suplementaria_diurna_pct` (25), `recargo_suplementaria_nocturna_pct` (50), `recargo_extraordinaria_pct` (100).
- **Data migration** sembrando 2025 y 2026 (patrón de `0026_tipos_ausencia_default.py` con `RunPython` + `get_or_create`). **El SBU 2026 y los porcentajes se marcan para validar con el contador** antes de producción.
- Helper `ParametrosLegales.del_anio(year)` (fallback al más reciente si falta el año), estilo `CompanySettings.load()`.

#### Valores vigentes 2026 (investigados jul-2026 — cotejar con el contador antes de producción)
| Parámetro | Valor 2026 | Nota |
|---|---|---|
| SBU (salario básico unificado) | **$482,00/mes** | Vigente desde 1-ene-2026 (+$12 vs $470 de 2025). Base del décimo cuarto. |
| Aporte personal IESS (dependencia, sector privado) | **9,45%** | Descuento al trabajador (egreso del rol). |
| Aporte patronal IESS | **11,15%** | Lo paga el empleador (adicional, no se descuenta). Total IESS 20,60%. IECE/SECAP según cómo los registre el contador. |
| Fondos de reserva | **8,33%** (≈1/12) | A partir del mes 13 (tras el primer año); mensualizado o acumulado al IESS. |
| IVA general | **15%** | Confirmado por circular SRI dic-2025 para 2026 (la tarifa base de ley es 13%, el 15% se mantiene por decreto). |
| Horas extra suplementarias | **+25%** diurnas / **+50%** nocturnas | Código de Trabajo (estable). |
| Horas extra extraordinarias | **+100%** | Sábados, domingos y feriados. |
| Décimo tercero | 1/12 de la remuneración (dic–nov) | Mensualizado o acumulado (pago hasta 24-dic). |
| Décimo cuarto | 1 SBU = **$482** (proporcional) | Mes de pago según región (Sierra/Amazonía: ago; Costa/Galápagos: mar). |

**Retención en la fuente a contratistas** (Resolución SRI **NAC-DGERCGC26-00000009**, vigente desde 1-mar-2026) — por eso el porcentaje va **configurable por contratista**:
| Caso | % 2026 |
|---|---|
| Honorarios/servicios de **persona natural**, predomina el intelecto (con o sin título) | **10%** |
| Servicios profesionales de **sociedad** (requiere título) | **5%** |
| Servicios donde predomina la **mano de obra** | **3%** (subió desde 2%) |
| Adquisición de bienes muebles | 2% |

### Ramificación del motor `calculate_salary` (models.py:396)
Hoy suma 4 componentes y devuelve un dict de 14+ llaves. Se ramifica por `self.tipo_relacion`, devolviendo un dict con una llave `regime` que las capas de salida (PDF/planilla/Dolibarr) leen para saber qué mostrar:
- `regime='servicios'` → monto de honorarios + IVA (si `cobra_iva`) + retención (si `aplica_retencion`) → **neto a pagar**.
- `regime='dependencia'` → **rol de pagos**: ingresos (sueldo, horas extra legales, comisiones, bono KPI, décimos mensualizados y fondos de reserva si aplican) − egresos (aporte personal IESS, anticipos, préstamos) → **líquido a pagar**.

El `datos` JSON de `ReciboNomina` es flexible (JSONField) y absorbe ambas formas sin cambio de esquema. `report_pdf.py` y `exports.py` ramifican por `regime` (plantillas/columnas distintas por régimen), reutilizando el bloque de branding Hellbam (`report_pdf.py::_bloque_empresa`).

---

## Etapas de construcción

### Etapa 0 — Fundamentos y parámetros (base de todo)
- Campos nuevos en `Employee` + `ParametrosLegales` + data migration de tasas 2025/2026.
- Primer **ModelForm** de configuración en `employees/forms.py` (hoy solo existe `SolicitudAusenciaForm`) + pantalla para editar parámetros por año, extendiendo la vista `company_settings` (views.py:261) / admin.
- **Sin cambio de cálculo todavía**: solo estructura. Migración aditiva, todos marcados `servicios` → producción intacta.
- Admin: registrar `ParametrosLegales`; añadir los campos nuevos al `EmployeeAdmin` (admin.py:35).

### Etapa 1 — Rama de contratistas por factura (lo que usan HOY)
Mejora el flujo actual con manejo fiscal correcto (es el régimen real de Hellbam hoy):
- `calculate_salary` rama `servicios`: monto + IVA opcional + retención en la fuente opcional → neto.
- Salida: recibo/comprobante de honorarios (nueva rama en `report_pdf.py`); columnas de contratista en `exports.py` (`COLUMNAS_PLANILLA` se vuelve dependiente de régimen).
- **Dolibarr**: nueva función `crear_factura_proveedor` en `dolibarr_api.py` apuntando a `/api/index.php/supplierinvoices`; enrutar en `nomina.py::enviar_recibos_dolibarr` (línea ~112) según `tipo_relacion` (dependencia→`/salaries`, servicios→`/supplierinvoices`). **Verificar el endpoint contra el `/api/index.php/explorer` real** y permisos `fournisseur→facture` del usuario del DOLAPIKEY.

### Etapa 2 — Rol de pagos de dependencia (núcleo laboral)
- `calculate_salary` rama `dependencia`: ingresos − egresos → líquido.
  - **Horas extra legales**: distinguir tipo de hora extra. Añadir a `WorkLog` (models.py:489) el desglose (suplementaria diurna/nocturna, extraordinaria) o derivarlo de la fecha (fin de semana/feriado → 100%). Aplicar recargos de `ParametrosLegales`.
  - **Aporte personal IESS** (9.45% configurable) como egreso; **anticipos/préstamos** como egresos (modelo simple `DescuentoNomina` o reutilizar entradas manuales).
- Salida: **rol de pagos PDF** con formato legal (ingresos/egresos/líquido), reutilizando branding.
- Tests: cálculo correcto de aportes y recargos; inmutabilidad del snapshot.

### Etapa 3 — Décimos y fondos de reserva
- **Décimo tercero**: mensualizado → línea en el rol; acumulado → se **computa del histórico de recibos** (Dic–Nov) con un helper estilo `Employee.saldo_vacaciones` (no hace falta ledger nuevo), pago hasta el 24 dic.
- **Décimo cuarto**: basado en SBU; mensualizado o acumulado; mes de pago según `region` (Costa/Galápagos: marzo; Sierra/Amazonía: agosto).
- **Fondos de reserva**: 8.33% tras el primer año de trabajo (helper por antigüedad); mensualizado en el rol o acumulado al IESS.
- Tests: provisiones desde histórico, elegibilidad por antigüedad, ambos regímenes de pago.

### Etapa 4 — Reportes legales y cumplimiento (final / opcional)
- **Planilla de aportes IESS** (export para el sistema del IESS).
- **Comprobantes de retención** para contratistas.
- **Resumen anual de ingresos y retenciones** (base para el formulario 107).
- Consolidados firmables del rol de pagos.

---

## Reutilización (evitar reinventar)
- **Snapshot inmutable**: `employees/nomina.py::generar_recibo/_jsonable` + `ReciboNomina.datos`. Sirve igual para ambos regímenes; protege el histórico.
- **Branding en salidas**: `employees/report_pdf.py::_bloque_empresa` y `employees/exports.py::_bloque_empresa`.
- **Seed de parámetros**: patrón `migrations/0026_tipos_ausencia_default.py` (`RunPython` + `get_or_create`).
- **Helper computado sin ledger**: `Employee.saldo_vacaciones` (models.py:79) como molde para provisiones de décimos/fondos.
- **Cliente Dolibarr**: `employees/dolibarr_api.py::crear_salario` como molde para `crear_factura_proveedor`.
- **Config editable**: vista `company_settings` (views.py:261) como molde para la pantalla de `ParametrosLegales`.

## Qué NO hacer
- No tocar el cálculo de comisiones (Dolibarr inbound) ni el flujo del candidato psico.
- No fijar tasas en el código (todo en `ParametrosLegales`).
- No romper a los empleados actuales: default `servicios`, migraciones aditivas.
- No construir un ledger contable completo; las provisiones se computan del histórico de recibos.

## Critical files (para la construcción futura)
- `employees/models.py` — `Employee` (57): campos de régimen/legales; `ParametrosLegales` (nuevo); `calculate_salary` (396): ramificación; `WorkLog` (489): tipo de hora extra.
- `employees/nomina.py` — snapshot y ramificación del envío a Dolibarr.
- `employees/dolibarr_api.py` — `crear_factura_proveedor` (nuevo) para `/supplierinvoices`.
- `employees/report_pdf.py`, `employees/exports.py` — ramas de salida por régimen (rol de pagos vs comprobante de honorarios).
- `employees/forms.py`, `employees/views.py` (`company_settings`), `employees/admin.py` — UI de parámetros y campos nuevos.
- `employees/migrations/` — nuevas migraciones dependientes de `0029` (schema + data seed 2025/2026).

## Verificación (por etapa, al construir)
- **Tests unitarios** de `calculate_salary` por régimen: dependencia (aportes 9.45%, recargos 25/50/100, líquido correcto) y servicios (IVA + retención opcionales, neto correcto), siguiendo el patrón de `PerformanceAndSalaryTest` en `tests.py`.
- **Inmutabilidad**: generar recibo → cambiar parámetros del año → el recibo NO cambia (patrón ya existente en `tests_ausencias.py`).
- **Provisiones**: verificar décimo tercero acumulado computado del histórico y elegibilidad de fondos de reserva por antigüedad.
- **Dolibarr**: `httpx` mockeado; dependencia→`/salaries`, servicios→`/supplierinvoices` (patrón `tests_dolibarr_push.py`).
- **Render**: rol de pagos PDF y comprobante de honorarios generan sin error y muestran los rubros correctos.
- **Validación con el contador**: cotejar SBU, porcentajes de aporte, recargos y retenciones contra la ley vigente antes de cualquier corrida real; correr una nómina de prueba y comparar el líquido a mano.
- Al cierre de cada etapa: `manage.py test employees` completo verde + deploy independiente (git pull + migrate + HUP).
