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
print '<tr class="liste_titre"><td>' . $langs->trans("Parameter") . '</td><td>' . $langs->trans("Value") . '</td></tr>';

// Webhook URL
$webhook_val = getDolGlobalString('PAYROLL_CONNECT_WEBHOOK_URL');
print '<tr class="oddeven">';
print '<td>Webhook URL<br><span class="opacitymedium small">Endpoint del servidor Django. Ejemplo: <code>https://salarios.ejemplo.com/api/webhook/dolibarr/</code></span></td>';
print '<td><input type="url" name="PAYROLL_CONNECT_WEBHOOK_URL" value="' . dol_escape_htmltag($webhook_val) . '" size="60" placeholder="https://salarios.ejemplo.com/api/webhook/dolibarr/"></td></tr>';

// API Secret
$secret_val = getDolGlobalString('PAYROLL_CONNECT_API_SECRET');
print '<tr class="oddeven">';
print '<td>API Secret (HMAC-SHA256)<br><span class="opacitymedium small">Clave compartida con Django. Generar con: <code>python3 -c "import secrets; print(secrets.token_hex(32))"</code><br>Debe ser id&eacute;ntica en Django Admin &gt; Dolibarr Instances &gt; Api secret.</span></td>';
print '<td><input type="password" name="PAYROLL_CONNECT_API_SECRET" value="' . dol_escape_htmltag($secret_val) . '" size="60"></td></tr>';

print '</table>';

print '<div class="center" style="margin-top: 8px;"><input type="submit" class="button" value="' . $langs->trans("Save") . '"></div>';
print '</form>';

// Help: required Django-side configuration
print '<br>';
print '<div class="opacitymedium small">';
print '<strong>Configuraci&oacute;n requerida en Django:</strong><br>';
print '1. Admin &gt; Dolibarr Instances &gt; crear instancia con el <strong>ID Profesional 1</strong> de esta empresa (Admin &gt; Empresa/Organizaci&oacute;n) y el mismo API Secret.<br>';
print '2. Admin &gt; Dolibarr User Identities &gt; vincular cada empleado con su <strong>User ID</strong> de Dolibarr (visible en la URL: <code>/user/card.php?id=<strong>N</strong></code>).';
print '</div>';

print dol_get_fiche_end();

llxFooter();
