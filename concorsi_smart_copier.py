#!/usr/bin/env python3
"""
CONCORSI SMART - COPIA AUTOMATICA v3.1
Compatibile con tutte le ASL su Concorsi Smart.
100% JavaScript - zero send_keys.

Uso: python3 concorsi_smart_copier.py [--debug]
"""

import csv, os, sys, time
from datetime import datetime

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
except ImportError:
    print("ERRORE: pip install selenium"); sys.exit(1)

PORT = 9222
TIMEOUT = 10
PAUSA = 2
DEBUG = "--debug" in sys.argv

SEZIONI = {
    "corsi": {
        "nome": "Corsi / Convegni / Congressi",
        "comp": "app-req-corsi",
        "btn": "Inserisci nuovo corso",
        "campi": [
            ("dataInizio","date"), ("dataFine","date"), ("attuale","checkbox"),
            ("datore","text"), ("indirizzoDatore","text"), ("descrizione1","text"),
            ("tipoCorso","select"), ("tipoRuolo","select"), ("durataOre","number"),
            ("esame","select"), ("crediti","number"), ("note","text"),
        ],
    },
    "pubblicazioni": {
        "nome": "Pubblicazioni / Articoli",
        "comp": "app-req-pubblicazioni",
        "btn": "Inserisci nuovo articolo",
        "campi": [
            ("tipoPubblicazione","select"), ("livelloPubblicazione","select"),
            ("titolo","text"), ("rivista","text"), ("numPagine","number"),
            ("dataPubblicazione","date"), ("autori","text"), ("isbn","text"),
            ("impactFactor","number"), ("singoloAutore","select"),
            ("tipoAutore","select"), ("note","text"),
        ],
    },
    "esperienze_pa": {
        "nome": "Esperienze Lavorative PA",
        "comp": "app-req-dipendente-asl-pa",
        "btn": "Inserisci nuova esperienza",
        "campi": [
            ("dataInizio","date"), ("dataFine","date"), ("attuale","checkbox"),
            ("datore","text"), ("indirizzoDatore","text"), ("tipoEnte","select"),
            ("estero","checkbox"),
            ("autoritaProvvedEstero","text"), ("numProvvedEstero","text"),
            ("_qualifica","autocomplete"),
            ("descrizione1","textarea"), ("tipoOrario","select"),
            ("percOreSettimanali","number"), ("tipoRapporto","select"),
            ("note","text"),
        ],
    },
    "titoli": {
        "nome": "Titoli di Studio",
        "comp": "app-req-titoli",
        "btn": "Inserisci nuovo titolo",
        "campi": [
            ("estero","checkbox"), ("tipo","select"),
            ("_denominazione","autocomplete"),
            ("istituto","text"), ("indirizzoIstituto","text"),
            ("specificheSpecializzazione","select"),
            ("dataConseguimento","date"), ("annoConseguimento","number"),
            ("durataLegale","number"), ("votazioneNumeratore","number"),
            ("votazioneDenominatore","number"), ("votazioneLode","checkbox"),
            ("votazioneText","text"), ("cicloDottorato","select"),
            ("settoriScientDisc","select"), ("areaDisciplina","textarea"),
            ("formazioneEstero","checkbox"), ("note","text"),
        ],
    },
}

def csv_key(c): return c[0].lstrip("_")
def dbg(msg):
    if DEBUG: print(f"    [DBG] {msg}")

# ============================================================================
# CONNESSIONE
# ============================================================================

def connetti():
    print(f"\n  Connessione Chrome porta {PORT}...")
    opts = Options()
    opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{PORT}")
    d = webdriver.Chrome(options=opts)
    print(f"  OK: {d.current_url}")
    return d

def js(drv, script, *args):
    return drv.execute_script(script, *args)

def is_readonly(drv):
    try:
        t = drv.find_element(By.TAG_NAME, "body").text
        return "DOMANDA INVIATA" in t and "DOMANDA NON INVIATA" not in t
    except: return False

def clicca_js(drv, el):
    try:
        js(drv, "arguments[0].scrollIntoView({block:'center'});", el)
        time.sleep(0.3)
        js(drv, "arguments[0].click();", el)
        return True
    except: return False

# ============================================================================
# CHECK: il campo e' REALMENTE nascosto? (solo display:none dei parent)
# Non check opacity - Angular usa opacity per animazioni ma il campo e' usabile
# ============================================================================

JS_IS_HIDDEN = """
(function(el){
    if(!el) return true;
    var p = el;
    while(p){
        var s = window.getComputedStyle(p);
        if(s.display === 'none') return true;
        p = p.parentElement;
    }
    return false;
})(arguments[0])
"""

# ============================================================================
# JAVASCRIPT: SCRITTURA CAMPI
# ============================================================================

JS_SET_INPUT = """
(function(el, val){
    el.focus();
    var setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, 'value').set;
    if(setter) setter.call(el, val);
    else el.value = val;
    el.dispatchEvent(new Event('input', {bubbles:true}));
    el.dispatchEvent(new Event('change', {bubbles:true}));
    el.dispatchEvent(new Event('blur', {bubbles:true}));
    return true;
})(arguments[0], arguments[1])
"""

JS_SET_TEXTAREA = """
(function(el, val){
    el.focus();
    var setter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype, 'value').set;
    if(setter) setter.call(el, val);
    else el.value = val;
    el.dispatchEvent(new Event('input', {bubbles:true}));
    el.dispatchEvent(new Event('change', {bubbles:true}));
    return true;
})(arguments[0], arguments[1])
"""

JS_SET_SELECT = """
(function(sel, val){
    for(var i=0; i<sel.options.length; i++){
        if(sel.options[i].value===val || sel.options[i].text===val){
            sel.selectedIndex = i;
            sel.dispatchEvent(new Event('change', {bubbles:true}));
            return true;
        }
    }
    return false;
})(arguments[0], arguments[1])
"""

JS_TYPE_AUTOCOMPLETE = """
(function(el, text){
    el.focus();
    var setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, 'value').set;
    // Clear
    if(setter) setter.call(el, '');
    else el.value = '';
    el.dispatchEvent(new Event('input', {bubbles:true}));
    // Type char by char
    for(var i=0; i<text.length; i++){
        var newVal = text.substring(0, i+1);
        if(setter) setter.call(el, newVal);
        else el.value = newVal;
        el.dispatchEvent(new InputEvent('input', {
            bubbles: true, data: text[i], inputType: 'insertText'
        }));
    }
    return true;
})(arguments[0], arguments[1])
"""

# ============================================================================
# LETTURA CAMPO
# ============================================================================

def leggi_campo(drv, name, tipo):
    if tipo == "autocomplete":
        try:
            el = drv.find_element(By.CSS_SELECTOR,
                "input[placeholder*='iniziare a digitare'], input[role='combobox']")
            return js(drv, "return arguments[0].value||'';", el)
        except: return ""
    try:
        el = drv.find_element(By.NAME, name)
    except: return ""
    try:
        if tipo == "select":
            return js(drv, "var s=arguments[0]; return (s.selectedIndex>=0)?s.options[s.selectedIndex].value:'';", el) or ""
        elif tipo == "checkbox":
            return "true" if js(drv, "return arguments[0].checked;", el) else "false"
        else:
            return js(drv, "return arguments[0].value||'';", el)
    except: return ""

# ============================================================================
# SCRITTURA CAMPO (tutto JS, solo skip se display:none)
# ============================================================================

def scrivi_campo(drv, name, tipo, valore):
    if not valore or valore == "null":
        return True
    if tipo == "checkbox" and valore.lower() in ("false","0","no"):
        return True

    # --- AUTOCOMPLETE (Material Angular via CDK overlay) ---
    if tipo == "autocomplete":
        try:
            el = drv.find_element(By.CSS_SELECTOR,
                "input[placeholder*='iniziare a digitare'], input[role='combobox']")
        except:
            dbg(f"autocomplete: elemento non trovato")
            return False

        if js(drv, JS_IS_HIDDEN, el):
            dbg(f"autocomplete: nascosto (display:none)")
            return False

        testo = valore.strip()
        dbg(f"autocomplete: digito '{testo}' con keyboard events")

        # Usa nativeInputValueSetter + KeyboardEvent per triggerare
        # il filtro di Angular Material Autocomplete
        js(drv, """
            var el = arguments[0], text = arguments[1];
            el.focus();
            el.click();
            var setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            setter.call(el, '');
            el.dispatchEvent(new Event('input', {bubbles:true}));
            setter.call(el, text);
            el.dispatchEvent(new Event('input', {bubbles:true}));
            el.dispatchEvent(new Event('change', {bubbles:true}));
            el.dispatchEvent(new KeyboardEvent('keydown', {bubbles:true, key:'a'}));
            el.dispatchEvent(new KeyboardEvent('keyup', {bubbles:true, key:'a'}));
            el.dispatchEvent(new Event('focusin', {bubbles:true}));
        """, el, testo)

        # Attendi dropdown nel CDK overlay
        best = None
        for attesa in range(10):
            time.sleep(1.5)
            opzioni = drv.find_elements(By.CSS_SELECTOR,
                ".cdk-overlay-container mat-option, "
                ".cdk-overlay-container .mat-mdc-option, "
                "mat-option.mat-mdc-option, "
                "[role='listbox'] [role='option']")
            dbg(f"autocomplete: tentativo {attesa+1}, {len(opzioni)} opzioni CDK")

            if opzioni:
                val_lower = valore.lower().strip()
                best = next((o for o in opzioni if o.text.strip().lower() == val_lower), None)
                if not best:
                    best = next((o for o in opzioni if val_lower in o.text.strip().lower()), None)
                if not best:
                    best = next((o for o in opzioni if o.text.strip().lower() in val_lower and len(o.text.strip()) > 10), None)
                if not best:
                    best = opzioni[0]
                break

        if best:
            dbg(f"autocomplete: seleziono '{best.text.strip()[:60]}'")
            clicca_js(drv, best)
            time.sleep(2)
            val_dopo = js(drv, "return arguments[0].value||'';", el)
            dbg(f"autocomplete: valore dopo = '{val_dopo[:60]}'")
        else:
            dbg(f"autocomplete: NESSUN dropdown, set diretto")
            js(drv, JS_SET_INPUT, el, valore)
            time.sleep(1)

        return True

    # --- CAMPI NORMALI ---
    try:
        el = drv.find_element(By.NAME, name)
    except:
        dbg(f"'{name}': non trovato")
        return False

    # Solo skip se il campo o un parent ha display:none (= sezione nascosta)
    if js(drv, JS_IS_HIDDEN, el):
        dbg(f"'{name}': nascosto (display:none), skip")
        return False

    try:
        if tipo == "select":
            # Retry: il select potrebbe non essere pronto subito (es. dopo autocomplete)
            for tentativo in range(3):
                ok = js(drv, JS_SET_SELECT, el, valore)
                if ok:
                    dbg(f"select '{name}'='{valore}' OK (tentativo {tentativo+1})")
                    return True
                dbg(f"select '{name}'='{valore}' fallito, retry...")
                time.sleep(1)
                # Ri-trova l'elemento (potrebbe essere stato ricreato da Angular)
                try: el = drv.find_element(By.NAME, name)
                except: break
            dbg(f"select '{name}'='{valore}' FALLITO dopo 3 tentativi")
            return False

        elif tipo == "checkbox":
            should = valore.lower() in ("true","1","si")
            is_on = js(drv, "return arguments[0].checked;", el)
            if is_on != should:
                js(drv, "arguments[0].click(); arguments[0].dispatchEvent(new Event('change',{bubbles:true}));", el)
            dbg(f"checkbox '{name}'={should}")
            return True

        elif tipo == "date":
            # Per i campi date Angular serve un approccio specifico:
            # 1. Focus + click per attivare il campo
            # 2. Set valore via nativeInputValueSetter
            # 3. Dispatch input + change per ngModel
            # 4. Blur per triggerare la validazione
            js(drv, """
                var el = arguments[0], val = arguments[1];
                // Focus e click
                el.focus();
                el.click();
                el.dispatchEvent(new Event('focus', {bubbles:true}));
                el.dispatchEvent(new Event('focusin', {bubbles:true}));

                // Set valore
                var setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value').set;
                setter.call(el, val);

                // Dispatch tutti gli eventi che Angular ascolta
                el.dispatchEvent(new Event('input', {bubbles:true}));
                el.dispatchEvent(new Event('change', {bubbles:true}));

                // Simula keydown/keyup (alcuni componenti li ascoltano)
                el.dispatchEvent(new KeyboardEvent('keydown', {bubbles:true}));
                el.dispatchEvent(new KeyboardEvent('keyup', {bubbles:true}));

                // Blur per triggerare validazione ngModel
                el.dispatchEvent(new Event('blur', {bubbles:true}));
                el.dispatchEvent(new Event('focusout', {bubbles:true}));
            """, el, valore)
            time.sleep(0.3)
            # Verifica
            actual = js(drv, "return arguments[0].value||'';", el)
            dbg(f"date '{name}'='{valore}' actual='{actual}'")
            return True

        elif tipo in ("text", "number"):
            js(drv, JS_SET_INPUT, el, valore)
            dbg(f"input '{name}'='{valore[:30]}'")
            return True

        elif tipo == "textarea":
            js(drv, JS_SET_TEXTAREA, el, valore)
            dbg(f"textarea '{name}'='{valore[:30]}'")
            return True

        else:
            js(drv, JS_SET_INPUT, el, valore)
            return True

    except Exception as e:
        dbg(f"'{name}' ERRORE: {e}")
        return False

# ============================================================================
# ATTENDI FORM PRONTO
# ============================================================================

def attendi_form(drv, cfg):
    """Attende che il form sia pronto controllando che i campi esistano e siano usabili."""
    # Cerca il primo campo data (dataInizio o dataPubblicazione) - presente in tutte le sezioni
    primo_campo = cfg["campi"][0][0].lstrip("_")
    dbg(f"Attendo form pronto (campo: {primo_campo})...")

    for tentativo in range(10):
        try:
            el = drv.find_element(By.NAME, primo_campo)
            if not js(drv, JS_IS_HIDDEN, el):
                dbg(f"Form pronto al tentativo {tentativo+1}")
                return True
        except:
            pass
        time.sleep(0.5)

    dbg("Form non pronto dopo 5 secondi")
    return False

# ============================================================================
# DIAGNOSTICA (con --debug)
# ============================================================================

def diagnostica_form(drv, cfg):
    """Mostra lo stato di tutti i campi nel form corrente."""
    print("    [DBG] === DIAGNOSTICA FORM ===")
    for nm, tp in cfg["campi"]:
        name = nm.lstrip("_")
        if tp == "autocomplete":
            try:
                el = drv.find_element(By.CSS_SELECTOR,
                    "input[placeholder*='iniziare a digitare'], input[role='combobox']")
                hidden = js(drv, JS_IS_HIDDEN, el)
                val = js(drv, "return arguments[0].value||'';", el)
                print(f"    [DBG]   autocomplete  hidden={hidden}  val='{val[:30]}'")
            except:
                print(f"    [DBG]   autocomplete  NON TROVATO")
            continue
        try:
            el = drv.find_element(By.NAME, name)
            hidden = js(drv, JS_IS_HIDDEN, el)
            val = js(drv, "return arguments[0].value||'';", el)
            tag = js(drv, "return arguments[0].tagName;", el)
            disabled = js(drv, "return arguments[0].disabled;", el)
            print(f"    [DBG]   {name:25s} <{tag}> hidden={hidden} disabled={disabled} val='{val[:30]}'")
        except:
            print(f"    [DBG]   {name:25s} NON TROVATO")
    print("    [DBG] === FINE DIAGNOSTICA ===")

# ============================================================================
# LETTURA VOCI
# ============================================================================

def leggi_voci(drv, sk):
    cfg = SEZIONI[sk]
    print(f"\n{'='*60}\n  LETTURA: {cfg['nome']}\n{'='*60}")
    time.sleep(PAUSA)
    ro = is_readonly(drv)
    if ro: print("  [i] Pagina sola lettura\n")
    url = drv.current_url
    comp = cfg["comp"]

    tabs = drv.find_elements(By.CSS_SELECTOR, f"{comp} table") or drv.find_elements(By.CSS_SELECTOR, "table")
    if not tabs: print("  Nessuna tabella!"); return []
    rows = tabs[0].find_elements(By.CSS_SELECTOR, "tr.ng-star-inserted")
    tot = len(rows)
    print(f"  Trovate {tot} voci\n")
    voci = []

    for i in range(tot):
        print(f"  [{i+1}/{tot}] ", end="", flush=True)
        time.sleep(PAUSA)
        tabs = drv.find_elements(By.CSS_SELECTOR, f"{comp} table") or drv.find_elements(By.CSS_SELECTOR, "table")
        if not tabs: drv.get(url); time.sleep(3); tabs = drv.find_elements(By.CSS_SELECTOR, f"{comp} table")
        rows = tabs[0].find_elements(By.CSS_SELECTOR, "tr.ng-star-inserted")
        if i >= len(rows): print("skip"); continue

        try:
            clicca_js(drv, rows[i].find_element(By.CSS_SELECTOR, "button"))
            time.sleep(PAUSA)
        except: print("errore click"); continue

        voce = {}
        for nm, tp in cfg["campi"]:
            voce[csv_key((nm,tp))] = leggi_campo(drv, nm.lstrip("_"), tp)
        voci.append(voce)
        desc = voce.get("descrizione1") or voce.get("titolo") or voce.get("datore") or voce.get("istituto") or "?"
        print(f"OK - {desc[:65]}")

        # Torna alla lista
        ok = False
        if not ro:
            try:
                a = WebDriverWait(drv,3).until(EC.element_to_be_clickable((By.XPATH,"//button[contains(text(),'Annulla')]")))
                clicca_js(drv,a); time.sleep(PAUSA); ok=True
            except: pass
        if not ok:
            try:
                tabs = drv.find_elements(By.CSS_SELECTOR, f"{comp} table")
                if tabs:
                    rs = tabs[0].find_elements(By.CSS_SELECTOR, "tr.ng-star-inserted")
                    if i<len(rs): clicca_js(drv, rs[i].find_element(By.CSS_SELECTOR,"button")); time.sleep(PAUSA); ok=True
            except: pass
        if not ok: drv.get(url); time.sleep(3)

    print(f"\n  Lette {len(voci)} voci")
    return voci

# ============================================================================
# INSERIMENTO VOCI
# ============================================================================

def inserisci_voci(drv, voci, sk):
    cfg = SEZIONI[sk]
    print(f"\n{'='*60}\n  INSERIMENTO: {cfg['nome']}\n{'='*60}")
    if is_readonly(drv):
        print("  ERRORE: Pagina sola lettura!"); return 0, len(voci)
    print(f"  Voci: {len(voci)}")

    # Avviso campi manuali per esperienze PA
    ha_date_manuali = (sk == "esperienze_pa")
    if ha_date_manuali:
        print("\n  NOTA: Le date (inizio/fine) delle esperienze PA")
        print("  non possono essere compilate automaticamente.")
        print("  Lo script compilera' tutto il resto e poi si fermera'")
        print("  per farti inserire le date a mano prima di salvare.\n")

    ok = ko = 0
    url = drv.current_url

    for i, voce in enumerate(voci):
        desc = voce.get("descrizione1") or voce.get("titolo") or voce.get("datore") or voce.get("istituto") or f"#{i+1}"
        print(f"\n  [{i+1}/{len(voci)}] {desc[:55]}")

        try:
            # 1. Clicca Inserisci
            bi = WebDriverWait(drv, TIMEOUT).until(
                EC.presence_of_element_located((By.XPATH, f"//button[contains(text(),'{cfg['btn']}')]")))
            clicca_js(drv, bi)
            time.sleep(PAUSA + 1)

            # 2. Attendi form
            if not attendi_form(drv, cfg):
                print("    FORM NON PRONTO")
                ko += 1
                _recover(drv, url)
                continue

            if DEBUG:
                diagnostica_form(drv, cfg)

            # 3. Compila campi (salta date per esperienze PA)
            saltati = []
            date_da_inserire = []
            for nm, tp in cfg["campi"]:
                key = csv_key((nm,tp))
                val = voce.get(key, "")

                # Per esperienze PA, le date le segna per inserimento manuale
                if ha_date_manuali and tp == "date":
                    if val:
                        # Converti da yyyy-mm-dd a dd/mm/yyyy per mostrare all'utente
                        try:
                            parti = val.split("-")
                            val_display = f"{parti[2]}/{parti[1]}/{parti[0]}"
                        except:
                            val_display = val
                        date_da_inserire.append((key, val_display))
                    continue

                if val:
                    if not scrivi_campo(drv, nm.lstrip("_"), tp, val):
                        saltati.append(key)
                    time.sleep(0.2)

            time.sleep(1)

            # 4. Se ci sono date da inserire manualmente, pausa
            if date_da_inserire:
                print("    Campi compilati automaticamente.")
                print("    >>> INSERISCI MANUALMENTE queste date:")
                for campo, val in date_da_inserire:
                    print(f"        {campo}: {val}")
                input("    >>> Premi INVIO quando hai finito e vuoi SALVARE...")

            # 5. Salva
            bs = WebDriverWait(drv, TIMEOUT).until(
                EC.presence_of_element_located((By.XPATH, "//button[contains(text(),'Salva')]")))
            clicca_js(drv, bs)
            time.sleep(PAUSA + 1)

            # 6. Verifica salvataggio
            salvato = False
            try:
                WebDriverWait(drv, 4).until(
                    EC.presence_of_element_located((By.XPATH, f"//button[contains(text(),'{cfg['btn']}')]")))
                salvato = True
            except:
                pass

            if salvato:
                ok += 1
                note = f" (saltati: {','.join(saltati)})" if saltati else ""
                print(f"    SALVATO{note}")
            else:
                # Salvataggio fallito - chiedi intervento manuale
                print("    SALVATAGGIO FALLITO - errore di validazione.")
                print("    >>> Controlla i campi evidenziati in rosso nel browser.")
                scelta = input("    >>> (r)iprova salvataggio / (s)alta questa voce: ").strip().lower()

                if scelta == "r":
                    # L'utente ha corretto a mano, riprova salvataggio
                    bs = drv.find_element(By.XPATH, "//button[contains(text(),'Salva')]")
                    clicca_js(drv, bs)
                    time.sleep(PAUSA + 1)
                    try:
                        WebDriverWait(drv, 4).until(
                            EC.presence_of_element_located((By.XPATH, f"//button[contains(text(),'{cfg['btn']}')]")))
                        ok += 1
                        print("    SALVATO dopo correzione manuale")
                    except:
                        print("    Ancora non salvato. Salta.")
                        ko += 1
                        _recover(drv, url)
                else:
                    ko += 1
                    _recover(drv, url)

        except Exception as e:
            print(f"    ERRORE ({str(e).split(chr(10))[0][:60]})")
            ko += 1
            _recover(drv, url)

    print(f"\n  RISULTATO: {ok} OK, {ko} errori su {len(voci)}")
    return ok, ko

def _recover(drv, url):
    try:
        a = drv.find_element(By.XPATH, "//button[contains(text(),'Annulla')]")
        clicca_js(drv, a); time.sleep(PAUSA)
    except: drv.get(url); time.sleep(3)

# ============================================================================
# CSV
# ============================================================================

def salva_csv(voci, sk):
    nomi = [csv_key(c) for c in SEZIONI[sk]["campi"]]
    fn = f"{sk}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(fn,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=nomi,extrasaction='ignore'); w.writeheader(); w.writerows(voci)
    print(f"  Salvato: {fn} ({len(voci)} voci)"); return fn

def carica_csv(fn):
    with open(fn,"r",encoding="utf-8") as f: voci=[dict(r) for r in csv.DictReader(f)]
    print(f"  Caricati {len(voci)} voci da {fn}"); return voci

def trova_csv(sez=None):
    return sorted([f for f in os.listdir(".") if f.endswith(".csv") and (not sez or f.startswith(sez))], reverse=True)

# ============================================================================
# MENU
# ============================================================================

def scegli_sez():
    kk=list(SEZIONI.keys())
    for i,k in enumerate(kk): print(f"  {i+1}. {SEZIONI[k]['nome']}")
    print(f"  {len(kk)+1}. TUTTE")
    try:
        idx=int(input(f"  > ").strip())-1
        return list(kk) if idx==len(kk) else [kk[idx]]
    except: return None

def main():
    print(f"\n{'='*60}\n  CONCORSI SMART v3.1\n{'='*60}")
    if DEBUG: print("  [DEBUG MODE]")
    while True:
        print(f"\n  1.LEGGI  2.INSERISCI  3.TUTTO  4.CSV  5.Anteprima  0.Esci")
        s=input("  > ").strip()
        if s=="0": break
        elif s=="1":
            sez=scegli_sez()
            if not sez: continue
            print("\n  Vai sulla SORGENTE"); input("  INVIO...")
            d=connetti()
            for sk in sez:
                if len(sez)>1: print(f"\n  -> {SEZIONI[sk]['nome']}"); input("  INVIO...")
                v=leggi_voci(d,sk)
                if v: salva_csv(v,sk)
        elif s=="2":
            sez=scegli_sez()
            if not sez: continue
            for sk in sez:
                ff=trova_csv(sk)
                if not ff: print(f"  Nessun CSV per {SEZIONI[sk]['nome']}"); continue
                for i,f in enumerate(ff[:5]): print(f"  {i+1}. {f}")
                try: fn=ff[int(input("  Quale? (INVIO=1): ").strip() or "1")-1]
                except: fn=ff[0]
                voci=carica_csv(fn)
                if not voci: continue
                print(f"  Naviga a DESTINAZIONE -> {SEZIONI[sk]['nome']}")
                if input("  Procedere? (s/n): ").strip().lower() in ("s","si","y"):
                    d=connetti(); inserisci_voci(d,voci,sk)
        elif s=="3":
            sez=scegli_sez()
            if not sez: continue
            print("\n  FASE 1: SORGENTE"); input("  INVIO...")
            d=connetti(); dati={}
            for sk in sez:
                if len(sez)>1: print(f"\n  -> {SEZIONI[sk]['nome']}"); input("  INVIO...")
                v=leggi_voci(d,sk)
                if v: salva_csv(v,sk); dati[sk]=v
            if not dati: continue
            print(f"\n  FASE 2: DESTINAZIONE"); input("  INVIO...")
            d=connetti()
            for sk,v in dati.items():
                if len(dati)>1: print(f"\n  -> {SEZIONI[sk]['nome']}"); input("  INVIO...")
                inserisci_voci(d,v,sk)
        elif s=="4":
            for f in trova_csv(): print(f"  {f}")
        elif s=="5":
            ff=trova_csv()
            if not ff: continue
            for i,f in enumerate(ff): print(f"  {i+1}. {f}")
            try: fn=ff[int(input("  > ").strip())-1]
            except: continue
            for i,v in enumerate(carica_csv(fn)):
                print(f"\n  --- {i+1} ---")
                for k,val in v.items():
                    if val: print(f"    {k:25s}: {val[:70]}")

if __name__=="__main__": main()
