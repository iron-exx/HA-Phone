<?php
/**
 * modWallboxbilling.class.php — Wallbox Billing Modul Descriptor v2
 *
 * Schlankes Modul: nur RFID-Zuordnungstabelle, kein Cron, kein Export.
 * Session-Daten gehen direkt in llx_expensereport / llx_expensereport_det.
 */

include_once DOL_DOCUMENT_ROOT.'/core/modules/DolibarrModules.class.php';

class modWallboxbilling extends DolibarrModules
{
    public function __construct($db)
    {
        global $conf, $langs;

        $this->db = $db;

        $this->numero         = 104000;
        $this->rights_class   = 'wallboxbilling';
        $this->family         = 'financial';
        $this->module_position = '80';

        // Name: Klassenname ohne führendes "mod" — Dolibarr erwartet einen String, kein Array
        $this->name = preg_replace('/^mod/i', '', get_class($this));

        $this->description = 'RFID-based EV charging — sessions recorded directly as expense report lines';

        $this->version    = '2.0.2';
        $this->const_name = 'MAIN_MODULE_'.strtoupper($this->name);
        $this->special    = 0;
        $this->picto      = 'fa-charging-station';

        // Konfigurationsseite (zeigt "Konfigurieren"-Button in der Modulliste)
        $this->config_page_url = array('admin.php@wallboxbilling');

        // Sprachdatei des Moduls — @modulname-Syntax für Dateien im Modul-Verzeichnis
        $this->langfiles = array('wallboxbilling@wallboxbilling');

        $this->depends      = array();
        $this->requiredby   = array();
        $this->conflictwith = array();

        $this->phpmin             = array(7, 1);
        $this->need_dolibarr_version = array(17, 0);

        // Berechtigungen — Schlüssel [4] entspricht $user->rights->wallboxbilling->{[4]}
        $this->rights = array();
        $r = 0;

        $this->rights[$r][0] = 104001;
        $this->rights[$r][1] = 'View own charging sessions';
        $this->rights[$r][4] = 'lire';
        $r++;

        $this->rights[$r][0] = 104002;
        $this->rights[$r][1] = 'Manage all charging sessions and RFID mappings';
        $this->rights[$r][4] = 'admin';
    }

    /**
     * Wird beim Aktivieren des Moduls aufgerufen.
     * Erstellt Tabellen + registriert Rechte/Konstanten via _init().
     *
     * @param string $options Optionen ('', 'noboxes')
     * @return int 1 = OK, <=0 = Fehler
     */
    public function init($options = '')
    {
        // Bestehende Rechte vor Neuanlage entfernen
        $this->remove($options);

        // Tabelle anlegen
        $create_sql = "CREATE TABLE IF NOT EXISTS `".MAIN_DB_PREFIX."wallbox_rfid` (
            `rowid`         INTEGER AUTO_INCREMENT PRIMARY KEY NOT NULL,
            `fk_user`       INTEGER NOT NULL,
            `rfid_hash`     VARCHAR(64) NOT NULL,
            `price_kwh`     DECIMAL(8,4) NOT NULL DEFAULT 0.3000,
            `cost_center`   VARCHAR(100) NOT NULL DEFAULT '',
            `date_creation` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `tms`           TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY `uk_rfid_hash` (`rfid_hash`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8";

        if ($this->db->query($create_sql) === false) {
            dol_syslog('modWallboxbilling init() CREATE TABLE error: '.$this->db->lasterror(), LOG_ERR);
        }

        // Upgrade-Pfad: fehlende Spalten ergänzen
        $this->_addColumnIfMissing(
            MAIN_DB_PREFIX.'wallbox_rfid',
            'price_kwh',
            "ALTER TABLE `".MAIN_DB_PREFIX."wallbox_rfid`"
            ." ADD COLUMN price_kwh DECIMAL(8,4) NOT NULL DEFAULT 0.3000 AFTER rfid_hash"
        );
        $this->_addColumnIfMissing(
            MAIN_DB_PREFIX.'wallbox_rfid',
            'cost_center',
            "ALTER TABLE `".MAIN_DB_PREFIX."wallbox_rfid`"
            ." ADD COLUMN cost_center VARCHAR(100) NOT NULL DEFAULT '' AFTER price_kwh"
        );

        // Rechte, Konstanten und Menüs in die DB eintragen (Standard-Dolibarr-Mechanismus)
        return $this->_init(array(), $options);
    }

    /**
     * Wird beim Deaktivieren des Moduls aufgerufen.
     *
     * @param string $options Optionen
     * @return int 1 = OK, <=0 = Fehler
     */
    public function remove($options = '')
    {
        return $this->_remove(array(), $options);
    }

    private function _addColumnIfMissing($table, $column, $alter_sql)
    {
        $res = $this->db->query(
            "SHOW COLUMNS FROM `".$this->db->escape($table)."` LIKE '".$this->db->escape($column)."'"
        );
        if (!$res || $this->db->num_rows($res) == 0) {
            if ($this->db->query($alter_sql) === false) {
                dol_syslog(
                    "modWallboxbilling _addColumnIfMissing($column) error: ".$this->db->lasterror(),
                    LOG_ERR
                );
            }
        }
    }
}
