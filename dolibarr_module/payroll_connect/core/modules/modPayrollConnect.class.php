<?php
include_once DOL_DOCUMENT_ROOT . '/core/modules/DolibarrModules.class.php';

class modPayrollConnect extends DolibarrModules
{
    public function __construct($db)
    {
        global $langs, $conf;

        $this->db = $db;
        $this->numero = 505050; // New Unique ID
        $this->rights_class = 'payroll_connect';
        $this->family = "hr";
        $this->module_position = 50;
        $this->name = preg_replace('/^mod/i', '', get_class($this));
        $this->part_of_version = '1.0';
        $this->version = '1.0';
        $this->revision = '1';
        $this->editor_name = 'Antigravity / Google Deepmind';
        $this->editor_url = 'https://google.com';

        $this->img_warning = '';
        $this->error = '';

        $this->dirs = array();

        $this->confirminstall = array();
        $this->confirmuninstall = array();

        $this->depends = array();
        $this->requiredby = array();
        $this->conflictwith = array();
        $this->langfiles = array("payroll_connect@payroll_connect"); // Requires lang file
        $this->phpmin = array(7, 0);
        $this->need_remote = 0;

        // Validations
        $this->description = "Syncs Sales and Product data to Payroll System.";

        $this->const = array();
        $this->tabs = array();

        // Permissions
        $this->rights = array();
        $this->rights[0][0] = 505051;
        $this->rights[0][1] = 'Read configuration';
        $this->rights[0][2] = 'r';
        $this->rights[0][3] = 0;
        $this->rights[0][4] = 'admin';

        $this->rights[1][0] = 505052;
        $this->rights[1][1] = 'Configure module';
        $this->rights[1][2] = 'w';
        $this->rights[1][3] = 0;
        $this->rights[1][4] = 'setup';
    }

    public function init($options = '')
    {
        $this->remove($options);
        $sql = array();
        return $this->_init($sql, $options);
    }

    public function remove($options = '')
    {
        $sql = array();
        return $this->_remove($sql, $options);
    }
}
?>