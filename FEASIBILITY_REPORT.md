# Informe de Factibilidad: Integración de Efectividad de Ventas y Comisiones (Dolibarr + Django)

## 1. Resumen Ejecutivo
Es **totalmente factible** implementar la funcionalidad solicitada. La arquitectura propuesta implica el desarrollo de un módulo personalizado en Dolibarr que se comunique con el software de salarios (Django) a través de una API REST segura. Esto permitirá automatizar el cálculo del KPI de "Efectividad de Ventas" (conversión de proforma a factura) y el cálculo de comisiones para los vendedores.

Se han incorporado observaciones críticas para evitar vulnerabilidades en la métrica (fraude por omisión de proformas), manejo correcto de devoluciones (notas de crédito) y soporte para escenarios multi-empresa.

## 2. Arquitectura Propuesta

### 2.1. Lado Dolibarr (El ERP)
Se requiere desarrollar un **Módulo Personalizado de Dolibarr** que utilice el sistema de "Triggers" (Hooks).
*   **Evento 1: Validación de Proforma (`PROPAL_VALIDATE`)**: Cuando una proforma se valida, el módulo enviará un webhook (petición HTTP POST) al software de salarios con los datos de la proforma (ID, Usuario, Monto, Fecha).
*   **Evento 2: Validación de Factura (`BILL_VALIDATE`)**: Cuando una factura se valida, el módulo enviará un webhook con los datos de la venta.
    *   *Crucial:* El payload debe incluir el ID de la proforma de origen (`fk_propal`) o pedido de origen (`fk_commande`) para trazar el ciclo de venta completo.
*   **Evento 3: Validación de Nota de Crédito (`BILL_VALIDATE` con tipo Credit Note)**: Cuando se genera una nota de crédito por devolución o cancelación parcial, se debe enviar un evento para descontar este monto de las comisiones acumuladas.

### 2.2. Lado Software de Salarios (Django)
Se requiere extender la aplicación `employees` para recibir, almacenar y procesar estos datos.
*   **API REST:** Nuevos endpoints para recibir los datos desde múltiples instancias de Dolibarr.
*   **Base de Datos:** Nuevos modelos para rastrear el ciclo de venta, incluyendo soporte para multi-empresa y notas de crédito.
*   **Lógica de Negocio:** Actualización de los cálculos para validar la relación Proforma-Factura y deducir devoluciones.

## 3. Implementación Detallada

### 3.1. Sincronización de Usuarios
Para evitar una sincronización compleja de doble vía, se recomienda usar el **Correo Electrónico** como identificador único.
*   **Requisito:** El vendedor en Dolibarr debe tener el mismo correo electrónico que el `Employee` en el software de salarios.
*   **Multi-empresa:** Si un empleado trabaja para dos empresas, ambos sistemas Dolibarr enviarán datos usando el mismo correo, y el sistema central unificará la información.

### 3.2. Cambios en el Software de Salarios (Django)

#### A. Nuevos Modelos de Datos
Se sugiere actualizar el modelo `SalesRecord` para manejar la traza completa y multi-empresa:
```python
class SalesRecord(models.Model):
    employee = models.ForeignKey(Employee, ...)
    company_source = models.CharField(max_length=50) # Identificador de la empresa (Dolibarr A vs B)

    # IDs únicos de Dolibarr para evitar duplicados en ediciones
    dolibarr_proforma_id = models.CharField(unique=True, ...)
    dolibarr_invoice_id = models.CharField(unique=True, null=True, ...)
    dolibarr_credit_note_id = models.CharField(unique=True, null=True, ...) # Para devoluciones

    proforma_amount = models.DecimalField(...)
    invoice_amount = models.DecimalField(..., default=0)
    credit_note_amount = models.DecimalField(..., default=0) # Monto a restar

    proforma_date = models.DateField(...)
    invoice_date = models.DateField(..., null=True)

    # Estado para control interno
    status = models.CharField(choices=['proformed', 'invoiced', 'refunded', 'cancelled'])
```

#### B. Modificación de Modelos Existentes
1.  **Modelo `Salary` o `Employee`:** Agregar un campo `commission_percentage` (Decimal) para configurar el porcentaje de comisión por vendedor.
2.  **Modelo `KPI`:** Agregar un nuevo `measurement_type = 'sales_conversion'` para manejar la lógica automática.

#### C. Lógica de Cálculo (KPI y Comisiones)
1.  **KPI Efectividad de Ventas (Anti-Fraude):**
    *   *Fórmula:* `(Facturas con Proforma de Origen / Total Proformas Emitidas) * 100`.
    *   *Validación:* Solo se contarán como "Conversiones Exitosas" aquellas facturas que el sistema pueda vincular matemáticamente a una proforma previa mediante los IDs de Dolibarr. Las facturas directas (sin proforma) no suman al numerador de eficiencia, evitando que el empleado "engañe" al sistema saltándose pasos.

2.  **Comisiones (Considerando Devoluciones):**
    *   *Fórmula:* `(Monto Facturado - Monto Notas de Crédito) * (Porcentaje Comisión / 100)`.
    *   Se debe procesar la nota de crédito en el mes que se emite, restando de la comisión del periodo actual si es necesario.

#### D. Nuevos Endpoints de API
*   `POST /api/integrations/dolibarr/webhook/`: Endpoint unificado o segregado para recibir eventos (Proforma, Factura, Nota Crédito).
*   **Identificación de Fuente:** El payload o header debe indicar de qué empresa proviene (`company_source`) para manejar la lógica multi-empresa correctamente.

## 4. Retos y Desafíos

1.  **Ciclos de Venta entre Meses:**
    *   *Solución:* Al vincular estrictamente Proforma -> Factura mediante IDs, no importa si ocurren en meses distintos. El sistema puede reportar: "De las proformas emitidas en Enero, X% se cerraron (aunque fuera en Febrero)".

2.  **Evasión del Proceso (Gaming the system):**
    *   *Riesgo:* Empleados creando facturas directas para evitar que se cuenten proformas no cerradas.
    *   *Mitigación:* La lógica del KPI excluirá explícitamente facturas que no tengan un `fk_propal` (ID de proforma origen) válido. Esto fuerza al empleado a seguir el flujo correcto para que su venta cuente en el KPI de efectividad.

3.  **Manejo de Notas de Crédito:**
    *   Es vital que Dolibarr envíe notificaciones de Notas de Crédito. Si esto se omite, se pagarán comisiones sobre ventas que luego fueron devueltas, generando pérdidas para la empresa.

4.  **Multi-Empresa:**
    *   Vendedores que operan en dos instancias de Dolibarr requieren que el sistema de salarios agregue las ventas de ambas fuentes bajo el mismo empleado. Se usará el email como nexo común y un campo `company_source` para auditoría.

## 5. Posibles Errores y Riesgos

1.  **Datos Inconsistentes:** Duplicidad de registros por ediciones en Dolibarr.
    *   *Solución:* Uso estricto de los IDs de Dolibarr (`rowid`) como clave única en Django. Si llega un ID existente, se actualiza el registro (`UPDATE`) en lugar de crear uno nuevo (`INSERT`).
2.  **Seguridad:** Ambos sistemas (Dolibarr y Django) deben operar bajo HTTPS. Las claves de API deben ser rotativas y específicas por empresa origen.

## 6. Conclusión
La implementación robustecida automatizará la nómina y los KPIs, cerrando brechas de seguridad (fraude en métricas) y financiera (comisiones sobre devoluciones). El éxito depende de la correcta extracción de las relaciones (Proforma -> Factura) desde la API de Dolibarr.

**Tiempo estimado de implementación:** 3 semanas (incluyendo pruebas de integración para escenarios de devolución y multi-empresa).
