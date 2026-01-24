# Informe de Factibilidad: Integración de Efectividad de Ventas y Comisiones (Dolibarr + Django) (v7)

## 1. Resumen Ejecutivo
Es **totalmente factible** implementar la funcionalidad solicitada. La arquitectura propuesta implica el desarrollo de un módulo personalizado en Dolibarr que se comunique con el software de salarios (Django) a través de una API REST segura. Esto permitirá automatizar el cálculo del KPI de "Efectividad de Ventas" (conversión de proforma a factura) y el cálculo de comisiones para los vendedores.

Se mantienen las observaciones críticas de versiones anteriores para asegurar la integridad de los datos: prevención de **fraude por omisión de proformas** (mediante umbrales mínimos) y manejo correcto de **devoluciones**. Adicionalmente, esta versión (v8) incorpora mejoras de **seguridad (autenticación HMAC/Token)**, **resiliencia (cola de reintentos)** y **auditoría** para garantizar que ninguna venta se pierda por fallos de red.

Adicionalmente, se introduce el modelo **`JobProfile`** para gestionar qué KPIs aplican a cada rol (Ventas vs. Contabilidad) y se detallan las medidas anti-fraude para el **KPI de Creación de Productos**, incluyendo validación por Referencia (SKU).

## 2. Arquitectura Propuesta

### 2.1. Lado Dolibarr (El ERP)
Se requiere desarrollar un **Módulo Personalizado de Dolibarr** que utilice el sistema de "Triggers" (Hooks).
*   **Identificación de Instancia:** Cada instancia de Dolibarr enviará en sus peticiones el valor configurado en **"ID Profesional 1"** (ubicado en `admin/company.php`). Este valor servirá como identificador único de la empresa (`company_uid`).
*   **Evento 1: Validación de Proforma (`PROPAL_VALIDATE`)**: Se envía webhook al validar una proforma.
*   **Evento 2: Validación de Factura (`BILL_VALIDATE`)**: Se envía webhook al validar una factura.
    *   *Crucial:* El payload debe incluir el ID de la proforma de origen (`fk_propal`) para trazar el ciclo de venta.
    *   *Crucial:* El payload debe incluir el **total sin impuestos (Base Imponible/Total HT)**, ya que las comisiones se pagan sobre la venta real, no sobre el IVA recaudado.
*   **Evento 3: Validación de Nota de Crédito (`BILL_VALIDATE` con tipo Credit Note)**: Se envía webhook para descontar este monto de las comisiones del mes.
*   **Evento 4: Creación de Producto (`PRODUCT_CREATE`)**: Se envía webhook con ID, referencia (SKU), fecha y usuario.

#### Mejoras de Robustez en Dolibarr (Nuevos Requisitos)
*   **Cola de Reintentos (Retry Queue):** Si el servidor Django no responde (200 OK), el módulo debe guardar el evento y reintentar automáticamente (ej: cada 15 min).
*   **Resync Manual:** Botón en la ficha de Factura/Proforma para forzar el reenvío del evento en caso de errores.
*   **Dashboard Widget:** Indicador visual en el inicio de Dolibarr que alerte sobre fallos de conexión con el sistema de nómina.

### 2.2. Lado Software de Salarios (Django)
Se requiere extender la aplicación `employees` para recibir, almacenar y procesar estos datos.
*   **API REST Segura:** Endpoint protegido que valida el `company_uid` y verifica la autenticidad del mensaje mediante **Token/Secreto (HMAC)**.
*   **Procesamiento Asíncrono:** Recepción inmediata en un log (`WebhookLog`) para evitar timeouts, con procesamiento diferido de reglas de negocio.
*   **Base de Datos:** Nuevos modelos para configuración, logs de auditoría, traza de ventas y perfiles.

## 3. Implementación Detallada

### 3.1. Sincronización de Usuarios e Instancias
*   **Estrategia Robusta (Multi-Instancia):** Dado que un empleado puede vender en múltiples empresas (instancias) con distintos usuarios, no nos basaremos solo en el email.
*   **Modelo de Mapeo (`DolibarrUserIdentity`):** Tabla explícita que vincula `(DolibarrInstance, external_user_id)` -> `Employee`.
    *   Si llega un webhook con un ID no mapeado, el sistema crea un log de advertencia ("Empleado no identificado para ID 123 en Instancia A") para que el admin cree el vínculo.
* 3.  **Identificación de Empresa:** Modelo `DolibarrInstance`:
    *   Mapea el "ID Profesional 1" a un nombre legible.
    *   Almacena el **API Secret/Token** único para validar las peticiones de esa instancia.

### 3.2. Cambios en el Software de Salarios (Django)

#### A. Nuevos Modelos de Datos

1.  **Identificación Técnica del KPI (`internal_code` en `KPI`):**
    Campo `SlugField` en el modelo KPI para identificar lógicamente qué métrica es.
    *   Ejemplo: `SALES_EFFECTIVENESS`, `PRODUCT_CREATION`.

2.  **Configuración de Tasa Mínima (`min_volume_threshold` en `KPI`):**
    Campo `IntegerField` en el modelo KPI.
    *   *Propósito (Anti-Fraude):* Define el volumen mínimo de registros (ej: 10 proformas/mes) para ser elegible al bono. Evita que un empleado haga 1 proforma, 1 venta (100% efectividad) y cobre el bono máximo.

3.  **Modelo `KPIBonusTier` (Bonos Escalonados):**
    Permite definir múltiples niveles de recompensa.
    *   `kpi`: FK a KPI.
    *   `threshold`: Valor mínimo para el nivel (ej: 35% efectividad, o 20 productos creados).
    *   `bonus_amount`: Monto monetario del bono.

4.  **Modelo `JobProfile` (Gestión de Roles - NUEVO):**
    Centraliza la configuración de elegibilidad para evitar errores manuales.
    *   `name`: Nombre del puesto (ej: "Vendedor", "Contador", "Gerente de Logística").
    *   `kpis`: Relación Many-to-Many con el modelo `KPI`. Define qué indicadores se miden para este perfil.
    *   `earns_commissions`: Boolean (General). Indica si este perfil es elegible para el esquema de comisiones variable estándar.

        *   `api_secret`: Token HMAC para validar webhooks de esta instancia.

6.  **Modelo `DolibarrUserIdentity` (Mapeo de Usuarios - NUEVO):**
    *   `employee`: FK a `Employee`.
    *   `dolibarr_instance`: FK a `DolibarrInstance`.
    *   `dolibarr_user_id`: ID numérico del usuario en esa instancia de Dolibarr.
    *   `dolibarr_login`: (Opcional) Login/Username para referencia visual.
    *   *Unique Constraint:* (`dolibarr_instance`, `dolibarr_user_id`).

7.  **Modelo `SalesRecord` (Traza de Ventas):**
    *   `employee`: FK a `Employee` (Resolución: Webhook -> Instance+UserID -> Identity -> Employee).
    *   `dolibarr_instance`: FK a `DolibarrInstance`.
    *   `dolibarr_proforma_id`: ID original (RowID).
    *   `dolibarr_invoice_id`: ID original (RowID).
    *   `status`: Estado (proformado, facturado).
    *   `amount`: Monto **sin impuestos**.

6.  **Modelo `ProductCreationLog` (Traza de Productos - Anti-Fraude):**
    *   `dolibarr_product_id`: ID del producto en Dolibarr (para evitar duplicación inmediata).
    *   `product_ref`: SKU/Referencia del producto (para evitar fraude por borrado/recreación).
    *   `created_at`: Fecha.
    *   *Unique Constraint:* (`dolibarr_instance`, `dolibarr_product_id`).

7.  **Modelo `WebhookLog` (Auditoría y Resiliencia - NUEVO):**
    *   Almacena el payload crudo (`JSON`), headers, IP de origen y estado de procesamiento.
    *   Permite re-procesar eventos si hay bugs en la lógica de negocio sin perder los datos originales.

#### B. Modificación de Modelos Existentes (`Employee`)
*   Se añade campo `profile` (FK a `JobProfile`).
*   Se eliminan los campos booleanos individuales del empleado, delegando esa lógica al perfil.

#### C. Lógica de Cálculo Actualizada

1.  **Validación de Perfil:**
1.  **Validación de Perfil:**
    *   Antes de calcular cualquier métrica, el sistema verificará: `if kpi in employee.profile.kpis.all()`.
    *   Esto permite tener N perfiles (Ej: "Vendedor Junior", "Vendedor Senior") con diferentes sets de KPIs activados.

2.  **KPI Efectividad de Ventas (Conversión):**
    *   *Filtro Anti-Fraude:* Si `total_proformas < kpi.min_volume_threshold`, la efectividad es 0%.
    *   *Cálculo:* `(Facturas con Proforma / Total Proformas) * 100`.
    *   *Bono:* Se asigna según el `KPIBonusTier` alcanzado.

3.  **Comisiones por Ventas:**
    *   *Conversión de Moneda:* Si el payload indica una moneda distinta a la base del sistema, se normalizará el valor.
    *   *Inmutabilidad:* Las Notas de Crédito **no borran** el `SalesRecord` original. Crean un nuevo registro con monto negativo para mantener la traza de auditoría.
    *   *Base:* Suma de `amount` de todas las facturas y notas de crédito (negativas) del mes.
    *   *Pago:* `(Total Ventas Netas) * % Comisión`.

4.  **Bono por Creación de Productos (Anti-Fraude Reforzado):**
    *   *Problema:* Si un usuario borra un producto y lo recrea, Dolibarr asigna un nuevo ID, burlando la restricción de ID único.
    *   *Solución:* El sistema verificará también el campo `product_ref` (SKU). Si ya existe un registro reciente (ej: mismo mes) con ese mismo SKU para esa instancia, se marcará el nuevo registro como sospechoso o duplicado, no elegible para bono.
    *   *Pago:* Conteo de productos únicos válidos creados vs `KPIBonusTier`.

## 4. Análisis de Implicaciones
*   **Segregación de Funciones:** El uso de `JobProfile` garantiza que, por diseño, un administrativo no reciba comisiones de venta.
*   **Integridad Financiera:** El uso de montos sin impuestos y la deducción de notas de crédito protegen la caja de la empresa.

## 5. Riesgos
1.  **Cambio de ID Profesional:** Requiere coordinación estricta entre admins de Dolibarr y Django.
2.  **Manipulación de Datos:** Aunque hay controles (min_volume, unique IDs, SKU check), se recomienda auditoría aleatoria periódica.

## 6. Conclusión
Esta versión del diseño integra todas las protecciones contra fraude (umbrales mínimos, validación de SKU), la lógica financiera correcta (base imponible, notas de crédito) y la segregación de roles mediante **`JobProfile`**, cumpliendo con todos los requisitos de seguridad y negocio.

**Estado:** Listo para desarrollo.
