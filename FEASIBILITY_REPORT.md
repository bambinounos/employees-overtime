# Informe de Factibilidad: Integración de Efectividad de Ventas y Comisiones (Dolibarr + Django) (v5)

## 1. Resumen Ejecutivo
Es **totalmente factible** implementar la funcionalidad solicitada. La arquitectura propuesta implica el desarrollo de un módulo personalizado en Dolibarr que se comunique con el software de salarios (Django) a través de una API REST segura. Esto permitirá automatizar el cálculo del KPI de "Efectividad de Ventas" (conversión de proforma a factura) y el cálculo de comisiones para los vendedores.

Se han incorporado observaciones críticas para evitar vulnerabilidades en la métrica (fraude por omisión de proformas), manejo correcto de devoluciones (notas de crédito), soporte robusto para **múltiples empresas (Multi-Dolibarr)** y un sistema flexible de **bonificaciones escalonadas**.

Adicionalmente, se ha detallado la factibilidad del **KPI de Creación de Productos** para digitadores, y se ha introducido un sistema de **Perfiles de Puesto (`JobProfile`)** para asegurar la correcta segregación de KPIs entre roles (ej: Ventas vs. Contabilidad).

## 2. Arquitectura Propuesta

### 2.1. Lado Dolibarr (El ERP)
Se requiere desarrollar un **Módulo Personalizado de Dolibarr** que utilice el sistema de "Triggers" (Hooks).
*   **Identificación de Instancia:** Cada instancia de Dolibarr enviará en sus peticiones el valor configurado en **"ID Profesional 1"** (ubicado en `admin/company.php`). Este valor servirá como identificador único de la empresa (`company_uid`) para distinguir documentos cuando existen múltiples Dolibarrs conectados.
*   **Evento 1: Validación de Proforma (`PROPAL_VALIDATE`)**: Cuando una proforma se valida, el módulo enviará un webhook (petición HTTP POST) al software de salarios.
*   **Evento 2: Validación de Factura (`BILL_VALIDATE`)**: Cuando una factura se valida, el módulo enviará un webhook con los datos de la venta.
    *   *Crucial:* El payload debe incluir el ID de la proforma de origen (`fk_propal`) para trazar el ciclo de venta.
    *   *Crucial:* El payload debe incluir el **total sin impuestos (Base Imponible/Total HT)**, ya que las comisiones no se calculan sobre el IVA.
*   **Evento 3: Validación de Nota de Crédito (`BILL_VALIDATE` con tipo Credit Note)**: Cuando se genera una nota de crédito, se enviará un evento para descontar este monto (también sin impuestos) de las comisiones.
*   **Evento 4: Creación de Producto (`PRODUCT_CREATE`)**: Cuando se crea un producto, se envía un webhook con el ID del producto, su referencia, fecha de creación y el usuario responsable.

### 2.2. Lado Software de Salarios (Django)
Se requiere extender la aplicación `employees` para recibir, almacenar y procesar estos datos.
*   **API REST:** Endpoint único o segregado capaz de identificar el origen de los datos mediante el `company_uid` ("ID Profesional 1").
*   **Base de Datos:** Nuevos modelos para configuración de instancias Dolibarr, registros de ventas, reglas de bonificación avanzadas y perfiles de puesto.
*   **Lógica de Negocio:** Actualización de los cálculos para validar la relación Proforma-Factura, deducir devoluciones y aplicar escalas de bonificación según el perfil del empleado.

### 2.3. Arquitectura Adicional: KPI de Creación de Productos (Digitadores)
Para satisfacer la necesidad de premiar a los digitadores (no vendedores) por la creación de productos, se utilizará una lógica similar de Webhooks pero con controles de unicidad más estrictos.
*   **Problema de Fraude:** Un usuario podría borrar y recrear el mismo producto 20 veces para cobrar el bono.
*   **Solución:** El sistema almacenará un registro histórico de IDs de productos creados por instancia. Si el ID de producto `12345` de la instancia `A` ya fue pagado, cualquier webhook futuro con ese mismo ID será ignorado.

## 3. Implementación Detallada

### 3.1. Sincronización de Usuarios e Instancias
*   **Identificación de Empleado:** Se usará el **Correo Electrónico** como identificador único. Si un empleado trabaja en la Empresa A y la Empresa B, el sistema unificará sus ventas bajo su perfil único de `Employee`.
*   **Identificación de Empresa:** Se debe crear un registro en Django por cada instancia de Dolibarr conectada, almacenando su "ID Profesional 1" esperado. Si llega una petición con un ID desconocido, será rechazada.

### 3.2. Cambios en el Software de Salarios (Django)

#### A. Nuevos Modelos de Datos

1.  **Identificación Técnica del KPI (`internal_code`):**
    Actualmente, los KPIs son texto libre. Para que el sistema sepa qué KPI "conecta" con la lógica de Efectividad de Ventas, se añadirá un campo `internal_code` (SlugField) al modelo `KPI`.
    *   Ejemplo: `SALES_EFFECTIVENESS`, `PRODUCT_CREATION`.

2.  **Modelo `KPIBonusTier` (Bonos Escalonados):**
    Relación Uno-a-Muchos que permite múltiples niveles de premio.
    *   `kpi`: FK a KPI.
    *   `threshold`: Valor mínimo (ej: 35.00%, 20 productos).
    *   `bonus_amount`: Monto a pagar.

3.  **Modelo `JobProfile` (Gestión de Roles):**
    Para solucionar el problema de segregación de KPIs (ej: evitar bonos de venta a contadores), se centralizan los permisos en este modelo.
    *   `name`: Nombre del puesto (ej: "Vendedor Senior", "Contador", "Digitador").
    *   `measure_sales_effectiveness` (Boolean): ¿Aplica conversión Proforma-Factura?
    *   `earns_commissions` (Boolean): ¿Gana comisiones por venta?
    *   `measure_product_creation` (Boolean): ¿Gana bono por crear productos?

4.  **Modelo `SalesRecord` (Traza de Ventas):**
    *   `employee`: ForeignKey a `Employee`.
    *   `dolibarr_instance`: ForeignKey a `DolibarrInstance`.
    *   `dolibarr_proforma_id`: ID original en Dolibarr (RowID).
    *   `dolibarr_invoice_id`: ID original en Dolibarr (RowID).
    *   `status`: Estado del ciclo (proformado, facturado, cancelado).
    *   `amount`: Monto monetario **sin impuestos**.

5.  **Modelo `ProductCreationLog` (Traza de Creación de Productos):**
    *   `employee`: ForeignKey a `Employee`.
    *   `dolibarr_instance`: ForeignKey a `DolibarrInstance`.
    *   `dolibarr_product_id`: ID único del producto en Dolibarr.
    *   `product_ref`: Referencia del producto (SKU).
    *   `processed`: Boolean.

#### B. Modificación de Modelos Existentes (`Employee`)
*   **Campo `profile`:** Se agrega una ForeignKey al modelo `JobProfile`.
*   *Lógica:* `Employee` -> `JobProfile` -> Permisos. Esto evita la configuración manual de booleans por cada empleado y asegura consistencia.

#### C. Lógica de Cálculo Actualizada
1.  **Validación de Perfil:**
    Antes de procesar cualquier webhook o cálculo de fin de mes, el sistema verificará:
    `if employee.profile.measure_sales_effectiveness is True: calcular()`

2.  **KPI Efectividad de Ventas (con Tiers y Mínimos):**
    *   *Paso 1 (Volumen):* Se verifica si `total_proformas >= kpi.min_volume_threshold`.
    *   *Paso 2 (Cálculo):* `(Facturas con Proforma de Origen / Total Proformas Emitidas) * 100`.
    *   *Paso 3 (Bonificación):* Se busca en `KPIBonusTier` el nivel alcanzado.

3.  **Comisiones:**
    *   *Lógica:* `(Monto Facturado Sin Impuestos - Monto Notas de Crédito Sin Impuestos) * % Comisión`.

### 3.3 Implementación: Creación de Productos (Digitadores)
El flujo para el KPI de creación de productos será:

1.  **Recepción del Webhook:** Django recibe `PRODUCT_CREATE`.
2.  **Validación de Empleado:** Se busca el empleado por email.
3.  **Verificación de Rol:** Se chequea `employee.profile.measure_product_creation`. Si es falso (ej: es un Vendedor, no un Digitador), se ignora el evento o se loguea sin efecto de bono.
4.  **Prevención de Fraude:**
    *   Se consulta `ProductCreationLog` para evitar duplicados de ID de producto/instancia.
5.  **Cálculo de KPI:**
    *   Conteo mensual de registros válidos vs `KPIBonusTier`.

## 4. Análisis de Implicaciones

1.  **Configuración Inicial:**
    *   Creación de `JobProfiles` (Vendedor, Contador, etc.).
    *   Asignación de perfiles a empleados existentes.

2.  **Seguridad:**
    *   El sistema de perfiles mitiga el riesgo de pagar bonos incorrectos a roles administrativos.

## 5. Riesgos

1.  **Cambio de ID Profesional:** Si un administrador cambia el "ID Profesional 1" en Dolibarr sin actualizarlo en Django, la integración se romperá.
2.  **Manipulación de Proformas:** Si un vendedor elimina proformas en Dolibarr para mejorar su promedio, el webhook debe manejar eventos de eliminación (`PROPAL_DELETE`) o marcar esas proformas como anuladas en Django para mantener la integridad de la métrica.
3.  **Calidad de Productos:** El KPI de creación solo mide cantidad. Un digitador podría crear productos incompletos o con datos basura para llegar a la cuota. Se recomienda auditoría aleatoria.

## 6. Conclusión
La inclusión del modelo **`JobProfile`** completa la lógica de negocio al permitir una segregación estricta de responsabilidades y beneficios. Esto soluciona la problemática de aplicar KPIs incorrectos a perfiles como Contadores o Administrativos puros.

El diseño técnico ahora abarca la identificación de usuario, identificación de empresa, validación de reglas de negocio por perfil, trazabilidad de eventos y cálculo escalonado de bonificaciones.

**Estado:** Listo para fase de desarrollo. Diseño técnico robusto y completo.
