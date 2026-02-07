<?php
/* Copyright (C) 2026 Bambinounos
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 */

/**
 * Dashboard widget: Shows Payroll Connect webhook delivery status.
 * Per FEASIBILITY_REPORT section 2.1: "Dashboard Widget" -
 * Visual indicator on Dolibarr home alerting about connection failures.
 */

include_once DOL_DOCUMENT_ROOT . '/core/boxes/modules_boxes.php';
require_once __DIR__ . '/../../lib/payroll_connect.lib.php';

class box_payroll_connect_status extends ModeleBoxes
{
    public $boxcode = "payrollconnectstatus";
    public $boximg = "payroll_connect@payroll_connect";
    public $boxlabel = "PayrollConnectWidgetTitle";
    public $depends = array("payroll_connect");

    public $info_box_head = array();
    public $info_box_contents = array();

    public function __construct($db, $param = '')
    {
        global $user;
        $this->db = $db;
        parent::__construct($db, $param);
        $this->enabled = $user->admin;
    }

    /**
     * Load data into info_box_contents array to show widget
     *
     * @param int $max Maximum number of records to load
     * @return void
     */
    public function loadBox($max = 5)
    {
        global $langs;

        $langs->load("payroll_connect@payroll_connect");

        $this->info_box_head = array(
            array('text' => $langs->trans("PayrollConnectWidgetTitle"))
        );

        $stats = PayrollConnectHelper::getRetryQueueStats($this->db);
        $line = 0;

        if ($stats['pending'] > 0) {
            $this->info_box_contents[$line][] = array(
                'td' => 'class="tdoverflowmax200"',
                'text' => img_warning() . ' ' . $stats['pending'] . ' ' . $langs->trans("PayrollConnectPending"),
            );
            $this->info_box_contents[$line][] = array(
                'td' => 'class="right"',
                'text' => '<a href="' . dol_buildpath('/payroll_connect/admin/retry_queue.php', 1) . '">' . $langs->trans("RetryQueue") . '</a>',
            );
            $line++;
        }

        if ($stats['failed'] > 0) {
            $this->info_box_contents[$line][] = array(
                'td' => 'class="tdoverflowmax200"',
                'text' => img_error() . ' ' . $stats['failed'] . ' ' . $langs->trans("PayrollConnectFailed"),
            );
            $this->info_box_contents[$line][] = array(
                'td' => 'class="right"',
                'text' => '<a href="' . dol_buildpath('/payroll_connect/admin/retry_queue.php', 1) . '">' . $langs->trans("RetryQueue") . '</a>',
            );
            $line++;
        }

        if ($stats['pending'] == 0 && $stats['failed'] == 0) {
            $this->info_box_contents[$line][] = array(
                'td' => 'class="center"',
                'text' => img_picto('', 'tick') . ' ' . $langs->trans("PayrollConnectAllClear"),
            );
            $line++;
        }
    }

    /**
     * Method to show box
     *
     * @param array $head     Array with properties of box title
     * @param array $contents Array with properties of box lines
     * @param int   $nooutput If 1, return string
     * @return string
     */
    public function showBox($head = null, $contents = null, $nooutput = 0)
    {
        return parent::showBox($this->info_box_head, $this->info_box_contents, $nooutput);
    }
}
