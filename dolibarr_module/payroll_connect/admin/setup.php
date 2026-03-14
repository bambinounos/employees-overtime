<?php
/* Copyright (C) 2026 Bambinounos
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 */

// Load Dolibarr environment (htdocs/custom/payroll_connect/admin/ -> htdocs/)
$res = 0;
if (!$res && file_exists("../main.inc.php")) $res = @include "../main.inc.php";
if (!$res && file_exists("../../main.inc.php")) $res = @include "../../main.inc.php";
if (!$res && file_exists("../../../main.inc.php")) $res = @include "../../../main.inc.php";
if (!$res) die("Include of main fails");

require_once DOL_DOCUMENT_ROOT . '/core/lib/admin.lib.php';
require_once __DIR__ . '/../lib/payroll_connect.lib.php';

// Access control
if (!$user->admin) {
    accessforbidden();
}

$action = GETPOST('action', 'alpha');

// Save settings (with CSRF token validation)
if ($action == 'set') {
    if (GETPOST('token', 'alpha') != newToken()) {
        setEventMessages("Security token expired. Please try again.", null, 'errors');
    } else {
        // Use GETPOST for proper input sanitization (Dolibarr standard)
        $webhook_url = GETPOST('PAYROLL_CONNECT_WEBHOOK_URL', 'url');
        $api_secret = GETPOST('PAYROLL_CONNECT_API_SECRET', 'alphanohtml');

        if (empty($webhook_url)) {
            setEventMessages("Webhook URL is required.", null, 'errors');
        } elseif (empty($api_secret)) {
            setEventMessages("API Secret is required.", null, 'errors');
        } else {
            $res1 = dolibarr_set_const($db, "PAYROLL_CONNECT_WEBHOOK_URL", $webhook_url, 'chaine', 0, '', $conf->entity);
            $res2 = dolibarr_set_const($db, "PAYROLL_CONNECT_API_SECRET", $api_secret, 'chaine', 0, '', $conf->entity);

            if ($res1 && $res2) {
                setEventMessages("Configuration saved successfully.", null, 'mesgs');
            } else {
                setEventMessages("Error saving configuration.", null, 'errors');
            }
        }
    }
}

// Test connection action
$test_result = null;
if ($action == 'testconnect') {
    if (GETPOST('token', 'alpha') != newToken()) {
        setEventMessages("Security token expired. Please try again.", null, 'errors');
    } else {
        $test_result = _testConnection();
    }
}

/**
 * Run a full diagnostic test against the Django webhook endpoint.
 * Returns an array with diagnostic details.
 *
 * @return array Diagnostic results
 */
function _testConnection()
{
    global $conf, $mysoc;

    $diag = array(
        'success' => false,
        'checks' => array(),
    );

    // Check 1: Webhook URL configured
    $webhook_url = getDolGlobalString('PAYROLL_CONNECT_WEBHOOK_URL');
    if (empty($webhook_url)) {
        $diag['checks'][] = array('error', 'Webhook URL no est&aacute; configurada.');
        return $diag;
    }
    $diag['checks'][] = array('ok', 'Webhook URL: <code>' . dol_escape_htmltag($webhook_url) . '</code>');

    // Check 2: API Secret configured
    $api_secret = getDolGlobalString('PAYROLL_CONNECT_API_SECRET');
    if (empty($api_secret)) {
        $diag['checks'][] = array('error', 'API Secret no est&aacute; configurado.');
        return $diag;
    }
    $diag['checks'][] = array('ok', 'API Secret: configurado (' . strlen($api_secret) . ' caracteres)');

    // Check 3: Professional ID 1 (idprof1)
    $professional_id = !empty($mysoc->idprof1) ? $mysoc->idprof1 : '';
    if (empty($professional_id)) {
        $diag['checks'][] = array('error', 'ID Profesional 1 no est&aacute; configurado en Inicio &gt; Admin &gt; Empresa/Organizaci&oacute;n. Django usa este campo para identificar la instancia.');
        return $diag;
    }
    $diag['checks'][] = array('ok', 'ID Profesional 1: <code>' . dol_escape_htmltag($professional_id) . '</code>');

    // Check 4: cURL available
    if (!function_exists('curl_init')) {
        $diag['checks'][] = array('error', 'La extensi&oacute;n PHP cURL no est&aacute; instalada. Es necesaria para enviar webhooks.');
        return $diag;
    }
    $diag['checks'][] = array('ok', 'PHP cURL: disponible');

    // Check 5: Send test webhook
    $test_data = array(
        'trigger_code' => 'TEST_CONNECTION',
        'timestamp' => dol_print_date(dol_now(), 'dayrfc'),
        'instance_name' => $mysoc->name,
    );

    $json_payload = json_encode($test_data);
    $signature = hash_hmac('sha256', $json_payload, $api_secret);

    $ch = curl_init($webhook_url);
    curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "POST");
    curl_setopt($ch, CURLOPT_POSTFIELDS, $json_payload);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, array(
        'Content-Type: application/json',
        'Content-Length: ' . strlen($json_payload),
        'X-Dolibarr-Signature: ' . $signature,
        'X-Dolibarr-Professional-ID: ' . $professional_id
    ));
    curl_setopt($ch, CURLOPT_TIMEOUT, 15);
    curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 10);

    $response_body = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $curl_errno = curl_errno($ch);
    $curl_error = curl_error($ch);
    $total_time = round(curl_getinfo($ch, CURLINFO_TOTAL_TIME), 2);
    curl_close($ch);

    // Evaluate result
    if ($curl_errno) {
        // Connection-level failure
        $error_map = array(
            6  => 'No se pudo resolver el nombre del servidor (DNS). Verifique que la URL es correcta.',
            7  => 'No se pudo conectar al servidor. Verifique que el servidor est&aacute; activo y accesible desde esta red.',
            28 => 'Tiempo de conexi&oacute;n agotado. El servidor no respondi&oacute; en 15 segundos.',
            35 => 'Error de SSL/TLS. Verifique el certificado del servidor.',
            51 => 'Certificado SSL del servidor no es v&aacute;lido.',
            60 => 'Certificado SSL del servidor no se pudo verificar.',
        );
        $msg = isset($error_map[$curl_errno])
            ? $error_map[$curl_errno]
            : 'Error cURL #' . $curl_errno . ': ' . dol_escape_htmltag($curl_error);
        $diag['checks'][] = array('error', 'Conexi&oacute;n fallida: ' . $msg);
        return $diag;
    }

    $diag['checks'][] = array('ok', 'Conexi&oacute;n establecida (' . $total_time . 's)');

    // Check HTTP response
    if ($http_code == 200) {
        $response_data = json_decode($response_body, true);
        $instance_name = isset($response_data['instance']) ? $response_data['instance'] : '';
        $diag['checks'][] = array('ok', 'Django respondi&oacute; HTTP 200 OK');
        if ($instance_name) {
            $diag['checks'][] = array('ok', 'Instancia reconocida en Django: <strong>' . dol_escape_htmltag($instance_name) . '</strong>');
        }
        $diag['checks'][] = array('ok', '<strong>Conexi&oacute;n verificada exitosamente.</strong>');
        $diag['success'] = true;
    } elseif ($http_code == 400) {
        $response_data = json_decode($response_body, true);
        $error_msg = isset($response_data['error']) ? $response_data['error'] : 'Error desconocido';

        if (strpos($error_msg, 'HMAC') !== false) {
            $diag['checks'][] = array('error', 'HTTP 400: Firma HMAC inv&aacute;lida. El API Secret en Dolibarr no coincide con el de Django Admin &gt; Dolibarr Instances.');
        } elseif (strpos($error_msg, 'Unknown') !== false || strpos($error_msg, 'professional_id') !== false) {
            $diag['checks'][] = array('error', 'HTTP 400: Instancia no reconocida. El ID Profesional 1 (<code>' . dol_escape_htmltag($professional_id) . '</code>) no existe en Django Admin &gt; Dolibarr Instances &gt; Professional ID.');
        } elseif (strpos($error_msg, 'Missing') !== false) {
            $diag['checks'][] = array('error', 'HTTP 400: Headers de autenticaci&oacute;n faltantes. Respuesta: ' . dol_escape_htmltag($error_msg));
        } else {
            $diag['checks'][] = array('error', 'HTTP 400: ' . dol_escape_htmltag($error_msg));
        }
    } elseif ($http_code == 404) {
        $diag['checks'][] = array('error', 'HTTP 404: La URL del webhook no existe en el servidor Django. Verifique que la ruta sea <code>/api/webhook/dolibarr/</code>');
    } elseif ($http_code == 429) {
        $diag['checks'][] = array('warning', 'HTTP 429: Demasiadas solicitudes. El servidor est&aacute; limitando las peticiones. Espere unos minutos e intente de nuevo.');
    } elseif ($http_code == 500) {
        $diag['checks'][] = array('error', 'HTTP 500: Error interno del servidor Django. Revise los logs del servidor.');
    } elseif ($http_code == 502 || $http_code == 503) {
        $diag['checks'][] = array('error', 'HTTP ' . $http_code . ': El servidor Django no est&aacute; disponible. Verifique que gunicorn est&aacute; corriendo.');
    } else {
        $diag['checks'][] = array('error', 'HTTP ' . $http_code . ': Respuesta inesperada. Body: ' . dol_escape_htmltag(substr($response_body, 0, 200)));
    }

    return $diag;
}

// UI Setup
$page_name = "Payroll Connect Setup";
llxHeader('', $page_name);
$linkback = '<a href="' . DOL_URL_ROOT . '/admin/modules.php?restore_lastsearch_values=1">' . $langs->trans("BackToModuleList") . '</a>';

print load_fiche_titre($page_name, $linkback, 'title_setup');

// Configuration tabs
$head = payrollconnect_admin_prepare_head();
print dol_get_fiche_head($head, 'settings', $page_name, -1, 'payroll_connect@payroll_connect');

// Help box
print '<div class="opacitymedium" style="margin-bottom: 12px;">';
print 'Este m&oacute;dulo env&iacute;a webhooks al servidor Django de n&oacute;minas cada vez que se valida una factura, presupuesto, nota de cr&eacute;dito o se crea un producto. ';
print 'La comunicaci&oacute;n se autentica con firma HMAC-SHA256.';
print '</div>';

print '<form method="POST" action="' . $_SERVER["PHP_SELF"] . '">';
print '<input type="hidden" name="action" value="set">';
print '<input type="hidden" name="token" value="' . newToken() . '">';

print '<table class="noborder centpercent">';
print '<tr class="liste_titre"><td>' . $langs->trans("Parameter") . '</td><td>' . $langs->trans("Value") . '</td><td>' . $langs->trans("Status") . '</td></tr>';

// Webhook URL
$webhook_val = getDolGlobalString('PAYROLL_CONNECT_WEBHOOK_URL');
print '<tr class="oddeven">';
print '<td>Webhook URL<br><span class="opacitymedium small">Endpoint del servidor Django. Ejemplo: <code>https://salarios.ejemplo.com/api/webhook/dolibarr/</code></span></td>';
print '<td><input type="url" name="PAYROLL_CONNECT_WEBHOOK_URL" value="' . dol_escape_htmltag($webhook_val) . '" size="60" placeholder="https://salarios.ejemplo.com/api/webhook/dolibarr/"></td>';
print '<td>' . (!empty($webhook_val) ? img_picto('OK', 'tick') : img_picto('No configurado', 'warning')) . '</td>';
print '</tr>';

// API Secret
$secret_val = getDolGlobalString('PAYROLL_CONNECT_API_SECRET');
print '<tr class="oddeven">';
print '<td>API Secret (HMAC-SHA256)<br><span class="opacitymedium small">Clave compartida con Django. Generar con: <code>python3 -c "import secrets; print(secrets.token_hex(32))"</code><br>Debe ser id&eacute;ntica en Django Admin &gt; Dolibarr Instances &gt; Api secret.</span></td>';
print '<td><input type="password" name="PAYROLL_CONNECT_API_SECRET" value="' . dol_escape_htmltag($secret_val) . '" size="60"></td>';
print '<td>' . (!empty($secret_val) ? img_picto('OK', 'tick') : img_picto('No configurado', 'warning')) . '</td>';
print '</tr>';

// ID Profesional 1 (read-only, from company config)
global $mysoc;
$idprof1 = !empty($mysoc->idprof1) ? $mysoc->idprof1 : '';
print '<tr class="oddeven">';
print '<td>ID Profesional 1<br><span class="opacitymedium small">Se lee de Inicio &gt; Admin &gt; Empresa/Organizaci&oacute;n. Debe coincidir con Django Admin &gt; Dolibarr Instances &gt; Professional ID.</span></td>';
print '<td><code>' . (!empty($idprof1) ? dol_escape_htmltag($idprof1) : '<span class="warning">No configurado</span>') . '</code></td>';
print '<td>' . (!empty($idprof1) ? img_picto('OK', 'tick') : img_picto('Falta configurar', 'error')) . '</td>';
print '</tr>';

print '</table>';

print '<div class="center" style="margin-top: 8px;"><input type="submit" class="button" value="' . $langs->trans("Save") . '"></div>';
print '</form>';

// Test Connection Button
print '<div class="tabsAction">';
if (!empty($webhook_val) && !empty($secret_val) && !empty($idprof1)) {
    print '<a class="butAction" href="' . $_SERVER["PHP_SELF"] . '?action=testconnect&token=' . newToken() . '#testresult">Verificar Conexi&oacute;n</a>';
} else {
    print '<a class="butActionRefused classfortooltip" href="#" title="Configure todos los par&aacute;metros antes de verificar la conexi&oacute;n">Verificar Conexi&oacute;n</a>';
}
print '</div>';

// Display test results
if ($test_result !== null) {
    print '<a id="testresult"></a>';
    print '<div class="div-table-responsive-no-min">';
    print '<table class="noborder centpercent">';
    print '<tr class="liste_titre"><td colspan="2">Resultado de la verificaci&oacute;n</td></tr>';

    foreach ($test_result['checks'] as $check) {
        $type = $check[0];
        $msg = $check[1];

        if ($type == 'ok') {
            $icon = img_picto('OK', 'tick');
            $css = 'color: #27ae60;';
        } elseif ($type == 'warning') {
            $icon = img_picto('Advertencia', 'warning');
            $css = 'color: #e67e22;';
        } else {
            $icon = img_picto('Error', 'error');
            $css = 'color: #e74c3c;';
        }

        print '<tr class="oddeven"><td style="width: 30px; text-align: center;">' . $icon . '</td>';
        print '<td style="' . $css . '">' . $msg . '</td></tr>';
    }

    print '</table>';
    print '</div>';
}

// Help: required Django-side configuration
print '<br>';
print '<div class="opacitymedium small">';
print '<strong>Configuraci&oacute;n requerida en Django:</strong><br>';
print '1. Admin &gt; Dolibarr Instances &gt; crear instancia con el <strong>ID Profesional 1</strong> de esta empresa (Admin &gt; Empresa/Organizaci&oacute;n) y el mismo API Secret.<br>';
print '2. Admin &gt; Dolibarr User Identities &gt; vincular cada empleado con su <strong>User ID</strong> de Dolibarr (visible en la URL: <code>/user/card.php?id=<strong>N</strong></code>).';
print '</div>';

print dol_get_fiche_end();

llxFooter();
