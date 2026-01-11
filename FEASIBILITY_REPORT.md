# Informe de Factibilidad: Integración de Efectividad de Ventas y Comisiones (Dolibarr + Django) (v3)

## 1. Resumen Ejecutivo
Es **totalmente factible** implementar la funcionalidad solicitada. La arquitectura propuesta implica el desarrollo de un módulo personalizado en Dolibarr que se comunique con el software de salarios (Django) a través de una API REST segura. Esto permitirá automatizar el cálculo del KPI de "Efectividad de Ventas" (conversión de proforma a factura) y el cálculo de comisiones para los vendedores.

Se han incorporado observaciones críticas para evitar vulnerabilidades en la métrica (fraude por omisión de proformas), manejo correcto de devoluciones (notas de crédito) y un soporte robusto para **múltiples empresas (Multi-Dolibarr)**, utilizando identificadores únicos de configuración.

## 2. Arquitectura Propuesta

### 2.1. Lado Dolibarr (El ERP)
Se requiere desarrollar un **Módulo Personalizado de Dolibarr** que utilice el sistema de "Triggers" (Hooks).
*   **Identificación de Instancia:** Cada instancia de Dolibarr enviará en sus peticiones el valor configurado en **"ID Profesional 1"** (ubicado en `admin/company.php`). Este valor servirá como identificador único de la empresa (`company_uid`) para distinguir documentos cuando existen múltiples Dolibarrs conectados.
*   **Evento 1: Validación de Proforma (`PROPAL_VALIDATE`)**: Cuando una proforma se valida, el módulo enviará un webhook (petición HTTP POST) al software de salarios.
*   **Evento 2: Validación de Factura (`BILL_VALIDATE`)**: Cuando una factura se valida, el módulo enviará un webhook con los datos de la venta.
    *   *Crucial:* El payload debe incluir el ID de la proforma de origen (`fk_propal`) para trazar el ciclo de venta.
*   **Evento 3: Validación de Nota de Crédito (`BILL_VALIDATE` con tipo Credit Note)**: Cuando se genera una nota de crédito, se enviará un evento para descontar este monto de las comisiones.

### 2.2. Lado Software de Salarios (Django)
Se requiere extender la aplicación `employees` para recibir, almacenar y procesar estos datos.
*   **API REST:** Endpoint único o segregado capaz de identificar el origen de los datos mediante el `company_uid` ("ID Profesional 1").
*   **Base de Datos:** Nuevos modelos para configuración de instancias Dolibarr y registros de ventas con restricciones de unicidad compuestas.
*   **Lógica de Negocio:** Actualización de los cálculos para validar la relación Proforma-Factura y deducir devoluciones, respetando las configuraciones individuales de cada empleado.

## 3. Implementación Detallada

### 3.1. Sincronización de Usuarios e Instancias
*   **Identificación de Empleado:** Se usará el **Correo Electrónico** como identificador único. Si un empleado trabaja en la Empresa A y la Empresa B, el sistema unificará sus ventas bajo su perfil único de `Employee`.
*   **Identificación de Empresa:** Se debe crear un registro en Django por cada instancia de Dolibarr conectada, almacenando su "ID Profesional 1" esperado. Si llega una petición con un ID desconocido, será rechazada.

### 3.2. Cambios en el Software de Salarios (Django)

#### A. Nuevos Modelos de Datos

1.  **Modelo `DolibarrInstance` (Configuración):**
    *   `name`: Nombre amigable (ej: "Sucursal Norte").
    *   `professional_id_1`: El valor exacto del campo "ID Profesional 1" en el Dolibarr correspondiente. Usado para validación de origen.
    *   `api_key`: (Opcional) Token de seguridad específico para esa instancia.

2.  **Modelo `SalesRecord` (Traza de Ventas):**
    *   `employee`: ForeignKey a `Employee`.
    *   `dolibarr_instance`: ForeignKey a `DolibarrInstance`.
    *   `dolibarr_proforma_id`: ID original en Dolibarr (RowID).
    *   `dolibarr_invoice_id`: ID original en Dolibarr (RowID).
    *   *Restricciones:* Se debe aplicar `unique_together` para evitar colisiones de IDs entre empresas diferentes:
        *   `unique_together = [['dolibarr_instance', 'dolibarr_proforma_id'], ['dolibarr_instance', 'dolibarr_invoice_id']]`
    *   `status`: Estado del ciclo (proformado, facturado, cancelado).

#### B. Modificación de Modelos Existentes (`Employee`)
Es necesario agregar banderas de configuración para determinar a quién se le aplican estas lógicas:

1.  **`measure_sales_effectiveness` (Boolean):**
    *   Si es `True`: El sistema calculará el KPI de conversión (Proforma -> Factura).
    *   Si es `False`: Se ignorarán los registros de este empleado para este KPI específico (útil para personal administrativo o de soporte que ocasionalmente factura pero no se mide por ventas).

2.  **`earns_commissions` (Boolean):**
    *   Si es `True`: El sistema acumulará montos para el pago de comisiones y aplicará descuentos por notas de crédito.
    *   Si es `False`: No se generarán cálculos de comisiones para este usuario.

#### C. Lógica de Cálculo (KPI y Comisiones)
1.  **KPI Efectividad de Ventas (Anti-Fraude):**
    *   *Filtro:* Solo aplica si `employee.measure_sales_effectiveness == True`.
    *   *Lógica:* `(Facturas con Proforma de Origen / Total Proformas Emitidas) * 100`.
    *   *Multi-Empresa:* Se suman todas las proformas y facturas de todas las instancias (`DolibarrInstance`) asociadas al email del empleado.

2.  **Comisiones (Considerando Devoluciones):**
    *   *Filtro:* Solo aplica si `employee.earns_commissions == True`.
    *   *Lógica:* `(Monto Facturado - Monto Notas de Crédito) * % Comisión`.
    *   *Identificación:* El sistema debe ser capaz de rastrear una Nota de Crédito en la Empresa B que anula una factura de la Empresa B, usando el `dolibarr_instance` para no confundirla con documentos de la Empresa A.

## 4. Análisis de Implicaciones

1.  **Configuración Inicial:**
    *   Será obligatorio configurar el campo "ID Profesional 1" en cada instalación de Dolibarr antes de conectar.
    *   Será necesario editar cada perfil de empleado existente para activar/desactivar `measure_sales_effectiveness` y `earns_commissions`. Por defecto deberían ser `False` para evitar cálculos erróneos en personal no comercial.

2.  **Colisión de IDs:**
    *   Al usar `unique_together` con el `dolibarr_instance`, resolvemos el problema de que la "Factura #100" exista tanto en la Empresa A como en la Empresa B. Sin embargo, esto hace estricta la necesidad de que el webhook envíe siempre el "ID Profesional 1".

3.  **Gestión de Errores:**
    *   Si un Dolibarr envía un webhook sin el "ID Profesional 1" o con uno no registrado en Django, la petición fallará. Esto requiere logs claros para depuración.

## 5. Riesgos

1.  **Cambio de ID Profesional:** Si un administrador cambia el "ID Profesional 1" en Dolibarr sin actualizarlo en Django, la integración se romperá inmediatamente.
2.  **Emails No Coincidentes:** Si un empleado usa `juan@empresa1.com` en un Dolibarr y `juan@empresa2.com` en otro, el sistema los tratará como dos personas distintas. Se debe estandarizar el email o crear un mecanismo de alias (fuera del alcance actual).

## 6. Conclusión
La inclusión del "ID Profesional 1" como discriminador de empresa y las banderas de configuración por empleado robustecen significativamente la propuesta. Permiten un despliegue escalable donde múltiples sucursales o razones sociales alimentan un único sistema de nómina centralizado, sin mezclar documentos ni aplicar métricas a personal incorrecto.

**Estado:** Listo para fase de desarrollo. No se requieren más cambios de diseño.
