<?php
/* Copyright (C) 2026 Bambinounos
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 */

/**
 * Prepare admin pages header (tabs)
 *
 * @return array Array of tabs for admin pages
 */
function payrollconnect_admin_prepare_head()
{
    global $langs, $conf;

    $h = 0;
    $head = array();

    $head[$h][0] = dol_buildpath("/payroll_connect/admin/setup.php", 1);
    $head[$h][1] = $langs->trans("Settings");
    $head[$h][2] = 'settings';
    $h++;

    $head[$h][0] = dol_buildpath("/payroll_connect/admin/retry_queue.php", 1);
    $head[$h][1] = $langs->trans("RetryQueue");
    $head[$h][2] = 'retryqueue';
    $h++;

    complete_head_from_modules($conf, $langs, null, $head, $h, 'payroll_connect@payroll_connect');
    complete_head_from_modules($conf, $langs, null, $head, $h, 'payroll_connect@payroll_connect', 'remove');

    return $head;
}

/**
 * Helper class for sending webhooks to Django payroll system
 */
class PayrollConnectHelper
{
    /**
     * Sends a payload to the Django Webhook with HMAC-SHA256 authentication.
     *
     * @param string $webhook_url URL configured in setup
     * @param string $api_secret  Secret configured in setup
     * @param array  $data        Data to send
     * @return bool|string        Response body on success, false on failure
     */
    public static function sendToDjango($webhook_url, $api_secret, $data)
    {
        global $db, $conf, $mysoc;

        if (empty($webhook_url) || empty($api_secret)) {
            dol_syslog("PayrollConnect: sendToDjango called without URL or Secret.", LOG_WARNING);
            return false;
        }

        $json_payload = json_encode($data);

        // Calculate HMAC-SHA256 Signature
        $signature = hash_hmac('sha256', $json_payload, $api_secret);

        // Company identifier: "ID Profesional 1" from Dolibarr admin/company.php
        $professional_id_1 = !empty($mysoc->idprof1) ? $mysoc->idprof1 : '';

        if (empty($professional_id_1)) {
            dol_syslog("PayrollConnect: WARNING - ID Profesional 1 (idprof1) is not set in company config. Webhook will fail authentication.", LOG_ERR);
        }

        // Curl Setup
        $ch = curl_init($webhook_url);
        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "POST");
        curl_setopt($ch, CURLOPT_POSTFIELDS, $json_payload);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);

        // Headers
        $headers = array(
            'Content-Type: application/json',
            'Content-Length: ' . strlen($json_payload),
            'X-Dolibarr-Signature: ' . $signature,
            'X-Dolibarr-Professional-ID: ' . $professional_id_1
        );
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
        curl_setopt($ch, CURLOPT_TIMEOUT, 10);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 5);

        $result = curl_exec($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $curl_error = curl_error($ch);
        curl_close($ch);

        if ($http_code >= 200 && $http_code < 300) {
            dol_syslog("PayrollConnect: Webhook sent successfully to $webhook_url. HTTP $http_code", LOG_INFO);
            return $result;
        }

        dol_syslog("PayrollConnect: Webhook FAILED to $webhook_url. HTTP $http_code. cURL error: $curl_error. Response: $result", LOG_ERR);
        return false;
    }

    /**
     * Queue a failed webhook event for retry.
     * Creates a record in llx_payroll_connect_retry_queue.
     * Per FEASIBILITY_REPORT section 2.1: "Cola de Reintentos".
     *
     * @param DoliDB $db   Database handler
     * @param array  $data The payload that failed to send
     * @return int         ID of the queued record, or -1 on error
     */
    public static function queueForRetry($db, $data)
    {
        $json_payload = json_encode($data);
        $now = dol_now();

        $sql = "INSERT INTO " . MAIN_DB_PREFIX . "payroll_connect_retry_queue";
        $sql .= " (payload, trigger_code, status, attempts, date_creation, date_next_retry)";
        $sql .= " VALUES (";
        $sql .= "'" . $db->escape($json_payload) . "',";
        $sql .= "'" . $db->escape($data['trigger_code']) . "',";
        $sql .= "'pending',";
        $sql .= "0,";
        $sql .= "'" . $db->idate($now) . "',";
        // First retry in 15 minutes
        $sql .= "'" . $db->idate($now + (15 * 60)) . "'";
        $sql .= ")";

        $resql = $db->query($sql);
        if ($resql) {
            $id = $db->last_insert_id(MAIN_DB_PREFIX . "payroll_connect_retry_queue");
            dol_syslog("PayrollConnect: Event queued for retry. Queue ID: $id, trigger: " . $data['trigger_code'], LOG_WARNING);
            return $id;
        }

        dol_syslog("PayrollConnect: CRITICAL - Failed to queue event for retry: " . $db->lasterror(), LOG_ERR);
        return -1;
    }

    /**
     * Process pending items in the retry queue.
     * Called by cron job or manual resync.
     *
     * @param DoliDB $db Database handler
     * @return int Number of successfully processed items
     */
    public static function processRetryQueue($db)
    {
        global $conf;

        $webhook_url = getDolGlobalString('PAYROLL_CONNECT_WEBHOOK_URL');
        $api_secret = getDolGlobalString('PAYROLL_CONNECT_API_SECRET');

        if (empty($webhook_url) || empty($api_secret)) {
            return 0;
        }

        $now = dol_now();
        $max_attempts = 10;
        $processed = 0;

        $sql = "SELECT rowid, payload, attempts FROM " . MAIN_DB_PREFIX . "payroll_connect_retry_queue";
        $sql .= " WHERE status = 'pending'";
        $sql .= " AND date_next_retry <= '" . $db->idate($now) . "'";
        $sql .= " AND attempts < " . $max_attempts;
        $sql .= " ORDER BY date_creation ASC";
        $sql .= " LIMIT 50";

        $resql = $db->query($sql);
        if ($resql) {
            while ($obj = $db->fetch_object($resql)) {
                $data = json_decode($obj->payload, true);
                if (!$data) continue;

                $result = self::sendToDjango($webhook_url, $api_secret, $data);
                $new_attempts = $obj->attempts + 1;

                if ($result !== false) {
                    // Success: mark as processed
                    $sql_update = "UPDATE " . MAIN_DB_PREFIX . "payroll_connect_retry_queue";
                    $sql_update .= " SET status = 'processed', attempts = " . $new_attempts;
                    $sql_update .= ", date_processed = '" . $db->idate($now) . "'";
                    $sql_update .= " WHERE rowid = " . $obj->rowid;
                    $db->query($sql_update);
                    $processed++;
                } else {
                    // Failure: update attempts and schedule next retry (exponential backoff: 15, 30, 60, 120... min)
                    $delay_minutes = 15 * pow(2, min($new_attempts - 1, 6));
                    $next_retry = $now + ($delay_minutes * 60);

                    $new_status = ($new_attempts >= $max_attempts) ? 'failed' : 'pending';

                    $sql_update = "UPDATE " . MAIN_DB_PREFIX . "payroll_connect_retry_queue";
                    $sql_update .= " SET attempts = " . $new_attempts;
                    $sql_update .= ", status = '" . $new_status . "'";
                    $sql_update .= ", date_next_retry = '" . $db->idate($next_retry) . "'";
                    $sql_update .= " WHERE rowid = " . $obj->rowid;
                    $db->query($sql_update);
                }
            }
        }

        return $processed;
    }

    /**
     * Get count of pending retries (for dashboard widget).
     * Per FEASIBILITY_REPORT section 2.1: "Dashboard Widget".
     *
     * @param DoliDB $db Database handler
     * @return array     Array with 'pending' and 'failed' counts
     */
    public static function getRetryQueueStats($db)
    {
        $stats = array('pending' => 0, 'failed' => 0);

        $sql = "SELECT status, COUNT(*) as cnt FROM " . MAIN_DB_PREFIX . "payroll_connect_retry_queue";
        $sql .= " WHERE status IN ('pending', 'failed')";
        $sql .= " GROUP BY status";

        $resql = $db->query($sql);
        if ($resql) {
            while ($obj = $db->fetch_object($resql)) {
                $stats[$obj->status] = (int) $obj->cnt;
            }
        }

        return $stats;
    }
}
