<?php
// Load admin header
require '../../main.inc.php';
require_once DOL_DOCUMENT_ROOT . '/core/lib/admin.lib.php';
require_once '../lib/payroll_connect.lib.php';

// Access control
if (!$user->admin) {
    accessforbidden();
}

$action = GETPOST('action', 'alpha');

// Save settings
if ($action == 'set') {
    $webhook_url = trim($_POST['PAYROLL_CONNECT_WEBHOOK_URL']);
    $api_secret = trim($_POST['PAYROLL_CONNECT_API_SECRET']);

    $res1 = dolibarr_set_const($db, "PAYROLL_CONNECT_WEBHOOK_URL", $webhook_url, 'chaine', 0, '', $conf->entity);
    $res2 = dolibarr_set_const($db, "PAYROLL_CONNECT_API_SECRET", $api_secret, 'chaine', 0, '', $conf->entity);

    if ($res1 && $res2) {
        setEventMessages("Configuration Saved", null, 'mesgs');
    } else {
        setEventMessages("Error Saving Configuration", null, 'errors');
    }
}

// UI Setup
$page_name = "Payroll Connect Setup";
llxHeader('', $page_name);
$linkback = '<a href="' . DOL_URL_ROOT . '/admin/modules.php?restore_lastsearch_values=1">' . $langs->trans("BackToModuleList") . '</a>';

print load_fiche_titre($page_name, $linkback, 'title_setup');

print '<form method="POST" action="' . $_SERVER["PHP_SELF"] . '">';
print '<input type="hidden" name="action" value="set">';
print '<input type="hidden" name="token" value="' . newToken() . '">';

print '<table class="noborder" width="100%">';
print '<tr class="liste_titre"><td>Parameter</td><td>Value</td></tr>';

// Webhook URL
print '<tr class="oddeven"><td>Webhook URL (Django)</td>';
print '<td><input type="text" name="PAYROLL_CONNECT_WEBHOOK_URL" value="' . $conf->global->PAYROLL_CONNECT_WEBHOOK_URL . '" size="60"></td></tr>';

// API Secret
print '<tr class="oddeven"><td>API Secret (HMAC Key)</td>';
print '<td><input type="password" name="PAYROLL_CONNECT_API_SECRET" value="' . $conf->global->PAYROLL_CONNECT_API_SECRET . '" size="60"></td></tr>';

print '</table>';

print '<div class="center"><input type="submit" class="button" value="' . $langs->trans("Save") . '"></div>';
print '</form>';

llxFooter();
?>