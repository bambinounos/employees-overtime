# Informe de Factibilidad: Integración de Efectividad de Ventas y Comisiones (Dolibarr + Django)

## 1. Resumen Ejecutivo
Es **totalmente factible** implementar la funcionalidad solicitada. La arquitectura propuesta implica el desarrollo de un módulo personalizado en Dolibarr que se comunique con el software de salarios (Django) a través de una API REST segura. Esto permitirá automatizar el cálculo del KPI de "Efectividad de Ventas" (conversión de proforma a factura) y el cálculo de comisiones para los vendedores.

## 2. Arquitectura Propuesta

### 2.1. Lado Dolibarr (El ERP)
Se requiere desarrollar un **Módulo Personalizado de Dolibarr** que utilice el sistema de "Triggers" (Hooks).
*   **Evento 1: Validación de Proforma (`PROPAL_VALIDATE`)**: Cuando una proforma se valida, el módulo enviará un webhook (petición HTTP POST) al software de salarios con los datos de la proforma (ID, Usuario, Monto, Fecha).
*   **Evento 2: Validación de Factura (`BILL_VALIDATE`)**: Cuando una factura se valida (y proviene de una proforma), el módulo enviará otro webhook con los datos de la venta finalizada.

### 2.2. Lado Software de Salarios (Django)
Se requiere extender la aplicación `employees` para recibir, almacenar y procesar estos datos.
*   **API REST:** Nuevos endpoints para recibir los datos desde Dolibarr.
*   **Base de Datos:** Nuevos modelos para rastrear el ciclo de venta.
*   **Lógica de Negocio:** Actualización de los cálculos de nómina y KPIs.

## 3. Implementación Detallada

### 3.1. Sincronización de Usuarios
Para evitar una sincronización compleja de doble vía, se recomienda usar el **Correo Electrónico** como identificador único.
*   **Requisito:** El vendedor en Dolibarr debe tener el mismo correo electrónico que el `Employee` en el software de salarios.
*   **Validación:** Al recibir datos, el sistema buscará `Employee.objects.get(email=dolibarr_email)`. Si no existe, se registrará un error o se ignorará.

### 3.2. Cambios en el Software de Salarios (Django)

#### A. Nuevos Modelos de Datos
Se sugiere crear un modelo `SalesRecord` para almacenar la traza de la venta:
```python
class SalesRecord(models.Model):
    employee = models.ForeignKey(Employee, ...)
    dolibarr_proforma_id = models.CharField(...) # ID externo
    dolibarr_invoice_id = models.CharField(..., null=True) # ID externo
    proforma_amount = models.DecimalField(...)
    invoice_amount = models.DecimalField(..., default=0)
    proforma_date = models.DateField(...)
    invoice_date = models.DateField(..., null=True)
    status = models.CharField(choices=['proformed', 'invoiced', 'cancelled'])
```

#### B. Modificación de Modelos Existentes
1.  **Modelo `Salary` o `Employee`:** Agregar un campo `commission_percentage` (Decimal) para configurar el porcentaje de comisión por vendedor.
2.  **Modelo `KPI`:** Agregar un nuevo `measurement_type = 'sales_conversion'` para manejar la lógica automática de este indicador.

#### C. Lógica de Cálculo (KPI y Comisiones)
1.  **KPI Efectividad de Ventas:**
    *   *Fórmula:* `(Total Facturas Validadas / Total Proformas Emitidas) * 100` en el periodo (mes).
    *   Se implementará en `calculate_performance_bonus` filtrando los `SalesRecord` del mes.
2.  **Comisiones:**
    *   *Fórmula:* `Monto Facturado * (Porcentaje Comisión / 100)`.
    *   Se actualizará el método `calculate_salary` para sumar este valor al sueldo base y bonos.

#### D. Nuevos Endpoints de API
*   `POST /api/integrations/dolibarr/proforma/`: Recibe datos de proformas.
*   `POST /api/integrations/dolibarr/invoice/`: Recibe datos de facturas.
*   **Seguridad:** Se debe implementar autenticación por Token (Dolibarr enviará un token en el header `Authorization`).

## 4. Retos y Desafíos

1.  **Ciclos de Venta entre Meses:**
    *   *Escenario:* Proforma en Enero, Factura en Febrero.
    *   *Desafío:* ¿El KPI de Enero baja por no convertir? ¿El de Febrero sube "artificialmente"?
    *   *Solución Recomendada:* Medir la conversión basada en la *fecha de cierre (factura)* comparada con las proformas *generadas* ese mismo mes, o usar una ventana móvil. Para comisiones, siempre se paga en el mes de la factura.

2.  **Modificaciones y Cancelaciones:**
    *   Si una proforma se modifica en Dolibarr después de enviarse, el sistema debe ser capaz de actualizar el registro existente en lugar de duplicarlo. Se usará el ID de Dolibarr como clave externa única.

3.  **Conectividad:**
    *   Si el software de salarios está caído, Dolibarr podría fallar al enviar. Se recomienda que el módulo de Dolibarr tenga una cola de reintentos o que los envíos sean asíncronos.

## 5. Posibles Errores y Riesgos

1.  **Desincronización de Emails:** Si un vendedor cambia su correo en uno de los sistemas, la integración fallará para ese usuario.
2.  **Datos Inconsistentes:** Que Dolibarr envíe una factura sin referencia a la proforma original (si el proceso manual en Dolibarr no se sigue correctamente). El sistema solo podrá calcular conversión si existe el vínculo.
3.  **Seguridad:** Exponer endpoints financieros requiere HTTPS obligatorio y tokens de seguridad rotativos para evitar inyección de datos falsos.

## 6. Conclusión
La implementación automatizará significativamente el cálculo de nómina variable y ofrecerá métricas reales sobre el desempeño de ventas. El esfuerzo principal recae en el desarrollo del módulo de Dolibarr (PHP) y la creación de la API receptora en Django (Python).

**Tiempo estimado de implementación:** 2-3 semanas (dependiendo de la complejidad de las reglas de negocio en Dolibarr).
