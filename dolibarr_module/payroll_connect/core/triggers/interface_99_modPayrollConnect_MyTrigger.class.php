<?php
/* Copyright (C) 2026 Bambinounos
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 */

require_once DOL_DOCUMENT_ROOT . '/core/triggers/interface.class.php';
require_once __DIR__ . '/../../lib/payroll_connect.lib.php';

class interface_99_modPayrollConnect_MyTrigger extends InterfaceTriggers
{
    public function __construct($db)
    {
        $this->db = $db;
        $this->name = preg_replace('/^interface_99_|_[^_]+$/i', '', get_class($this));
        $this->family = "payroll_connect";
        $this->description = "Triggers for Payroll Connect integration: syncs invoices, proposals and product creations to Django payroll system.";
        $this->version = '1.1';
        $this->picto = 'payroll_connect@payroll_connect';
    }

    /**
     * Function called when a Dolibarr business event occurs.
     *
     * @param string    $action     Event action code
     * @param Object    $object     Object concerned
     * @param User      $user       User performing the action
     * @param Translate $langs      Translation object
     * @param Conf      $conf       Configuration object
     * @return int                  0=OK, <0=KO
     */
    public function run_trigger($action, $object, User $user, Translate $langs, Conf $conf)
    {
        global $db;

        // 1. BILL_VALIDATE (Invoice or Credit Note validated)
        // Dolibarr: type=0 = Standard Invoice, type=2 = Credit Note
        // Per FEASIBILITY_REPORT sections 2.1 events 2 & 3
        if ($action == 'BILL_VALIDATE') {
            $data = array(
                'trigger_code' => 'BILL_VALIDATE',
                'object' => array(
                    'id' => $object->id,
                    'ref' => $object->ref,
                    'type' => $object->type,  // 0=invoice, 2=credit note
                    'total_ht' => $object->total_ht,
                    'fk_user_author' => $object->user_author_id,
                    'fk_propal' => isset($object->fk_source_propal) ? $object->fk_source_propal : null,
                    'date_validation' => dol_print_date($object->date_validation, 'dayrfc'),
                )
            );
            return $this->send($data);
        }

        // 2. PROPAL_VALIDATE (Proposal/Proforma validated)
        elseif ($action == 'PROPAL_VALIDATE') {
            $data = array(
                'trigger_code' => 'PROPAL_VALIDATE',
                'object' => array(
                    'id' => $object->id,
                    'ref' => $object->ref,
                    'total_ht' => $object->total_ht,
                    'fk_user_author' => $object->user_author_id,
                    'date_validation' => dol_print_date($object->date_validation, 'dayrfc'),
                )
            );
            return $this->send($data);
        }

        // 3. PRODUCT_CREATE (New Product created)
        elseif ($action == 'PRODUCT_CREATE') {
            $data = array(
                'trigger_code' => 'PRODUCT_CREATE',
                'object' => array(
                    'id' => $object->id,
                    'ref' => $object->ref,
                    'fk_user_author' => $user->id,
                    'date_creation' => dol_print_date(dol_now(), 'dayrfc'),
                )
            );
            return $this->send($data);
        }

        return 0;
    }

    /**
     * Send data to Django via the helper, with retry queue on failure.
     *
     * @param array $data Payload to send
     * @return int 0=OK, -1=Error (queued for retry)
     */
    private function send($data)
    {
        global $conf;
        $webhook_url = getDolGlobalString('PAYROLL_CONNECT_WEBHOOK_URL');
        $api_secret = getDolGlobalString('PAYROLL_CONNECT_API_SECRET');

        if (empty($webhook_url) || empty($api_secret)) {
            dol_syslog("PayrollConnect: Module not configured (missing URL or Secret). Skipping.", LOG_WARNING);
            return 0;
        }

        $result = PayrollConnectHelper::sendToDjango($webhook_url, $api_secret, $data);

        if ($result === false) {
            // Queue for retry (per FEASIBILITY_REPORT section 2.1 "Cola de Reintentos")
            PayrollConnectHelper::queueForRetry($this->db, $data);
            return -1;
        }

        return 0;
    }
}
