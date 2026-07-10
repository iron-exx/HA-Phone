<?php
/**
 *  index.php - Liste der Ladevorgänge (Skeleton)
 */

require_once '../../../main.inc.php';
$langs->load('wallboxbilling.lang');

llxHeader('', $langs->trans('WallboxSessions'));

print load_fiche_titre($langs->trans('WallboxSessions'), '', 'title_wallbox.png');

// Vorbereitung für Phase 2: Sessions anzeigen
print '<p>'.$langs->trans('SessionsWillBeDisplayedHere').'</p>';

llxFooter();
?>
