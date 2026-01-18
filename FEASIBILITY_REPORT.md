# Informe de Factibilidad: Integración de Efectividad de Ventas y Comisiones (Dolibarr + Django) (v4)

## 1. Resumen Ejecutivo
Es **totalmente factible** implementar la funcionalidad solicitada. La arquitectura propuesta implica el desarrollo de un módulo personalizado en Dolibarr que se comunique con el software de salarios (Django) a través de una API REST segura. Esto permitirá automatizar el cálculo del KPI de "Efectividad de Ventas" (conversión de proforma a factura) y el cálculo de comisiones para los vendedores.

Se han incorporado observaciones críticas para evitar vulnerabilidades en la métrica (fraude por omisión de proformas), manejo correcto de devoluciones (notas de crédito), soporte robusto para **múltiples empresas (Multi-Dolibarr)** y un sistema flexible de **bonificaciones escalonadas**.

Adicionalmente, se ha detallado la factibilidad del **KPI de Creación de Productos** para digitadores, incluyendo mecanismos antifraude para evitar la duplicación de bonos por productos recreados.

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
*   **Base de Datos:** Nuevos modelos para configuración de instancias Dolibarr, registros de ventas y reglas de bonificación avanzadas.
*   **Lógica de Negocio:** Actualización de los cálculos para validar la relación Proforma-Factura, deducir devoluciones y aplicar escalas de bonificación.

### 2.3. Arquitectura Adicional: KPI de Creación de Productos (Digitadores)
Para satisfacer la necesidad de premiar a los digitadores (no vendedores) por la creación de productos, se utilizará una lógica similar de Webhooks pero con controles de unicidad más estrictos.
*   **Problema de Fraude:** Un usuario podría borrar y recrear el mismo producto 20 veces para cobrar el bono.
*   **Solución:** El sistema almacenará un registro histórico de IDs de productos creados por instancia. Si el ID de producto `12345` de la instancia `A` ya fue pagado, cualquier webhook futuro con ese mismo ID será ignorado, incluso si el producto fue borrado y recreado (Dolibarr incrementa el ID en nuevas creaciones, pero si se renombra o modifica, el ID se mantiene. Si se borra y crea uno "igual", tendrá nuevo ID, por lo que la validación debe incluir también la **Referencia (Ref)** del producto para mayor seguridad, o limitar la velocidad de creación).

## 3. Implementación Detallada

### 3.1. Sincronización de Usuarios e Instancias
*   **Identificación de Empleado:** Se usará el **Correo Electrónico** como identificador único. Si un empleado trabaja en la Empresa A y la Empresa B, el sistema unificará sus ventas bajo su perfil único de `Employee`.
*   **Identificación de Empresa:** Se debe crear un registro en Django por cada instancia de Dolibarr conectada, almacenando su "ID Profesional 1" esperado. Si llega una petición con un ID desconocido, será rechazada.

### 3.2. Cambios en el Software de Salarios (Django)

#### A. Nuevos Modelos de Datos y Modificaciones a KPIs

1.  **Identificación Técnica del KPI (`internal_code`):**
    Actualmente, los KPIs son texto libre. Para que el sistema sepa qué KPI "conecta" con la lógica de Efectividad de Ventas, se añadirá un campo `internal_code` (SlugField) al modelo `KPI`.
    *   Ejemplo: Un registro KPI puede llamarse "Efectividad Ventas Q1", pero su `internal_code` será `SALES_EFFECTIVENESS`.
    *   Otro Ejemplo: `PRODUCT_CREATION` para el bono de digitadores.
    *   El motor de cálculo verificará: `if kpi.internal_code == 'SALES_EFFECTIVENESS': ejecutar_logica_proformas()`.

2.  **Modelo `KPIBonusTier` (Bonos Escalonados):**
    Se reemplazará el modelo simple actual por una relación Uno-a-Muchos que permita múltiples niveles de premio.
    *   `kpi`: FK a KPI.
    *   `threshold`: Valor mínimo para alcanzar este nivel (ej: 35.00, 50.00, o 20 productos, 40 productos).
    *   `bonus_amount`: Monto a pagar si se alcanza este nivel.
    *   *Lógica:* El sistema evaluará el desempeño y otorgará el bono del nivel más alto alcanzado.

3.  **Configuración de Tasa Mínima (`min_volume_threshold`):**
    Para evitar el "gaming" del sistema (ej: hacer 1 proforma, vender 1, tener 100% efectividad y cobrar bono), se añadirá un campo `min_volume_threshold` al modelo `KPI`.
    *   Si el empleado no cumple con el mínimo de registros (ej: 10 proformas/mes), el KPI se considera no cumplido, independientemente del porcentaje.

4.  **Modelo `DolibarrInstance` (Configuración):**
    *   `name`: Nombre amigable (ej: "Sucursal Norte").
    *   `professional_id_1`: El valor exacto del campo "ID Profesional 1" en el Dolibarr correspondiente.
    *   `api_key`: Token de seguridad específico.

5.  **Modelo `SalesRecord` (Traza de Ventas):**
    *   `employee`: ForeignKey a `Employee`.
    *   `dolibarr_instance`: ForeignKey a `DolibarrInstance`.
    *   `dolibarr_proforma_id`: ID original en Dolibarr (RowID).
    *   `dolibarr_invoice_id`: ID original en Dolibarr (RowID).
    *   `status`: Estado del ciclo (proformado, facturado, cancelado).
    *   `amount`: Monto monetario **sin impuestos** (para comisiones).

6.  **Modelo `ProductCreationLog` (Traza de Creación de Productos):**
    *   `employee`: ForeignKey a `Employee`.
    *   `dolibarr_instance`: ForeignKey a `DolibarrInstance`.
    *   `dolibarr_product_id`: ID único del producto en Dolibarr (RowID).
    *   `product_ref`: Referencia del producto (SKU) para doble validación.
    *   `created_at`: Fecha de creación reportada.
    *   `processed`: Boolean (Si ya se contó para bono).
    *   *Unique Constraint:* (`dolibarr_instance`, `dolibarr_product_id`) para evitar duplicados.

#### B. Modificación de Modelos Existentes (`Employee`)
Es necesario agregar banderas de configuración para determinar a quién se le aplican estas lógicas:

1.  **`measure_sales_effectiveness` (Boolean):**
    *   Si es `True`: El sistema calculará el KPI de conversión (Proforma -> Factura).
    *   Si es `False`: Se ignorarán los registros de este empleado para este KPI.

2.  **`earns_commissions` (Boolean):**
    *   Si es `True`: El sistema acumulará montos para el pago de comisiones y aplicará descuentos por notas de crédito.
    *   Si es `False`: No se generarán cálculos de comisiones para este usuario.

3.  **`measure_product_creation` (Boolean):**
    *   Si es `True`: Habilita la recepción de eventos de creación de productos para este empleado (Digitadores).
    *   Si es `False`: Se ignoran estos eventos.

#### C. Lógica de Cálculo Actualizada
1.  **KPI Efectividad de Ventas (con Tiers y Mínimos):**
    *   *Paso 1 (Volumen):* Se verifica si `total_proformas >= kpi.min_volume_threshold`. Si no, eficiencia = 0%.
    *   *Paso 2 (Cálculo):* `(Facturas con Proforma de Origen / Total Proformas Emitidas) * 100`.
    *   *Paso 3 (Bonificación):* Se busca en `KPIBonusTier` los niveles superados por el porcentaje obtenido y se asigna el monto correspondiente al nivel más alto.

2.  **Comisiones (Considerando Devoluciones):**
    *   *Lógica:* `(Monto Facturado Sin Impuestos - Monto Notas de Crédito Sin Impuestos) * % Comisión`.
    *   *Identificación:* El sistema debe rastrear la Nota de Crédito usando el `dolibarr_instance` para asociarla correctamente a la factura original.

### 3.3 Implementación: Creación de Productos (Digitadores)
El flujo para el KPI de creación de productos será:

1.  **Recepción del Webhook:** Django recibe `PRODUCT_CREATE` con `{id: 500, ref: 'PROD-001', user: 'juan@empresa.com'}`.
2.  **Validación de Empleado:** Se busca el empleado por email. Si tiene `measure_product_creation=True`, se procede.
3.  **Prevención de Fraude:**
    *   Se consulta `ProductCreationLog`.
    *   Si ya existe un registro con `dolibarr_instance` y `dolibarr_product_id=500`, se descarta (es un duplicado o reenvío).
    *   Opcional: Si existe un registro con `product_ref='PROD-001'` creado recientemente, se puede marcar para revisión manual (posible borrado y recreación).
4.  **Registro:** Se guarda el `ProductCreationLog`.
5.  **Cálculo de KPI:**
    *   A fin de mes, se cuenta el número de registros en `ProductCreationLog` para ese mes.
    *   Se compara este número (ej: 45 productos) contra la tabla `KPIBonusTier` del KPI `PRODUCT_CREATION`.
    *   Ejemplo Tiers:
        *   Tier 1: Threshold 20 -> Bono $50
        *   Tier 2: Threshold 40 -> Bono $100
    *   Resultado: Se paga el bono de $100.

## 4. Análisis de Implicaciones

1.  **Configuración Inicial:**
    *   Obligatorio configurar "ID Profesional 1" en Dolibarr.
    *   Configuración de `internal_code` en el KPI de ventas para activar la automatización.
    *   Definición de las tablas de bonos (`KPIBonusTier`) para escalonar los pagos.

2.  **Colisión de IDs:**
    *   Al usar `unique_together` con el `dolibarr_instance`, resolvemos el problema de que la "Factura #100" exista en múltiples empresas.

3.  **Gestión de Errores:**
    *   Si un Dolibarr envía un webhook sin el "ID Profesional 1" o con uno no registrado en Django, la petición fallará.

## 5. Riesgos

1.  **Cambio de ID Profesional:** Si un administrador cambia el "ID Profesional 1" en Dolibarr sin actualizarlo en Django, la integración se romperá.
2.  **Manipulación de Proformas:** Si un vendedor elimina proformas en Dolibarr para mejorar su promedio, el webhook debe manejar eventos de eliminación (`PROPAL_DELETE`) o marcar esas proformas como anuladas en Django para mantener la integridad de la métrica.
3.  **Calidad de Productos:** El KPI de creación solo mide cantidad. Un digitador podría crear productos incompletos o con datos basura para llegar a la cuota. Se recomienda auditoría aleatoria.

## 6. Conclusión
La inclusión del campo `internal_code` permite al sistema distinguir programáticamente qué KPI requiere lógica compleja, mientras que el modelo de `KPIBonusTier` y el umbral de volumen (`min_volume_threshold`) aseguran un sistema de incentivos justo, flexible y resistente al fraude.

La adición del KPI de **Creación de Productos** es factible y segura mediante el uso de logs de trazabilidad (`ProductCreationLog`) que impiden el doble conteo de registros, permitiendo extender el sistema de incentivos al personal administrativo.

**Estado:** Listo para fase de desarrollo. Diseño técnico completo.
