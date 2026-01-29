<?php
require_once DOL_DOCUMENT_ROOT . '/core/triggers/interface.class.php';
require_once __DIR__ . '/../../lib/payroll_connect.lib.php';

class interface_99_modPayrollConnect_MyTrigger extends InterfaceTriggers
{
    public function __construct($db)
    {
        $this->db = $db;
        $this->name = preg_replace('/^interface_99_|_[^_]+$/i', '', get_class($this));
        $this->family = "payroll_connect";
        $this->description = "Triggers for Payroll Connect integration.";
        $this->version = '1.0';
        $this->picto = 'payroll_connect@payroll_connect';
    }

    public function run_trigger($action, $object, User $user, Translate $langs, Conf $conf)
    {
        global $db;

        // 1. BILL_VALIDATE (Invoice Validated)
        if ($action == 'BILL_VALIDATE') {
            $data = array(
                'trigger_code' => 'BILL_VALIDATE',
                'object' => array(
                    'id' => $object->id,
                    'ref' => $object->ref,
                    'total_ht' => $object->total_ht,
                    'fk_user_author' => $object->user_author_id,
                    'fk_propal' => isset($object->fk_source_propal) ? $object->fk_source_propal : null,
                )
            );
            $this->send($data);
        }

        // 2. PROPAL_VALIDATE (Proposal Validated)
        elseif ($action == 'PROPAL_VALIDATE') {
            $data = array(
                'trigger_code' => 'PROPAL_VALIDATE',
                'object' => array(
                    'id' => $object->id,
                    'ref' => $object->ref,
                    'total_ht' => $object->total_ht,
                    'fk_user_author' => $object->user_author_id
                )
            );
            $this->send($data);
        }

        // 3. PRODUCT_CREATE (New Product)
        elseif ($action == 'PRODUCT_CREATE') {
            $data = array(
                'trigger_code' => 'PRODUCT_CREATE',
                'object' => array(
                    'id' => $object->id,
                    'ref' => $object->ref,
                    'fk_user_author' => $user->id
                )
            );
            $this->send($data);
        }

        return 0;
    }

    private function send($data)
    {
        global $conf;
        $webhook_url = $conf->global->PAYROLL_CONNECT_WEBHOOK_URL;
        $api_secret = $conf->global->PAYROLL_CONNECT_API_SECRET;

        PayrollConnectHelper::sendToDjango($webhook_url, $api_secret, $data);
    }
}
?>