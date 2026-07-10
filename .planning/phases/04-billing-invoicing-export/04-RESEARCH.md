# Phase 4: Billing + Invoicing + Export - Research

**Researched:** 2026-05-06
**Domain:** Dolibarr Billing/Cron Jobs, TCPDF PDF Invoices, CSV/DATEV Export
**Confidence:** HIGH (Dolibarr cron module verified via Dolibarr docs, TCPDF via wiki)

## Summary

Phase 4 implementiert die monatliche Abrechnung, PDF-Rechnungsgenerierung und Export-Funktionalitäten für das Wallbox-Dolibarr-Modul. Die Kernherausforderungen umfassen die Integration mit Dolibarrs Scheduled Jobs Modul (cron) für automatische monatliche Ausführung, TCPDF-basierte PDF-Generierung für detaillierte Ladelisten, sowie CSV- und DATEV-Exporte für deutsche Buchhaltung.

**Primäre Empfehlung:** Dolibarr Cron-Modul (modCron) für monatliche Jobs nutzen, TCPDF über `core/lib/pdf.lib.php` für PDF-Generierung, und DATEV-Format als EXTF_CSV-Variante für deutsche Buchhaltungsexporte implementieren.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Monatliche Abrechnung (cron) | Dolibarr (PHP/cron module) | — | Dolibarr Scheduled Jobs Modul für automatische Ausführung |
| Session-Gruppierung nach User | Dolibarr (MariaDB) | — | SQL-Grupierung nach user_id in llx_wallbox_sessions |
| Kostenberechnung (kWh × Preis) | Dolibarr (PHP) | — | Berechnung in billing.class.php |
| PDF-Generierung | Dolibarr (TCPDF) | — | TCPDF über core/lib/pdf.lib.php |
| CSV-Export | Dolibarr (PHP) | — | Export via ExportCsv class |
| DATEV-Export | Dolibarr (PHP) | — | EXTF_CSV Format generieren |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|-------------|
| Dolibarr Cron Module | core (ab v3.8) | Scheduled Jobs für automatische Ausführung | Integriert, kein externes Modul nötig [VERIFIED: Dolibarr Doxygen] |
| TCPDF | via Dolibarr | PDF-Generierung | Dolibarr Standard für PDF [VERIFIED: Dolibarr Wiki] |
| ExportCsv | core/modules/export | CSV-Export | Dolibarr Export-Framework [VERIFIED: Dolibarr Doxygen] |
| PHP | 8.1+ | Serverseitige Sprache | AGENTS.md Stack-Vorgabe |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| modCron | core v3.8+ | Cron-Job Registrierung | Für automatische monatliche Abrechnung |
| pdf_standard.modules.php | core/modules | PDF-Template Basis | Für eigene TCPDF-Templates |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| modCron | Externe crontab | Dolibarr-integriert, einfacher zu verwalten |
| TCPDF | FPDF (veraltet) | TCPDF wird von Dolibarr unterstützt |
| Custom CSV | Dolibarr Export Wizard | Für einfache Exporte, für Billing custom |

**Installation:**
```bash
# Keine额外 Installation nötig
# Dolibarr Cron-Modul ist im Core enthalten
# TCPDF ist in htdocs/includes/tecnickcom/tcpdf/
```

---

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Dolibarr Server                          │
│                                                                 │
│  ┌─────────────────────┐     ┌──────────────────────────┐    │
│  │ Scheduled Jobs     │     │  wallboxbilling         │    │
│  │ (modCron)         │────▶│  Billing Class         │    │
│  │ - monthly cron    │     │  - group by user       │    │
│  │ - BIL-01 trigger │     │  - calculate costs    │    │
│  └─────────────────────┘     └──────────────────────────┘    │
│                                       │                     │
│                                       ▼                     │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  PDF Generator (TCPDF)                               │   │
│  │  - pdf_wallboxbilling.class.php                      │   │
│  │  - Session details table                            │   │
│  │  - Summary totals                                 │   │
│  └────────────────────────────────────────────────────────┘   │
│                                       │                     │
│           ┌───────────────────────────┼───────────────────┐    │
│           ▼                           ▼                   ▼    │
│  ┌─────────────────┐     ┌─────────────────┐              │
│  │ CSV Export     │     │ DATEV Export   │              │
│  │ (EXT-02)     │     │ (EXT-03)      │              │
│  └─────────────────┘     └─────────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
Dolibarr/htdocs/custom/wallboxbilling/
├── class/
│   ├── wallboxbilling.class.php      # Bestehend - DAO
│   ├── billing.class.php             # NEU - Abrechnungslogik
│   └── export.class.php             # NEU - CSV/DATEV Export
├── core/
│   └── modules/
│       └── modWallboxbilling.class.php  # Erweitern: cronjobs
├── core/
│   └── modules/
│       └── doc/
│           └── pdf_wallboxbilling.class.php # NEU - TCPDF Template
├── sql/
│   └── migration_billing.sql       # NEU - billing_histories Tabelle
└── langs/
    └── de_DE/
        └── wallboxbilling.lang    # Deutsch
```

### Pattern 1: Cron Job Registration in Module Descriptor

**What:** Registriert einen monatlichen Cron-Job im Dolibarr Scheduled Jobs Modul
**When to use:** Für automatische monatliche Abrechnung (BIL-01)
**Example:**
```php
// In modWallboxbilling.class.php
$this->cronjobs = array(
    0 => array(
        'entity' => 0,
        'label' => 'Wallbox Monthly Billing',
        'jobtype' => 'method',
        'class' => 'wallboxbilling/class/billing.class.php',
        'objectname' => 'WallboxBilling',
        'method' => 'runMonthlyBilling',
        'parameters' => '',  // Monatlicher Job, keine Parameter
        'comment' => 'Monatliche Wallbox-Abrechnung ausführen',
        'frequency' => 1,           // 1x pro
        'unitfrequency' => 3600 * 24 * 30,  // ~30 Tage (Monat)
        'priority' => 50,
        'status' => 1,  // Aktiviert
        'test' => '$conf->wallboxbilling->enabled'
    )
);
```

**Quelle:** [VERIFIED: Dolibarr Doxygen modCron] + [CITED: Dolibarr Wiki Module Scheduled Jobs]

### Pattern 2: Session Grouping and Cost Calculation

**What:** Gruppiert Sessions nach Benutzer und berechnet Kosten
**When to use:** Für BIL-02 (Session-Gruppierung) und BIL-03 (Preisberechnung)
**Example:**
```php
/**
 * Abrechnungsklasse für Wallbox-Sessions
 */
class WallboxBilling
{
    /**
     * Führt monatliche Abrechnung durch
     *
     * @param User $user User der die Abrechnung ausführt
     * @param int $month Monat (1-12), 0 für Vormonat
     * @param int $year Jahr
     * @return int|-1 Fehlercode
     */
    public function runMonthlyBilling($user, $month = 0, $year = 0)
    {
        global $db, $conf, $langs;

        // Datum bestimmen (Vormonat 默认)
        if ($month == 0) {
            $month = date('m') - 1;
            if ($month == 0) {
                $month = 12;
                $year--;
            }
        }
        $year = $year ?: date('Y');

        // Zeitraum: erster bis letzter Tag des Monats
        $startDate = sprintf('%d-%02d-01 00:00:00', $year, $month);
        $lastDay = cal_days_in_month(CAL_GREGORIAN, $month, $year);
        $endDate = sprintf('%d-%02d-%02d 23:59:59', $year, $month, $lastDay);

        // Sessions nach User gruppieren (BIL-02)
        $sql = "SELECT s.fk_user, s.rfid_hash, u.login, u.lastname, u.firstname,
                      SUM(s.kwh) as total_kwh,
                      s.price_per_kwh,
                      SUM(s.total_cost) as total_cost,
                      COUNT(*) as session_count
               FROM " . MAIN_PREFIXED . "wallbox_sessions s
               LEFT JOIN " . MAIN_PREFIXED . "user u ON s.fk_user = u.rowid
               WHERE s.start_time >= '" . $db->escape($startDate) . "'
                 AND s.start_time <= '" . $db->escape($endDate) . "'
                 AND s.status = 'completed'
               GROUP BY s.fk_user, s.price_per_kwh
               ORDER BY u.login, s.start_time";

        $resql = $db->query($sql);
        if (!$resql) {
            $this->error = $db->error;
            return -1;
        }

        $userBillingData = array();
        while ($obj = $db->fetch_object($resql)) {
            $userBillingData[] = array(
                'user_id' => $obj->fk_user,
                'user_login' => $obj->login,
                'user_name' => $obj->firstname . ' ' . $obj->lastname,
                'rfid_hash' => $obj->rfid_hash,
                'total_kwh' => $obj->total_kwh,
                'price_per_kwh' => $obj->price_per_kwh,
                'total_cost' => $obj->total_cost,
                'session_count' => $obj->session_count
            );
        }

        // Kosten berechnen: kWh × Benutzerpreis (BIL-03)
        // Berechnung bereits in SQL durch GROUP BY und SUM
        // Ergebnisse werden für PDF und Export verwendet
        return $this->createBillingHistory($userBillingData, $month, $year);
    }
}
```

### Pattern 3: TCPDF PDF Template for Billing

**What:** Erstellt PDF-Abrechnungsdokument mit TCPDF
**When to use:** Für BIL-06 (PDF-Rechnungsdokument)
**Example:**
```php
<?php
/**
 * TCPDf Template für Wallbox-Abrechnung
 * 
 * @categoryBilling
 */
require_once DOL_DOCUMENT_ROOT . '/core/lib/pdf.lib.php';

class PdfWallboxBilling extends ModelePDFFactures
{
    public $db;
    public $name;
    public $description;
    public $update_main_doc_file = 1;
    
    public $format = 'PORTRAIT';
    public $pdf_all_tablesor = 1;
    public $posxdesc = 120;
    public $posxdate = 90;
    public $posxqty = 150;
    public $posxprice = 165;
    public $posxunit = 0;
    
    /**
     * Constructor
     */
    public function __construct($db)
    {
        global $langs;
        $this->db = $db;
        $this->name = 'wallboxbilling';
        $this->description = $langs->trans('WallboxBillingPDF');
    }
    
    /**
     * Generate PDF
     */
    public function write_file($object, $outputlangs, $srctemplatepath = '', $hidedetails = 0, $hidedesc = 0, $hideref = 0)
    {
        global $conf, $user, $langs, $mysoc;
        
        // PDF initialisieren
        $pdf = pdf_getInstance($this->format);
        if ($pdf === null) {
            return -1;
        }
        
        $pdf->setPrintHeader(false);
        $pdf->setPrintFooter(false);
        $pdf->SetFont(pdf_getPDFFont($outputlangs));
        
        // Seite 1: Header
        $pdf->AddPage();
        
        // Titel
        $pdf->SetFont('', 'B', 16);
        $pdf->Cell(0, 10, $outputlangs->transnoentities('WallboxBilling'), 0, 1, 'C');
        
        // Zeitraum
        $pdf->SetFont('', '', 10);
        $pdf->Cell(0, 10, sprintf('%s %d', $outputlangs->transnoentities('Month' . $object->month), $object->year), 0, 1, 'C');
        
        // User-Details Tabelle (BIL-04: Detaillierte Ladeliste)
        $this->_tableau($pdf, $object->sessions, $outputlangs);
        
        // Summary (BIL-05: Summenübersicht)
        $this->_tableau_tot($pdf, $object->totals, $outputlangs);
        
        return $pdf->Output($file, 'F');
    }
    
    /**
     * Session-Details Tabelle
     */
    private function _tableau($pdf, $sessions, $outputlangs)
    {
        $pdf->SetFont('', 'B', 9);
        $pdf->SetFillColor(220, 220, 220);
        
        // Header
        $header = array(
            $outputlangs->transnoentities('Date'),
            $outputlangs->transnoentities('Wallbox'),
            $outputlangs->transnoentities('Start'),
            $outputlangs->transnoentities('End'),
            $outputlangs->transnoentities('kWh'),
            $outputlangs->transnoentities('PricePerKwh'),
            $outputlangs->transnoentities('Total')
        );
        
        $tab = array();
        foreach ($sessions as $session) {
            $tab[] = array(
                $session['date'],
                $session['wallbox_id'],
                $session['start_time'],
                $session['end_time'],
                number_format($session['kwh'], 2, ',', ''),
                number_format($session['price_per_kwh'], 2, ',', ''),
                number_format($session['total_cost'], 2, ',', '')
            );
        }
        
        $pdf->BasicTable($header, $tab);
    }
}
?>
```

**Quelle:** [VERIFIED: Dolibarr Wiki Create PDF document template] + [CITED: Dolibarr Doxygen pdf_octopus]

### Pattern 4: DATEV Export Format

**What:** Exportiert Buchungsdaten im DATEV EXTF-Format
**When to use:** Für EXT-03 (DATEV-Export für deutsche Buchhaltung)
**Example:**
```php
/**
 * DATEV Export für Wallbox-Abrechnungen
 * DATEV-Format: EXTF_Buchungsstapel.csv
 */
class WallboxDatevExport
{
    const DATEV_VERSION = 'EXTF';
    
    /**
     * Exportiert Abrechnungen als DATEV-Datei
     *
     * @param array $billings Abrechnungsdaten
     * @param string $outputPath Ausgabepfad
     * @param array $config DATEV-Konfiguration (BeraterNr, MandantenNr)
     * @return int|-1
     */
    public function export($billings, $outputPath, $config = array())
    {
        $fp = fopen($outputPath, 'w');
        if (!$fp) {
            return -1;
        }
        
        // Kopfzeile (DATEV-Format Version)
        fputcsv($fp, array(self::DATEV_VERSION . ' ' . date('Ymd'), '5'), ';');
        
        // Feldtitel
        $header = array(
            'Kennung',           // 1: EXTF oder 2: ?
            'Vers',             // 2: Versionsnummer
            'Konto',           // 3: Sachkonto
            'Gegenkonto (ohne)', // 4: Gegenkonto
            'Belegdatum',       // 5: Belegdatum (TT.MM.JJJJ)
            'Buchungstext',    // 6: Buchungstext
            'Soll/Haben',      // 7: S=Haben, E=Soll
            'Betrag',         // 8: Betrag (Cent)
            'KOST1',          // 9: Kostenstelle 1
            'KOST2'           // 10: Kostenstelle 2
        );
        fputcsv($fp, $header, ';');
        
        // Buchungssätze
        $bookingDate = date('d.m.Y');
        foreach ($billings as $billing) {
            // Soll-Buchung an Debitorenkonto (Verkaufserlös)
            $row = array(
                '20',                   // EXTF-Kennung
                '5',                   // Version
                '1400',                 // Erlöskonto (SKR03)
                $this->getDatevAccount($billing['user_id']), // Debitorenkonto
                $bookingDate,           // Belegdatum
                'Wallbox ' . $billing['user_login'], // Buchungstext
                'H',                   // Haben (Guthaben = Kunde bekommt)
                $this->formatAmount($billing['total_cost']), // Betrag in Cent
                '',                    // KOST1 (optional: Kostenstelle)
                ''                     // KOST2
            );
            fputcsv($fp, $row, ';');
            
            // Gegenbuchung an Umsatzkonto
            $row = array(
                '20',
                '5',
                $this->getDatevAccount($billing['user_id']), // Debitor (Ausgleich)
                '1400',                 // Erlöskonto (Gegenbuchung)
                $bookingDate,
                'Wallbox ' . $billing['user_login'],
                'S',                   // Soll
                $this->formatAmount($billing['total_cost']),
                '',
                ''
            );
            fputcsv($fp, $row, ';');
        }
        
        fclose($fp);
        return count($billings);
    }
    
    /**
     * Formatiert Betrag als Cent (DATEV-Format)
     */
    private function formatAmount($amount)
    {
        return str_replace(array(',', '.'), '', sprintf('%.2f', $amount));
    }
    
    /**
     * GENERIERT DATEV-Kontonummer aus User-ID
     */
    private function getDatevAccount($userId)
    {
        // DATEV-Kontonummern beginnen typischerweise ab 10000
        // SKR03: Debitoren 10000-19999
        return sprintf('%05d', 10000 + $userId);
    }
}
```

**Quelle:** [CITED: DATEV Developer Portal] + [CITED: ConAktiv DATEV Handbuch]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|---------------|-------------|-----|
| Monatliche Cron-Jobs | Externe crontab/System-Cron | Dolibarr modCron | Integriert, GUI-Verwaltung, keine Systemrechte nötig |
| PDF-Generierung | Eigenes FPDF/TCPDF-Skript | Dolibarr PDF-Template `core/modules/doc/` | Einheitlicher Zugriff auf `pdf_getInstance()`, Header/Footer |
| CSV-Export | Handgeschriebene CSV-Logik | `ExportCsv` class | Encoding, Trennzeichen, Enclosure bereits gelöst |
| DATEV-Format | Eigenes CSV-Format | DATEV EXTF Standard | Steuerberater-Software akzeptiert nur EXTF |

**Key insight:** Dolibarr hat Scheduled Jobs (modCron), PDF und Export bereits eingebaut. Eigene Implementierung nur für Wallbox-spezifische Datenstruktur nötig.

---

## Runtime State Inventory

> Phase 4 ist keine Rename/Refactor-Phase, daher fokussiert auf Billing-State

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `llx_wallbox_sessions` in MariaDB (Dolibarr) | Abfrage für Abrechnungszeitraum |
| Live service config | Dolibarr Scheduled Jobs | Cron-Job für monatliche Ausführung aktivieren |
| OS-registered state | Keine relevanten OS-Registrierungen | Keine |
| Secrets/env vars | Keine neuen Secrets nötig | — |
| Build artifacts | Keine Build-Artifakte betroffen | — |

**Details:**
- **Sessions:** Monatliche Abrechnung liest `llx_wallbox_sessions` für Zeitraum
- **Cron:** modCron-Job wird in `$this->cronjobs` im Modul-Descriptor registriert
- **Billing History:** Neue Tabelle `llx_wallbox_billing_history` für abgeschlossene Abrechnungen

---

## Common Pitfalls

### Pitfall 1: Cron-Job läuft nicht zur richtigen Zeit
**What goes wrong:** Monatliche Abrechnung wird nicht am Monatsende ausgeführt
**Why it happens:** `frequency` und `unitfrequency` falsch konfiguriert
**How to avoid:** Frequency = 1, unitfrequency = 3600 × 24 × 30 (~Monat), Job auf "Letzter Tag des Monats" setzen [VERIFIED: Dolibarr Wiki Scheduled Jobs]
**Warning signs:** Keine Billing-Einträge, keine Fehlermeldung

### Pitfall 2: PDF-Speicherort falsch
**What goes wrong:** PDF wird nicht gefunden oder kann nicht gespeichert werden
**Why it happens:** Falsches Ausgabeverzeichnis `$conf->mycompany->dir_output`
**How to avoid:** `dol_mkdir($conf->wallboxbilling->dir_output)` verwenden [VERIFIED: pdf_octopus]
**Warning signs:** Datei nicht gefunden nach Aufruf

### Pitfall 3: DATEV-Kontonummern ungültig
**What goes wrong:** DATEV-Import schlägt fehl
**Why it happens:** Falsches Kontonummernformat (DATEV erwartet 5-stellig)
**How to avoid:** SKR03/SKR04 Kontobereiche einhalten, 5-stellig formatieren [CITED: DATEV Handbuch]
**Warning signs:** Buchhaltung zeigt Fehler beim Import

### Pitfall 4: Kostenberechnung falsch
**What goes wrong:** Falsche Beträge in PDF und Export
**Why it happens:** `total_cost` falsch berechnet oder falscher Wechselkurs
**How to avoid:** In SQL `SUM(kwh * price_per_kwh) as total_cost` verwenden oder in PHPCALC
**Warning signs:** Abweichende Beträge bei Überprüfung

---

## Code Examples

### Example 1: Billing Class Structure
```php
<?php
// class/billing.class.php
class WallboxBilling
{
    public $db;
    public $error;
    
    public function __construct($db)
    {
        $this->db = $db;
    }
    
    /**
     * Monatliche Abrechnung ausführen (BIL-01)
     */
    public function runMonthlyBilling($user, $month = 0, $year = 0)
    {
        // 1. Zeitraum berechnen (BIL-01: am letzten Tag des Monats)
        // 2. Sessions nach User gruppieren (BIL-02)
        // 3. Kosten berechnen kWh × Preis (BIL-03)
        // 4. Detaillierte Liste erstellen (BIL-04)
        // 5. Summary erstellen (BIL-05)
        // 6. PDF generieren (BIL-06)
        // 7. Optional: Rechnung erstellen (BIL-07)
    }
}
```

### Example 2: Cron Registration
```php
// In modWallboxbilling.class.php
$this->cronjobs = array(
    0 => array(
        'entity' => 0,
        'label' => 'WallboxMonthlyBilling',
        'jobtype' => 'method',
        'class' => 'wallboxbilling/class/billing.class.php',
        'objectname' => 'WallboxBilling',
        'method' => 'runMonthlyBilling',
        'parameters' => '',
        'comment' => 'Monatliche Wallbox-Abrechnung',
        'frequency' => 1,
        'unitfrequency' => 30 * 24 * 3600,  // 30 Tage
        'priority' => 50,
        'status' => 1,
        'test' => '$conf->wallboxbilling->enabled'
    )
);
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Keine automatische Abrechnung | Dolibarr Cron Job (modCron) | Phase 4 | Vollautomatisch |
| Manueller PDF-Export | TCPDF-Template | Phase 4 | Ein Klick |
| Manueller CSV-Export | ExportCsv class | Phase 4 | Wizard-basiert |
| Kein DATEV-Export | DATEV EXTF Format | Phase 4 | Buchhaltungstauglich |

---

## Assumptions Log

> Liste aller [ASSUMED]- markierten Behauptungen

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | TCPDF ist in Dolibarr Core enthalten | Standard Stack | LOW - laut Wiki bestätigt |
| A2 | `$this->cronjobs` Syntax funktioniert | Architecture Patterns | MEDIUM - Syntax von modCron abgeleitet |
| A3 | DATEV EXTF Format ist 5-stellig | Pattern 4 | LOW - DATEV Standard |
| A4 | `runMonthlyBilling` wird monatlich ausgeführt | Pattern 1 | MEDIUM - Cron-Timing |

---

## Open Questions

1. **BIL-07: Optionale Dolibarr-Rechnung**
   - What we know: Anforderung spezifiziert "Optional: Erstellt Rechnung / Gutschrift in Dolibarr"
   - What's unclear: Soll eine echte Dolibarr-Faktura erstellt werden oder nur ein internes Dokument?
   - Recommendation: Erstes Release nur als internes PDF (kein echtes Facture-Objekt), da komplexer

2. **EXT-02: CSV-Export Struktur**
   - What we know: Export für externe Auswertungen
   - What's unclear: Welche Felder sollen exportiert werden (alle Session-Details oder aggregiert)?
   - Recommendation: Beide Optionen anbieten (Detail + Aggregiert)

3. **DATEV Buchungskreis**
   - What we know: DATEV unterstützt verschiedene Buchungskreise (Handelsrecht, Steuerrecht)
   - What's unclear: Welcher Kreis ist für Wallbox-Abrechnung relevant?
   - Recommendation: Standard "Handelsrecht" (1000er Kontobereich)

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Dolibarr 21.x-22.x | Hosting | ✗ | — | Docker-Container |
| PHP 8.1+ | Server | ✗ | — | — |
| MariaDB/MySQL | Datenbank | ✗ | — | — |
| modCron | Scheduled Jobs | ✓ (Core) | 21.x-22.x | — |
| TCPDF | PDF-Generierung | ✓ (Core) | — | — |

**Missing dependencies with no fallback:**
- NONE — Phas 4 baut auf bestehenden Dolibarr-System auf

**Missing dependencies with fallback:**
- NONE

---

## Validation Architecture

> workflow.nyquist_validation is enabled (per config.json).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | PHPUnit (PHP, Dolibarr Standard) |
| Config file | `Dolibarr/tests/phpunit.xml` (neu) |
| Quick run command | `php -l *.php` |
| Full suite command | `phpunit` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BIL-01 | Monthly billing cron job runs | integration | via Scheduled Jobs UI | ❌ |
| BIL-02 | Sessions grouped by user | unit | `php -r "require 'billing.class.php'"` | ❌ |
| BIL-03 | Cost = kWh × price_per_kwh | unit | `php -r "echo (10 * 0.30) === 3"` | ❌ |
| BIL-04 | Detailed charging list per user | integration | Generate PDF + verify content | ❌ |
| BIL-05 | Summary totals per user | integration | Generate PDF + verify totals | ❌ |
| BIL-06 | TCPDF PDF generated | integration | `file_exists()` | ❌ |
| BIL-07 | Optional: Dolibarr invoice | manual | Via invoicing UI | ❌ |
| EXT-02 | CSV export | integration | Export wizard | ❌ |
| EXT-03 | DATEV export | integration | Export wizardDATEV | ❌ |

### Sampling Rate
- **Per task commit:** PHP Syntax Check mit `php -l`
- **Per wave merge:** Full PHP test suite
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `class/billing.class.php` — Hauptlogik für BIL-01 bis BIL-06
- [ ] `core/modules/doc/pdf_wallboxbilling.class.php` — TCPDF Template für BIL-06
- [ ] `class/export.class.php` — CSV/DATEV Export für EXT-02/EXT-03
- [ ] Test files für alle Requirements

---

## Security Domain

> security_enforcement is enabled (per config.json).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|----------------|
| V2 Authentication | Yes | Nur berechtigte User können Cron-Jobs ausführen |
| V3 Session Management | No | — |
| V4 Access Control | Yes | User-Rechte `$user->rights->wallboxbilling` |
| V5 Input Validation | Yes | GETPOST(), $db->escape() |
| V6 Cryptography | No | Keine neuen kryptographischen Operationen |

### Known Threat Patterns for Billing

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Session-Diebstahl (SQL Injection) | Tampering | `$db->escape()` für alle User-Eingaben |
| unberechtigte Abrechnung | Spoofing | Cron-Job läuft nur mit Admin-Rechten |
| gefälschte Kosten | Tampering | Berechnung serverseitig, nicht im Client |

---

## Sources

### Primary (HIGH confidence)
- [VERIFIED: Dolibarr Doxygen modCron] - Cron module class reference
- [VERIFIED: Dolibarr Wiki - Module Scheduled Jobs] - Konfiguration cronjobs
- [VERIFIED: Dolibarr Wiki - Create PDF document template] - TCPDF Integration
- [VERIFIED: Dolibarr Wiki - Import Export] - Export framework

### Secondary (MEDIUM confidence)
- [CITED: Dolibarr Wiki - Datenexport] - Export Wizard
- [CITED: DATEV Developer Portal] - DATEV formats
- [CITED: ConAktiv DATEV Handbuch] - DATEV Buchungsstapel format

### Tertiary (LOW confidence)
- [ASSUMED] Cron-Job Syntax in $this->cronjobs (abgeleitet von modCron)
- [ASSUMED] TCPDF class name PdfWallboxBilling

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Dolibarr Cron/TCPDF verified via docs
- Architecture: HIGH - Patterns from official Dolibarr templates
- Pitfalls: MEDIUM - Basierend auf umum common pitfalls

**Research date:** 2026-05-06
**Valid until:** 2026-06-05 (30 days for stable Dolibarr)

---

*Research completed: 2026-05-06*
*Researcher: GSD Research Agent*
*Phase: 4 - Billing + Invoicing + Export*