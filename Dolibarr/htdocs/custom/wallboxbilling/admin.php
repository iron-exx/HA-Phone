<?php
/**
 * admin.php — Wallbox Billing Administration v2
 *
 * 2 Tabs: Konfiguration | RFID-Verwaltung
 * Sessions werden direkt in Spesenabrechnung eingetragen (kein Status-Tab).
 */

require_once '../../../main.inc.php';
require_once '../core/modules/modWallboxbilling.class.php';

if (!$user->rights->wallboxbilling->admin) {
    accessforbidden();
}

$langs->load('wallboxbilling@wallboxbilling');

$action = GETPOST('action', 'alpha');

// WR-09: Tab gegen Whitelist validieren
$allowed_tabs = array('config', 'rfid');
$tab = GETPOST('tab', 'aZ09');
if (!in_array($tab, $allowed_tabs, true)) $tab = 'config';

// --- Action: Konfiguration speichern ---
if ($action == 'update') {
    checkToken();
    dolibarr_set_const($db, 'WALLBOXBILLING_DEFAULT_PRICE',
        GETPOST('WALLBOXBILLING_DEFAULT_PRICE', 'none'), 'chaine', 0, '', $conf->entity);
    dolibarr_set_const($db, 'WALLBOXBILLING_ADMIN_EMAIL',
        GETPOST('WALLBOXBILLING_ADMIN_EMAIL', 'email'), 'chaine', 0, '', $conf->entity);
    setEventMessages($langs->trans('Saved'), null, 'mesgs');
}

// --- Action: RFID speichern ---
if ($action == 'update_rfid') {
    checkToken();

    // Welcher Benutzer-Speichern-Button wurde gedrückt?
    $user_id = 0;
    foreach ($_POST as $key => $val) {
        if (preg_match('/^save_(\d+)$/', $key, $m)) {
            $user_id = (int)$m[1];
            break;
        }
    }

    if ($user_id > 0) {
        $rfid_hex    = trim(GETPOST('rfid_hex_'.$user_id, 'aZ09'));
        $cost_center = GETPOST('cost_center_'.$user_id, 'alphanohtml');

        // WR-05: Dezimalwert nicht mit 'alpha' filtern — manuelle Validierung
        $price_raw = trim(GETPOST('price_kwh_'.$user_id, 'none'));
        if (!preg_match('/^\d+(\.\d{1,4})?$/', $price_raw)) {
            setEventMessages($langs->trans('WallboxInvalidPrice'), null, 'errors');
        } else {
            $price_kwh = $price_raw;

            if (!empty($rfid_hex)) {
                // Neues RFID setzen (Hash berechnen, nie den Hash in Logs/Responses)
                $rfid_hash = hash('sha256', $rfid_hex);
                dol_syslog("Wallbox: saving RFID mapping for user_id=$user_id", LOG_INFO);
                // SEC-01: rfid_hash NICHT geloggt

                $sql = "INSERT INTO ".MAIN_DB_PREFIX."wallbox_rfid"
                     ." (fk_user, rfid_hash, price_kwh, cost_center)"
                     ." VALUES (".(int)$user_id.", '".$db->escape($rfid_hash)."',"
                     ." '".$db->escape($price_kwh)."', '".$db->escape($cost_center)."')"
                     ." ON DUPLICATE KEY UPDATE"
                     ."  fk_user=VALUES(fk_user),"
                     ."  price_kwh=VALUES(price_kwh),"
                     ."  cost_center=VALUES(cost_center)";
                if ($db->query($sql)) {
                    setEventMessages($langs->trans('RFIDHashSaved'), null, 'mesgs');
                } else {
                    setEventMessages($langs->trans('DatabaseError').': '.$db->lasterror(), null, 'errors');
                    dol_syslog("Wallbox update_rfid INSERT error for user_id=$user_id: ".$db->lasterror(), LOG_ERR);
                }
            } else {
                // WR-04: Nur Preis/Kostenstelle aktualisieren — alle RFIDs dieses Users
                // (Design: ein User = ein Preis, mehrere Karten erhalten denselben Satz)
                $sql = "UPDATE ".MAIN_DB_PREFIX."wallbox_rfid"
                     ." SET price_kwh='".$db->escape($price_kwh)."',"
                     ."     cost_center='".$db->escape($cost_center)."'"
                     ." WHERE fk_user=".(int)$user_id;
                if ($db->query($sql) && $db->affected_rows() > 0) {
                    setEventMessages($langs->trans('Saved'), null, 'mesgs');
                } elseif ($db->affected_rows() == 0) {
                    setEventMessages($langs->trans('WallboxNoRFIDToUpdate'), null, 'warnings');
                } else {
                    setEventMessages($langs->trans('DatabaseError').': '.$db->lasterror(), null, 'errors');
                    dol_syslog("Wallbox update_rfid UPDATE error for user_id=$user_id: ".$db->lasterror(), LOG_ERR);
                }
            }
        }
    }
}

// --- HTML Output ---
llxHeader('', $langs->trans('WallboxBillingSetup'));

$form = new Form($db);

// Design-System Styles
print '<style>
.wb-card{background:#fff;border:1px solid #E2E8F0;border-radius:10px;padding:24px;margin-bottom:20px}
.wb-card-title{font-size:14px;font-weight:700;color:#0F172A;margin:0 0 18px;padding-bottom:12px;
  border-bottom:1px solid #F1F5F9;display:flex;align-items:center;gap:8px}
.wb-form-row{display:grid;grid-template-columns:200px 1fr;gap:12px 16px;align-items:center;margin-bottom:12px}
.wb-form-label{font-size:13px;font-weight:500;color:#374151}
.wb-input{padding:8px 12px;border:1px solid #D1D5DB;border-radius:6px;font-size:13px;
  color:#1E293B;background:#fff;box-sizing:border-box;width:100%;max-width:320px;
  transition:border-color 150ms,box-shadow 150ms}
.wb-input:focus{border-color:#6366F1;outline:none;box-shadow:0 0 0 3px rgba(99,102,241,.12)}
.wb-input-sm{max-width:140px}
.wb-input-xs{max-width:100px}
.wb-btn{display:inline-flex;align-items:center;gap:5px;padding:6px 13px;border-radius:6px;
  font-size:12.5px;font-weight:500;cursor:pointer;border:1px solid transparent;
  transition:background 150ms,border-color 150ms;white-space:nowrap;text-decoration:none}
.wb-btn:focus{outline:2px solid #6366F1;outline-offset:2px}
.wb-btn-save{background:#6366F1;color:#fff;border-color:#6366F1}
.wb-btn-save:hover{background:#4F46E5;border-color:#4F46E5}
.wb-btn svg{flex-shrink:0}
.wb-wrap{overflow-x:auto;margin-bottom:24px}
.wb-t{width:100%;border-collapse:collapse;font-size:13.5px;white-space:nowrap}
.wb-t thead th{background:#F8FAFC;color:#475569;font-weight:700;font-size:11.5px;
  text-transform:uppercase;letter-spacing:.05em;padding:10px 14px;
  border-bottom:2px solid #E2E8F0;text-align:left}
.wb-t tbody tr{border-bottom:1px solid #F1F5F9;transition:background 120ms}
.wb-t tbody tr:hover{background:#F8FAFC}
.wb-t tbody td{padding:10px 14px;color:#1E293B;vertical-align:middle}
.wb-badge-has{display:inline-block;padding:2px 9px;border-radius:20px;
  font-size:11.5px;font-weight:700;background:#ECFDF5;color:#059669}
.wb-badge-none{display:inline-block;padding:2px 9px;border-radius:20px;
  font-size:11.5px;font-weight:700;background:#F1F5F9;color:#94A3B8}
.wb-code{display:inline-block;padding:2px 7px;background:#EEF2FF;color:#6366F1;
  border-radius:4px;font-family:monospace;font-size:11.5px;font-weight:600}
.wb-empty{text-align:center;padding:48px 20px;color:#94A3B8;font-size:13.5px}
.wb-section-title{font-size:13px;font-weight:700;color:#64748B;text-transform:uppercase;
  letter-spacing:.06em;padding:16px 0 8px;border-bottom:1px solid #F1F5F9;
  display:flex;align-items:center;gap:6px;margin-bottom:8px}
@media(max-width:768px){.wb-form-row{grid-template-columns:1fr}.wb-input{max-width:100%}}
@media(prefers-reduced-motion:reduce){.wb-t tbody tr,.wb-btn,.wb-input{transition:none}}
</style>';

print load_fiche_titre($langs->trans('WallboxBillingSetup'), '', 'title_setup.png');

// Tabs
$head = array();
$head[0][0] = $_SERVER['PHP_SELF'].'?tab=config';
$head[0][1] = $langs->trans('WallboxConfiguration');
$head[0][2] = 'config';
$head[1][0] = $_SERVER['PHP_SELF'].'?tab=rfid';
$head[1][1] = $langs->trans('WallboxUserRFIDManagement');
$head[1][2] = 'rfid';

print dol_get_fiche_head($head, $tab, $langs->trans('WallboxBillingSetup'), -1, 'title_setup');


// =====================================================================
// TAB: KONFIGURATION
// =====================================================================
if ($tab == 'config') {

    print '<form method="POST" action="'.$_SERVER['PHP_SELF'].'?tab=config">';
    print '<input type="hidden" name="token" value="'.newToken().'">';
    print '<input type="hidden" name="action" value="update">';

    print '<div class="wb-card">';
    print '<h3 class="wb-card-title">';
    print '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/></svg>';
    print htmlspecialchars($langs->trans('WallboxConfiguration'), ENT_QUOTES, 'UTF-8');
    print '</h3>';

    // Standardpreis
    print '<div class="wb-form-row">';
    print '<label class="wb-form-label" for="wb_price">'.htmlspecialchars($langs->trans('DefaultPricePerKwh'), ENT_QUOTES, 'UTF-8').'</label>';
    print '<div style="display:flex;align-items:center;gap:8px">';
    print '<input type="text" id="wb_price" name="WALLBOXBILLING_DEFAULT_PRICE" class="wb-input wb-input-sm"';
    print ' value="'.htmlspecialchars(getDolGlobalString('WALLBOXBILLING_DEFAULT_PRICE'), ENT_QUOTES, 'UTF-8').'"';
    print ' placeholder="0.30" pattern="\d+(\.\d{1,4})?" title="Dezimalzahl, z.B. 0.30">';
    print '<span style="font-size:13px;color:#64748B">€/kWh</span>';
    print '</div></div>';

    // Admin-E-Mail
    print '<div class="wb-form-row">';
    print '<label class="wb-form-label" for="wb_email">'.htmlspecialchars($langs->trans('WallboxAdminEmail'), ENT_QUOTES, 'UTF-8').'</label>';
    print '<input type="email" id="wb_email" name="WALLBOXBILLING_ADMIN_EMAIL" class="wb-input"';
    print ' value="'.htmlspecialchars(getDolGlobalString('WALLBOXBILLING_ADMIN_EMAIL'), ENT_QUOTES, 'UTF-8').'"';
    print ' placeholder="admin@example.com">';
    print '</div>';

    print '<div style="margin-top:20px;padding-top:16px;border-top:1px solid #F1F5F9">';
    print '<button type="submit" class="wb-btn wb-btn-save">';
    print '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
    print ' '.htmlspecialchars($langs->trans('Save'), ENT_QUOTES, 'UTF-8');
    print '</button>';
    print '</div>';

    print '</div>';

    // Info-Box: API-Endpoint
    print '<div class="wb-card" style="background:#F8FAFC">';
    print '<h3 class="wb-card-title">';
    print '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>';
    print 'API-Endpoint';
    print '</h3>';
    print '<p style="font-size:13px;color:#475569;margin:0 0 8px">'.htmlspecialchars($langs->trans('WallboxAPIInfo'), ENT_QUOTES, 'UTF-8').'</p>';
    print '<code style="font-size:12px;background:#EEF2FF;color:#4338CA;padding:4px 10px;border-radius:4px;display:inline-block">';
    print 'POST '.htmlspecialchars(DOL_MAIN_URL_ROOT, ENT_QUOTES, 'UTF-8').'/api/index.php/wallboxbilling/session';
    print '</code>';
    print '</div>';

    print '</form>';


// =====================================================================
// TAB: RFID-VERWALTUNG
// =====================================================================
} elseif ($tab == 'rfid') {

    // CR-05/SEC-01: rfid_hash NICHT in SELECT laden — nur rowid für UPDATE-Referenz
    $existing = array();
    $res_rfid = $db->query(
        "SELECT rowid, fk_user, price_kwh, cost_center FROM ".MAIN_DB_PREFIX."wallbox_rfid"
    );
    if ($res_rfid) {
        while ($obj_rfid = $db->fetch_object($res_rfid)) {
            $existing[(int)$obj_rfid->fk_user] = array(
                'rowid'       => (int)$obj_rfid->rowid,
                'price_kwh'   => $obj_rfid->price_kwh,
                'cost_center' => $obj_rfid->cost_center,
            );
        }
        $db->free($res_rfid);
    }

    print '<form method="POST" action="'.$_SERVER['PHP_SELF'].'?tab=rfid">';
    print '<input type="hidden" name="token" value="'.newToken().'">';
    print '<input type="hidden" name="action" value="update_rfid">';

    print '<div class="wb-wrap">';
    print '<table class="wb-t">';
    print '<thead><tr>';
    print '<th>'.htmlspecialchars($langs->trans('User'), ENT_QUOTES, 'UTF-8').'</th>';
    print '<th>RFID</th>';
    print '<th>'.htmlspecialchars($langs->trans('PricePerKWh'), ENT_QUOTES, 'UTF-8').'</th>';
    print '<th>'.htmlspecialchars($langs->trans('CostCenter'), ENT_QUOTES, 'UTF-8').'</th>';
    print '<th>'.htmlspecialchars($langs->trans('Action'), ENT_QUOTES, 'UTF-8').'</th>';
    print '</tr></thead>';
    print '<tbody>';

    $res_users = $db->query(
        "SELECT rowid, login, lastname, firstname FROM ".MAIN_DB_PREFIX."user"
       ." WHERE statut=1 ORDER BY login"
    );
    if ($res_users) {
        $num = $db->num_rows($res_users);
        if ($num == 0) {
            print '<tr><td colspan="5"><div class="wb-empty">'.htmlspecialchars($langs->trans('WallboxNoActiveUsers'), ENT_QUOTES, 'UTF-8').'</div></td></tr>';
        }
        while ($obj = $db->fetch_object($res_users)) {
            $uid    = (int)$obj->rowid;
            $mapped = isset($existing[$uid]) ? $existing[$uid] : null;
            $cur_price  = $mapped ? htmlspecialchars($mapped['price_kwh'], ENT_QUOTES, 'UTF-8') : '';
            $cur_center = $mapped ? htmlspecialchars($mapped['cost_center'], ENT_QUOTES, 'UTF-8') : '';

            print '<tr>';

            // Benutzer
            print '<td>';
            print '<span style="font-weight:500">'.htmlspecialchars(trim($obj->firstname.' '.$obj->lastname), ENT_QUOTES, 'UTF-8').'</span>';
            print '<br><span style="font-size:11.5px;color:#94A3B8">'.htmlspecialchars($obj->login, ENT_QUOTES, 'UTF-8').'</span>';
            print '</td>';

            // RFID-Status + Hex-Eingabe
            // CR-05: Kein rfid_hash im HTML — nur Status (zugeordnet / nicht zugeordnet)
            print '<td>';
            if ($mapped) {
                print '<span class="wb-badge-has">'.htmlspecialchars($langs->trans('WallboxRFIDAssigned'), ENT_QUOTES, 'UTF-8').'</span>';
                print '<br><span style="font-size:11px;color:#64748B;display:block;margin-top:3px">'.htmlspecialchars($langs->trans('WallboxEnterNewHex'), ENT_QUOTES, 'UTF-8').'</span>';
            } else {
                print '<span class="wb-badge-none">'.htmlspecialchars($langs->trans('WallboxRFIDNotAssigned'), ENT_QUOTES, 'UTF-8').'</span>';
            }
            print '<input type="text" name="rfid_hex_'.$uid.'" class="wb-input wb-input-sm"';
            print ' value="" placeholder="EFCD083E" style="margin-top:4px"';
            print ' autocomplete="off">';
            print '</td>';

            // Preis (WR-05: pattern-Attribut für clientseitige Validierung als Zusatzschutz)
            print '<td><div style="display:flex;align-items:center;gap:6px">';
            print '<input type="text" name="price_kwh_'.$uid.'" class="wb-input wb-input-xs"';
            print ' value="'.$cur_price.'" placeholder="0.30"';
            print ' pattern="\d+(\.\d{1,4})?" title="Dezimalzahl, z.B. 0.30">';
            print '<span style="font-size:12px;color:#64748B">€/kWh</span>';
            print '</div></td>';

            // Kostenstelle
            print '<td><input type="text" name="cost_center_'.$uid.'" class="wb-input wb-input-sm"';
            print ' value="'.$cur_center.'" placeholder="Projekt ABC">';
            print '</td>';

            // Speichern
            print '<td>';
            print '<button type="submit" name="save_'.$uid.'" class="wb-btn wb-btn-save">';
            print '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
            print ' '.htmlspecialchars($langs->trans('Save'), ENT_QUOTES, 'UTF-8');
            print '</button>';
            print '</td>';

            print '</tr>';
        }
        $db->free($res_users);
    }

    print '</tbody></table></div>';
    print '</form>';

    // Berechtigungen
    print '<div class="wb-section-title">';
    print '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>';
    print htmlspecialchars($langs->trans('Permissions'), ENT_QUOTES, 'UTF-8');
    print '</div>';

    print '<div class="wb-wrap">';
    print '<table class="wb-t">';
    print '<thead><tr>';
    print '<th>'.htmlspecialchars($langs->trans('Permission'), ENT_QUOTES, 'UTF-8').'</th>';
    print '<th>'.htmlspecialchars($langs->trans('Description'), ENT_QUOTES, 'UTF-8').'</th>';
    print '</tr></thead><tbody>';
    print '<tr><td><span class="wb-code">wallboxbilling.user</span></td><td>'.htmlspecialchars($langs->trans('ViewOwnSessions'), ENT_QUOTES, 'UTF-8').'</td></tr>';
    print '<tr><td><span class="wb-code">wallboxbilling.admin</span></td><td>'.htmlspecialchars($langs->trans('ManageAllSessions'), ENT_QUOTES, 'UTF-8').'</td></tr>';
    print '</tbody></table></div>';
}

print dol_fiche_end();
llxFooter();
?>
