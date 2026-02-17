<?php
/* Copyright (C) 2026 Bambinounos
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 */

include_once DOL_DOCUMENT_ROOT . '/core/modules/DolibarrModules.class.php';

class modPayrollConnect extends DolibarrModules
{
    public function __construct($db)
    {
        global $langs, $conf;

        $this->db = $db;
        $this->numero = 505050;
        $this->rights_class = 'payroll_connect';
        $this->family = "hr";
        $this->module_position = 50;
        $this->name = preg_replace('/^mod/i', '', get_class($this));
        $this->description = "Syncs Sales, Invoice, Credit Note and Product data to Django Payroll System via webhooks.";
        $this->descriptionlong = "Payroll Connect sends real-time webhook notifications to your Django-based payroll system when invoices are validated, proposals are confirmed, credit notes are issued, and products are created. Includes HMAC-SHA256 authentication and a retry queue for reliability.";

        $this->version = '1.1.6';
        $this->const_name = 'MAIN_MODULE_' . strtoupper($this->name);
        $this->picto = 'payroll_connect@payroll_connect';

        $this->editor_name = 'Bambinounos';
        $this->editor_url = 'https://github.com/bambinounos';

        // Admin setup page: links the gear icon in module list to admin/setup.php
        $this->config_page_url = array("setup.php@payroll_connect");

        $this->dirs = array();

        $this->depends = array();
        $this->requiredby = array();
        $this->conflictwith = array();
        $this->langfiles = array("payroll_connect@payroll_connect");
        $this->phpmin = array(7, 4);
        $this->need_dolibarr_version = array(16, 0);

        // Constants
        $this->const = array(
            0 => array('PAYROLL_CONNECT_WEBHOOK_URL', 'chaine', '', 'URL of the Django webhook endpoint', 0, 'current', 1),
            1 => array('PAYROLL_CONNECT_API_SECRET', 'chaine', '', 'HMAC-SHA256 secret for webhook authentication', 0, 'current', 1),
        );

        $this->tabs = array();

        // Permissions
        $this->rights = array();
        $this->rights[0][0] = 505051;
        $this->rights[0][1] = 'Read Payroll Connect configuration';
        $this->rights[0][2] = 'r';
        $this->rights[0][3] = 0;
        $this->rights[0][4] = 'admin';

        $this->rights[1][0] = 505052;
        $this->rights[1][1] = 'Configure Payroll Connect module';
        $this->rights[1][2] = 'w';
        $this->rights[1][3] = 0;
        $this->rights[1][4] = 'setup';

        // Cronjobs: process retry queue every 15 minutes
        $this->cronjobs = array(
            0 => array(
                'label' => 'PayrollConnect - Process Retry Queue',
                'jobtype' => 'method',
                'class' => '/payroll_connect/lib/payroll_connect.lib.php',
                'objectname' => 'PayrollConnectHelper',
                'method' => 'processRetryQueue',
                'parameters' => '',
                'comment' => 'Process pending webhook retries (exponential backoff)',
                'frequency' => 15,
                'unitfrequency' => 60,  // seconds -> every 15 minutes
                'status' => 1,
                'test' => '$conf->payroll_connect->enabled',
            ),
        );
    }

    /**
     * Function called when module is enabled.
     * Creates the retry queue table if it does not exist.
     *
     * @param string $options Options when enabling module
     * @return int 1 if OK, 0 if KO
     */
    public function init($options = '')
    {
        $this->remove($options);

        // Create retry queue table (compatible with MySQL and PostgreSQL)
        $sql = array();

        if ($this->db->type == 'pgsql') {
            $sql[] = "CREATE TABLE IF NOT EXISTS " . MAIN_DB_PREFIX . "payroll_connect_retry_queue ("
                . "rowid SERIAL PRIMARY KEY,"
                . "payload TEXT NOT NULL,"
                . "trigger_code VARCHAR(50) NOT NULL,"
                . "status VARCHAR(20) DEFAULT 'pending',"
                . "attempts INTEGER DEFAULT 0,"
                . "date_creation TIMESTAMP NOT NULL,"
                . "date_next_retry TIMESTAMP,"
                . "date_processed TIMESTAMP"
                . ")";
        } else {
            $sql[] = "CREATE TABLE IF NOT EXISTS " . MAIN_DB_PREFIX . "payroll_connect_retry_queue ("
                . "rowid INTEGER AUTO_INCREMENT PRIMARY KEY,"
                . "payload TEXT NOT NULL,"
                . "trigger_code VARCHAR(50) NOT NULL,"
                . "status VARCHAR(20) DEFAULT 'pending',"
                . "attempts INTEGER DEFAULT 0,"
                . "date_creation DATETIME NOT NULL,"
                . "date_next_retry DATETIME,"
                . "date_processed DATETIME"
                . ") ENGINE=InnoDB DEFAULT CHARSET=utf8";
        }

        // Index created separately for cross-DB compatibility
        $sql[] = "CREATE INDEX IF NOT EXISTS idx_retry_status_date ON "
            . MAIN_DB_PREFIX . "payroll_connect_retry_queue (status, date_next_retry)";

        return $this->_init($sql, $options);
    }

    /**
     * Function called when module is disabled.
     *
     * @param string $options Options when disabling module
     * @return int 1 if OK, 0 if KO
     */
    public function remove($options = '')
    {
        $sql = array();
        return $this->_remove($sql, $options);
    }
}
