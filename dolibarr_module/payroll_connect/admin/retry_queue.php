<?php
/* Copyright (C) 2026 Bambinounos
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 */

// Load Dolibarr environment
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

// Process retry queue manually (Resync Manual per FEASIBILITY_REPORT 2.1)
if ($action == 'process_queue') {
    if (GETPOST('token', 'alpha') != newToken()) {
        setEventMessages("Security token expired. Please try again.", null, 'errors');
    } else {
        $processed = PayrollConnectHelper::processRetryQueue($db);
        if ($processed > 0) {
            setEventMessages("$processed event(s) successfully re-sent to payroll system.", null, 'mesgs');
        } else {
            setEventMessages("No pending events to process, or all retries failed.", null, 'warnings');
        }
    }
}

// Retry a single specific event
if ($action == 'retry_one') {
    if (GETPOST('token', 'alpha') != newToken()) {
        setEventMessages("Security token expired.", null, 'errors');
    } else {
        $queue_id = GETPOST('id', 'int');
        if ($queue_id > 0) {
            $webhook_url = getDolGlobalString('PAYROLL_CONNECT_WEBHOOK_URL');
            $api_secret = getDolGlobalString('PAYROLL_CONNECT_API_SECRET');

            $sql = "SELECT payload FROM " . MAIN_DB_PREFIX . "payroll_connect_retry_queue WHERE rowid = " . (int) $queue_id;
            $resql = $db->query($sql);
            if ($resql && $obj = $db->fetch_object($resql)) {
                $data = json_decode($obj->payload, true);
                if ($data) {
                    $result = PayrollConnectHelper::sendToDjango($webhook_url, $api_secret, $data);
                    if ($result !== false) {
                        $sql_update = "UPDATE " . MAIN_DB_PREFIX . "payroll_connect_retry_queue SET status = 'processed', date_processed = '" . $db->idate(dol_now()) . "' WHERE rowid = " . (int) $queue_id;
                        $db->query($sql_update);
                        setEventMessages("Event #$queue_id re-sent successfully.", null, 'mesgs');
                    } else {
                        setEventMessages("Failed to resend event #$queue_id.", null, 'errors');
                    }
                }
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
print dol_get_fiche_head($head, 'retryqueue', $page_name, -1, 'payroll_connect@payroll_connect');

// Stats summary
$stats = PayrollConnectHelper::getRetryQueueStats($db);
print '<div class="info">';
print 'Pending events: <strong>' . $stats['pending'] . '</strong> | ';
print 'Failed events (max retries reached): <strong style="color:red;">' . $stats['failed'] . '</strong>';
print '</div><br>';

// Manual process button
print '<form method="POST" action="' . $_SERVER["PHP_SELF"] . '">';
print '<input type="hidden" name="action" value="process_queue">';
print '<input type="hidden" name="token" value="' . newToken() . '">';
print '<input type="submit" class="button" value="Process Retry Queue Now">';
print '</form><br>';

// List pending/failed events
$sql = "SELECT rowid, trigger_code, status, attempts, date_creation, date_next_retry";
$sql .= " FROM " . MAIN_DB_PREFIX . "payroll_connect_retry_queue";
$sql .= " WHERE status IN ('pending', 'failed')";
$sql .= " ORDER BY date_creation DESC";
$sql .= " LIMIT 100";

$resql = $db->query($sql);
if ($resql) {
    $num = $db->num_rows($resql);
    print '<table class="noborder centpercent">';
    print '<tr class="liste_titre">';
    print '<td>ID</td><td>Trigger</td><td>Status</td><td>Attempts</td><td>Created</td><td>Next Retry</td><td>Action</td>';
    print '</tr>';

    if ($num == 0) {
        print '<tr class="oddeven"><td colspan="7" class="center">No pending events in retry queue.</td></tr>';
    }

    while ($obj = $db->fetch_object($resql)) {
        print '<tr class="oddeven">';
        print '<td>' . $obj->rowid . '</td>';
        print '<td>' . dol_escape_htmltag($obj->trigger_code) . '</td>';
        print '<td>' . dol_escape_htmltag($obj->status) . '</td>';
        print '<td>' . $obj->attempts . '</td>';
        print '<td>' . dol_print_date($db->jdate($obj->date_creation), 'dayhour') . '</td>';
        print '<td>' . ($obj->date_next_retry ? dol_print_date($db->jdate($obj->date_next_retry), 'dayhour') : '-') . '</td>';
        print '<td>';
        print '<a class="button buttongen" href="' . $_SERVER["PHP_SELF"] . '?action=retry_one&id=' . $obj->rowid . '&token=' . newToken() . '">Retry Now</a>';
        print '</td>';
        print '</tr>';
    }

    print '</table>';
}

print dol_get_fiche_end();

llxFooter();
