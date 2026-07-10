import re
import socket
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from jinja2 import Environment
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import ProvisioningTemplate, ProvisionedDevice, Extension
from backend import ami

# Auth-protected CRUD router
router = APIRouter()
# PUBLIC router — devices fetch their config unauthenticated (secured by MAC).
public_router = APIRouter()


def _norm_mac(value: str) -> str:
    """Lowercase hex only (strip :, -, ., spaces)."""
    return re.sub(r"[^0-9a-fA-F]", "", value or "").lower()


def _parse_extension_numbers(value: str, allow_empty: bool = False) -> list[int]:
    if not value or not value.strip():
        if allow_empty:
            return []
        raise HTTPException(status_code=422, detail="extension_numbers must not be empty")
    try:
        numbers = [int(n.strip()) for n in value.split(",") if n.strip()]
    except ValueError:
        raise HTTPException(status_code=422, detail="extension_numbers must be comma-separated integers")
    if not numbers and not allow_empty:
        raise HTTPException(status_code=422, detail="extension_numbers must not be empty")
    if len(numbers) != len(set(numbers)):
        raise HTTPException(status_code=422, detail="extension_numbers must not contain duplicates")
    return numbers


def _validate_extension_numbers(value: str, session: Session, allow_empty: bool = False) -> str:
    """Parse + verify every number resolves to a real extension. Returns the
    normalized (deduped-order-preserved) comma-separated string to store."""
    numbers = _parse_extension_numbers(value, allow_empty=allow_empty)
    if not numbers:
        return ""
    existing = {e.number for e in session.exec(select(Extension)).all()}
    missing = [n for n in numbers if n not in existing]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown extension_numbers: {','.join(str(n) for n in missing)}",
        )
    return ",".join(str(n) for n in numbers)


def _lan_ip() -> str:
    """Best-effort primary LAN IPv4 of the host (the address phones register to)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return ""


def _gigaset_slots(accounts: list[dict], max_slots: int = 6) -> list[dict[str, str | int]]:
    """Return all fixed Gigaset DECT account slots, including empty ones.

    Field-name suffix scheme confirmed against Yeastar's official Gigaset
    N510 IP PRO ProviderFrame template: most per-account SYMB_ITEM IDs carry
    NO suffix for account 1 (e.g. 'aucS_SIP_ACCOUNT_NAME') and '_2'.."_6" for
    accounts 2-6 - EXCEPT 'ucB_SIP_ACCOUNT_IS_ACTIVE', which is always
    numbered '_1'.."_6", including for account 1. The original 0.7.77
    template used one uniform suffix for every field including the active
    flag, so 'ucB_SIP_ACCOUNT_IS_ACTIVE' (missing '_1') was never a field
    the base recognized - account 1 (and therefore every device using only
    one line) silently failed to activate."""
    slots: list[dict[str, str | int]] = []
    for idx in range(max_slots):
        account = accounts[idx] if idx < len(accounts) else None
        suffix = "" if idx == 0 else f"_{idx + 1}"
        active_suffix = f"_{idx + 1}"
        mask = f"0x{1 << idx:x}" if account else "0x0"
        slots.append(
            {
                "index0": idx,
                "suffix": suffix,
                "active_suffix": active_suffix,
                "account_name": account["number"] if account else "",
                "display_name": account["display_name"] if account else "",
                "sip_username": account["sip_username"] if account else "",
                "sip_auth": account["sip_auth"] if account else "",
                "sip_password": account["sip_password"] if account else "",
                "active_hex": "0x1" if account else "0x0",
                "state_hex": "0x1" if account else "0x0",
                "send_mask": mask,
                "receive_mask": mask,
            }
        )
    return slots


# ── Built-in starter templates (fully editable in the UI) ────────────────────
BUILTIN_TEMPLATES = [
    {
        "name": "Yealink T5x/T4x",
        "vendor": "Yealink",
        "file_pattern": "{mac}.cfg",
        "content": (
            "#!version:1.0.0.1\n"
            "## HA-Phone auto-provisioning — Yealink. Editierbar.\n"
            "account.1.enable = 1\n"
            "account.1.label = {{label}}\n"
            "account.1.display_name = {{display_name}}\n"
            "account.1.auth_name = {{sip_username}}\n"
            "account.1.user_name = {{sip_username}}\n"
            "account.1.password = {{sip_password}}\n"
            "account.1.sip_server.1.address = {{sip_server}}\n"
            "account.1.sip_server.1.port = {{sip_port}}\n"
            "account.1.sip_server.1.transport_type = 0\n"
        ),
    },
    {
        "name": "Grandstream",
        "vendor": "Grandstream",
        "file_pattern": "cfg{mac}.xml",
        "content": (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<!-- HA-Phone auto-provisioning — Grandstream P-values. Editierbar. -->\n"
            '<gs_provision version="1">\n'
            "  <config version=\"1\">\n"
            "    <P271>1</P271>\n"
            "    <P47>{{sip_server}}</P47>\n"
            "    <P35>{{sip_username}}</P35>\n"
            "    <P36>{{sip_username}}</P36>\n"
            "    <P34>{{sip_password}}</P34>\n"
            "    <P3>{{display_name}}</P3>\n"
            "  </config>\n"
            "</gs_provision>\n"
        ),
    },
    {
        "name": "Fanvil",
        "vendor": "Fanvil",
        "file_pattern": "{mac}.cfg",
        "content": (
            "<<VOIP CONFIG FILE>>Version:2.0000\n"
            "## HA-Phone auto-provisioning — Fanvil. Editierbar.\n"
            "<SIP CONFIG MODULE>\n"
            "SIP1 Phone Number :{{sip_username}}\n"
            "SIP1 Display Name :{{display_name}}\n"
            "SIP1 Register User :{{sip_username}}\n"
            "SIP1 Register Pswd :{{sip_password}}\n"
            "SIP1 Register Addr :{{sip_server}}\n"
            "SIP1 Register Port :{{sip_port}}\n"
            "SIP1 Register Enable :1\n"
        ),
    },
    {
        "name": "Gigaset N510/N610/N670/N870 IP PRO (DECT)",
        "vendor": "Gigaset",
        "file_pattern": "{mac}.xml",
        "content": (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<!-- HA-Phone auto-provisioning — Gigaset DECT provider profiles.\n"
            "     STARTVORLAGE: exakte Parameternamen je nach Firmware anpassen!\n"
            "     Eine SipProvider-Zeile pro zugeordneter Nebenstelle (Geraet ->\n"
            "     mehrere Nebenstellen zuweisen, siehe Provisioning-Seite).\n"
            "     WICHTIG: welches Mobilteil (IPUI) welche Zeile nutzt, wird nicht\n"
            "     hierueber uebertragen - das bleibt manuell in der Gigaset-Basis\n"
            "     unter Einstellungen -> Mobilteile -> [Mobilteil bearbeiten] -> SIP\n"
            "     zuzuordnen (dort auf 'HA-Phone <Nummer>' setzen). Ohne diesen\n"
            "     Schritt hat das Mobilteil keine Amtsleitung und jeder Anruf\n"
            "     erzeugt sofort ein Besetztzeichen, ohne dass ein SIP-Paket rausgeht.\n"
            "     Gigaset-Datenserver-URL am Gerät: http://<PBX-IP>/api/autoprovision/[MAC].xml -->\n"
            '<provisioning version="1.1" productID="e2">\n'
            "  <nvm>\n"
            "{% for account in accounts %}"
            '    <param name="SipProvider.{{ loop.index0 }}.Name" value="HA-Phone {{ account.number }}"/>\n'
            '    <param name="SipProvider.{{ loop.index0 }}.Domain" value="{{ sip_server }}"/>\n'
            '    <param name="SipProvider.{{ loop.index0 }}.RegServer" value="{{ sip_server }}"/>\n'
            '    <param name="SipProvider.{{ loop.index0 }}.RegServerPort" value="{{ sip_port }}"/>\n'
            '    <param name="SipProvider.{{ loop.index0 }}.ProxyServer" value="{{ sip_server }}"/>\n'
            '    <param name="SipProvider.{{ loop.index0 }}.ProxyServerPort" value="{{ sip_port }}"/>\n'
            '    <param name="Handset.{{ loop.index0 }}.SIP.UserName" value="{{ account.sip_username }}"/>\n'
            '    <param name="Handset.{{ loop.index0 }}.SIP.AuthName" value="{{ account.sip_auth }}"/>\n'
            '    <param name="Handset.{{ loop.index0 }}.SIP.AuthPassword" value="{{ account.sip_password }}"/>\n'
            '    <param name="Handset.{{ loop.index0 }}.SIP.DisplayName" value="{{ account.display_name }}"/>\n'
            "{% endfor %}"
            "  </nvm>\n"
            "</provisioning>\n"
        ),
    },
    {
        "name": "Gigaset N510 IP PRO (Yeastar ProviderFrame)",
        "vendor": "Gigaset",
        "file_pattern": "{mac}.xml",
        "content": (
            '<?xml version="1.0" encoding="ISO-8859-1"?>\n'
            '<ProviderFrame xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xsi:noNamespaceSchemaLocation="profile.xsd">\n'
            "  <Provider>\n"
            "    <!-- HA-Phone auto-provisioning - Gigaset N510 IP PRO.\n"
            "         Field names verified against Yeastar's official Gigaset N510\n"
            "         IP PRO ProviderFrame template (a real PBX vendor's reference,\n"
            "         not a guess). Data server URL on the base:\n"
            "         http://<PBX-IP>/api/autoprovision/[MAC].xml\n"
            "         One SIP account per assigned extension, max. 6. Unused slots\n"
            "         are explicitly cleared so old assignments do not linger. -->\n"
            '    <PROFILE_NAME class="string" value="HA-Phone"/>\n'
            '    <PROFILE_VERSION class="string" value=""/>\n'
            '    <REBOOT value="true"/>\n'
            '    <SYMB_ITEM ID="BS_IP_Data1.ucB_ACCEPT_FOREIGN_SUBNET" class="symb_item" value="0x1"/>\n'
            '    <SYMB_ITEM ID="BS_IP_Data.ucB_AUTO_UPDATE_PROFILE" class="symb_item" value="0x1"/>\n'
            '    <SYMB_ITEM ID="BS_IP_Data3.ucI_ONESHOT_PROVISIONING_MODE_1" class="symb_item" value="0x1"/>\n'
            '    <SYMB_ITEM ID="BS_IP_Data1.ucI_SIP_PROVIDER_ID" class="symb_item" value="0"/>\n'
            "{% for slot in gigaset_slots %}"
            '    <SYMB_ITEM ID="BS_Accounts.astAccounts[{{ slot.index0 }}].aucAccountName[0]" class="symb_item" value=\'"{{ slot.account_name }}"\'/>\n'
            '    <SYMB_ITEM ID="BS_IP_Data1.aucS_SIP_ACCOUNT_NAME{{ slot.suffix }}" class="symb_item" value=\'"{{ slot.account_name }}"\'/>\n'
            '    <SYMB_ITEM ID="BS_IP_Data1.aucS_SIP_DISPLAYNAME{{ slot.suffix }}" class="symb_item" value=\'"{{ slot.display_name }}"\'/>\n'
            '    <SYMB_ITEM ID="BS_IP_Data3.aucS_SIP_LOGIN_ID{{ slot.suffix }}" class="symb_item" value=\'"{{ slot.sip_auth }}"\'/>\n'
            '    <SYMB_ITEM ID="BS_IP_Data1.aucS_SIP_PASSWORD{{ slot.suffix }}" class="symb_item" value=\'"{{ slot.sip_password }}"\'/>\n'
            '    <SYMB_ITEM ID="BS_IP_Data1.aucS_SIP_USER_ID{{ slot.suffix }}" class="symb_item" value=\'"{{ slot.sip_username }}"\'/>\n'
            '    <SYMB_ITEM ID="BS_IP_Data1.aucS_SIP_DOMAIN{{ slot.suffix }}" class="symb_item" value=\'"{{ sip_server }}"\'/>\n'
            '    <SYMB_ITEM ID="BS_IP_Data1.aucS_SIP_SERVER{{ slot.suffix }}" class="symb_item" value=\'"{{ sip_server }}"\'/>\n'
            '    <SYMB_ITEM ID="BS_IP_Data1.aucS_SIP_REGISTRAR{{ slot.suffix }}" class="symb_item" value=\'"{{ sip_server }}"\'/>\n'
            '    <SYMB_ITEM ID="BS_IP_Data1.aucS_SIP_PROVIDER_NAME{{ slot.suffix }}" class="symb_item" value=\'"PBX"\'/>\n'
            '    <SYMB_ITEM ID="BS_IP_Data1.uiI_SIP_SERVER_PORT{{ slot.suffix }}" class="symb_item" value="{{ gigaset_sip_port_hex }}"/>\n'
            '    <SYMB_ITEM ID="BS_IP_Data1.uiI_SIP_REGISTRAR_PORT{{ slot.suffix }}" class="symb_item" value="{{ gigaset_sip_port_hex }}"/>\n'
            '    <SYMB_ITEM ID="BS_IP_Data1.ucB_SIP_USE_STUN{{ slot.suffix }}" class="symb_item" value="0x0"/>\n'
            '    <SYMB_ITEM ID="BS_IP_Data1.ucI_OUTBOUND_PROXY_MODE{{ slot.suffix }}" class="symb_item" value="0x0"/>\n'
            '    <SYMB_ITEM ID="BS_IP_Data1.ucI_SIP_PREFERRED_VOCODER{{ slot.suffix }}" class="symb_item" value="0x05,0x01,0x00,0x02,0x03"/>\n'
            '    <SYMB_ITEM ID="BS_IP_Data1.ucB_SIP_ACCOUNT_IS_ACTIVE{{ slot.active_suffix }}" class="symb_item" value="{{ slot.active_hex }}"/>\n'
            '    <SYMB_ITEM ID="BS_Accounts.astAccounts[{{ slot.index0 }}].uiSendMask" class="symb_item" value="{{ slot.send_mask }}"/>\n'
            '    <SYMB_ITEM ID="BS_Accounts.astAccounts[{{ slot.index0 }}].uiReceiveMask" class="symb_item" value="{{ slot.receive_mask }}"/>\n'
            '    <SYMB_ITEM ID="BS_Accounts.astAccounts[{{ slot.index0 }}].ucState" class="symb_item" value="{{ slot.state_hex }}"/>\n'
            '    <SYMB_ITEM ID="BS_AE_Subscriber.stMtDat[{{ slot.index0 }}].aucTlnName[0]" class="symb_item" value=\'"{{ slot.account_name }}"\'/>\n'
            "{% endfor %}"
            '    <SYMB_ITEM ID="BS_LM_AppCfg.bit.bHasIdleTextInternalName" class="symb_item" value="1"/>\n'
            "    <!-- HA-Phone Telefonbuch als LDAP-Netzverzeichnis (Handset:\n"
            "         Telefonbuch-Taste lang druecken bzw. Menue -> Netzverzeichnis).\n"
            "         Feldnamen wie im Yeastar-Referenz-Template; 0xa aktiviert LDAP\n"
            "         auf Netdir-Slot 0, 0x185 = Port 389, Auth anonym. -->\n"
            '    <SYMB_ITEM ID="BS_XML_Netdirs.aucActivatedNetdirs[0]" class="symb_item" value="0xa"/>\n'
            '    <SYMB_ITEM ID="BS_LDAP_Netdirs.astNetdirProvider[0].aucDirName[0]" class="symb_item" value=\'"HA-Phone Telefonbuch"\'/>\n'
            '    <SYMB_ITEM ID="BS_LDAP_Netdirs.astNetdirProvider[0].aucServerURL[0]" class="symb_item" value=\'"{{ sip_server }}"\'/>\n'
            '    <SYMB_ITEM ID="BS_LDAP_Netdirs.astNetdirProvider[0].uiServerPort[0]" class="symb_item" value="0x185"/>\n'
            '    <SYMB_ITEM ID="BS_LDAP_Netdirs.astNetdirProvider[0].ucAuthType" class="symb_item" value="0"/>\n'
            '    <SYMB_ITEM ID="BS_LDAP_Netdirs.astNetdirProvider[0].aucBaseDN[0]" class="symb_item" value=\'"dc=phonebook"\'/>\n'
            '    <SYMB_ITEM ID="BS_LDAP_Netdirs.astNetdirProvider[0].NameFilter[0]" class="symb_item" value=\'"(|(cn=%)(sn=%)(givenName=%))"\'/>\n'
            '    <SYMB_ITEM ID="BS_LDAP_Netdirs.astNetdirProvider[0].NumberFilter[0]" class="symb_item" value=\'"(telephoneNumber=%)"\'/>\n'
            '    <SYMB_ITEM ID="BS_LDAP_Netdirs.astNetdirProvider[0].uiMaxNrOfSearchEntries" class="symb_item" value="0x32"/>\n'
            '    <SYMB_ITEM ID="BS_LDAP_Netdirs.astNetdirProvider[0].astNetDirDirectoryItems[0].aucItemAttribute[0]" class="symb_item" value=\'"givenName"\'/>\n'
            '    <SYMB_ITEM ID="BS_LDAP_Netdirs.astNetdirProvider[0].astNetDirDirectoryItems[1].aucItemAttribute[0]" class="symb_item" value=\'"sn"\'/>\n'
            '    <SYMB_ITEM ID="BS_LDAP_Netdirs.astNetdirProvider[0].astNetDirDirectoryItems[3].aucItemAttribute[0]" class="symb_item" value=\'"telephoneNumber"\'/>\n'
            "  </Provider>\n"
            "</ProviderFrame>\n"
        ),
    },
]

# The exact (broken) content shipped in 0.7.77-0.7.80: every per-account
# SYMB_ITEM ID used one uniform suffix, but the real device firmware (per
# Yeastar's official reference template) numbers 'ucB_SIP_ACCOUNT_IS_ACTIVE'
# starting at '_1' even for account 1, while every other account-1 field has
# NO suffix. That mismatch meant account 1 (and so every single-line device)
# never activated. Used below to repair already-seeded installs without
# touching a template a user has since edited themselves.
_N510_PROVIDERFRAME_NAME = "Gigaset N510 IP PRO (Yeastar ProviderFrame)"
_N510_PROVIDERFRAME_BROKEN_CONTENT = (
    '<?xml version="1.0" encoding="ISO-8859-1"?>\n'
    '<ProviderFrame xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    'xsi:noNamespaceSchemaLocation="profile.xsd">\n'
    "  <Provider>\n"
    "    <!-- HA-Phone auto-provisioning - Gigaset N510 IP PRO.\n"
    "         Yeastar-style ProviderFrame adapted to HA-Phone's multi-line\n"
    "         provisioning. Data server URL on the base:\n"
    "         http://<PBX-IP>/api/autoprovision/[MAC].xml\n"
    "         One SIP account per assigned extension, max. 6. Unused slots\n"
    "         are explicitly cleared so old assignments do not linger. -->\n"
    '    <PROFILE_NAME class="string" value="HA-Phone"/>\n'
    '    <PROFILE_VERSION class="string" value="1"/>\n'
    '    <REBOOT value="true"/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.ucB_ACCEPT_FOREIGN_SUBNET" class="symb_item" value="0x1"/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data.ucB_AUTO_UPDATE_PROFILE" class="symb_item" value="0x1"/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data3.ucI_ONESHOT_PROVISIONING_MODE_1" class="symb_item" value="0x1"/>\n'
    "{% for slot in gigaset_slots %}"
    '    <SYMB_ITEM ID="BS_Accounts.astAccounts[{{ slot.index0 }}].aucAccountName[0]" class="symb_item" value=\'"{{ slot.account_name }}"\'/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.aucS_SIP_ACCOUNT_NAME{{ slot.suffix }}" class="symb_item" value=\'"{{ slot.account_name }}"\'/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.aucS_SIP_DISPLAYNAME{{ slot.suffix }}" class="symb_item" value=\'"{{ slot.display_name }}"\'/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data3.aucS_SIP_LOGIN_ID{{ slot.suffix }}" class="symb_item" value=\'"{{ slot.sip_auth }}"\'/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.aucS_SIP_PASSWORD{{ slot.suffix }}" class="symb_item" value=\'"{{ slot.sip_password }}"\'/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.aucS_SIP_USER_ID{{ slot.suffix }}" class="symb_item" value=\'"{{ slot.sip_username }}"\'/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.aucS_SIP_DOMAIN{{ slot.suffix }}" class="symb_item" value=\'"{{ sip_server }}"\'/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.aucS_SIP_SERVER{{ slot.suffix }}" class="symb_item" value=\'"{{ sip_server }}"\'/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.aucS_SIP_REGISTRAR{{ slot.suffix }}" class="symb_item" value=\'"{{ sip_server }}"\'/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.aucS_SIP_PROVIDER_NAME{{ slot.suffix }}" class="symb_item" value=\'"HA-Phone"\'/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.uiI_SIP_SERVER_PORT{{ slot.suffix }}" class="symb_item" value="{{ gigaset_sip_port_hex }}"/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.uiI_SIP_REGISTRAR_PORT{{ slot.suffix }}" class="symb_item" value="{{ gigaset_sip_port_hex }}"/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.ucB_SIP_USE_STUN{{ slot.suffix }}" class="symb_item" value="0x0"/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.ucI_OUTBOUND_PROXY_MODE{{ slot.suffix }}" class="symb_item" value="0x0"/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.ucI_SIP_PREFERRED_VOCODER{{ slot.suffix }}" class="symb_item" value="0x05,0x01,0x00,0x02,0x03"/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.ucB_SIP_ACCOUNT_IS_ACTIVE{{ slot.suffix }}" class="symb_item" value="{{ slot.active_hex }}"/>\n'
    '    <SYMB_ITEM ID="BS_Accounts.astAccounts[{{ slot.index0 }}].uiSendMask" class="symb_item" value="{{ slot.send_mask }}"/>\n'
    '    <SYMB_ITEM ID="BS_Accounts.astAccounts[{{ slot.index0 }}].uiReceiveMask" class="symb_item" value="{{ slot.receive_mask }}"/>\n'
    '    <SYMB_ITEM ID="BS_Accounts.astAccounts[{{ slot.index0 }}].ucState" class="symb_item" value="{{ slot.state_hex }}"/>\n'
    '    <SYMB_ITEM ID="BS_AE_Subscriber.stMtDat[{{ slot.index0 }}].aucTlnName[0]" class="symb_item" value=\'"{{ slot.account_name }}"\'/>\n'
    "{% endfor %}"
    '    <SYMB_ITEM ID="BS_LM_AppCfg.bit.bHasIdleTextInternalName" class="symb_item" value="1"/>\n'
    "  </Provider>\n"
    "</ProviderFrame>\n"
)


# The 0.7.81-0.7.85 content: correct suffix scheme, but no LDAP phonebook
# section yet. Recognized so already-seeded installs pick up the LDAP block.
_N510_PROVIDERFRAME_PRE_LDAP_CONTENT = (
    '<?xml version="1.0" encoding="ISO-8859-1"?>\n'
    '<ProviderFrame xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    'xsi:noNamespaceSchemaLocation="profile.xsd">\n'
    "  <Provider>\n"
    "    <!-- HA-Phone auto-provisioning - Gigaset N510 IP PRO.\n"
    "         Field names verified against Yeastar's official Gigaset N510\n"
    "         IP PRO ProviderFrame template (a real PBX vendor's reference,\n"
    "         not a guess). Data server URL on the base:\n"
    "         http://<PBX-IP>/api/autoprovision/[MAC].xml\n"
    "         One SIP account per assigned extension, max. 6. Unused slots\n"
    "         are explicitly cleared so old assignments do not linger. -->\n"
    '    <PROFILE_NAME class="string" value="HA-Phone"/>\n'
    '    <PROFILE_VERSION class="string" value=""/>\n'
    '    <REBOOT value="true"/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.ucB_ACCEPT_FOREIGN_SUBNET" class="symb_item" value="0x1"/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data.ucB_AUTO_UPDATE_PROFILE" class="symb_item" value="0x1"/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data3.ucI_ONESHOT_PROVISIONING_MODE_1" class="symb_item" value="0x1"/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.ucI_SIP_PROVIDER_ID" class="symb_item" value="0"/>\n'
    "{% for slot in gigaset_slots %}"
    '    <SYMB_ITEM ID="BS_Accounts.astAccounts[{{ slot.index0 }}].aucAccountName[0]" class="symb_item" value=\'"{{ slot.account_name }}"\'/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.aucS_SIP_ACCOUNT_NAME{{ slot.suffix }}" class="symb_item" value=\'"{{ slot.account_name }}"\'/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.aucS_SIP_DISPLAYNAME{{ slot.suffix }}" class="symb_item" value=\'"{{ slot.display_name }}"\'/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data3.aucS_SIP_LOGIN_ID{{ slot.suffix }}" class="symb_item" value=\'"{{ slot.sip_auth }}"\'/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.aucS_SIP_PASSWORD{{ slot.suffix }}" class="symb_item" value=\'"{{ slot.sip_password }}"\'/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.aucS_SIP_USER_ID{{ slot.suffix }}" class="symb_item" value=\'"{{ slot.sip_username }}"\'/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.aucS_SIP_DOMAIN{{ slot.suffix }}" class="symb_item" value=\'"{{ sip_server }}"\'/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.aucS_SIP_SERVER{{ slot.suffix }}" class="symb_item" value=\'"{{ sip_server }}"\'/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.aucS_SIP_REGISTRAR{{ slot.suffix }}" class="symb_item" value=\'"{{ sip_server }}"\'/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.aucS_SIP_PROVIDER_NAME{{ slot.suffix }}" class="symb_item" value=\'"PBX"\'/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.uiI_SIP_SERVER_PORT{{ slot.suffix }}" class="symb_item" value="{{ gigaset_sip_port_hex }}"/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.uiI_SIP_REGISTRAR_PORT{{ slot.suffix }}" class="symb_item" value="{{ gigaset_sip_port_hex }}"/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.ucB_SIP_USE_STUN{{ slot.suffix }}" class="symb_item" value="0x0"/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.ucI_OUTBOUND_PROXY_MODE{{ slot.suffix }}" class="symb_item" value="0x0"/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.ucI_SIP_PREFERRED_VOCODER{{ slot.suffix }}" class="symb_item" value="0x05,0x01,0x00,0x02,0x03"/>\n'
    '    <SYMB_ITEM ID="BS_IP_Data1.ucB_SIP_ACCOUNT_IS_ACTIVE{{ slot.active_suffix }}" class="symb_item" value="{{ slot.active_hex }}"/>\n'
    '    <SYMB_ITEM ID="BS_Accounts.astAccounts[{{ slot.index0 }}].uiSendMask" class="symb_item" value="{{ slot.send_mask }}"/>\n'
    '    <SYMB_ITEM ID="BS_Accounts.astAccounts[{{ slot.index0 }}].uiReceiveMask" class="symb_item" value="{{ slot.receive_mask }}"/>\n'
    '    <SYMB_ITEM ID="BS_Accounts.astAccounts[{{ slot.index0 }}].ucState" class="symb_item" value="{{ slot.state_hex }}"/>\n'
    '    <SYMB_ITEM ID="BS_AE_Subscriber.stMtDat[{{ slot.index0 }}].aucTlnName[0]" class="symb_item" value=\'"{{ slot.account_name }}"\'/>\n'
    "{% endfor %}"
    '    <SYMB_ITEM ID="BS_LM_AppCfg.bit.bHasIdleTextInternalName" class="symb_item" value="1"/>\n'
    "  </Provider>\n"
    "</ProviderFrame>\n"
)

# Every superseded shipped revision of a builtin template, by name. A row is
# auto-upgraded to the current BUILTIN_TEMPLATES content ONLY if it still
# exactly matches one of these - user-edited templates are never touched.
_OUTDATED_BUILTIN_CONTENTS: dict[str, list[str]] = {
    _N510_PROVIDERFRAME_NAME: [
        _N510_PROVIDERFRAME_BROKEN_CONTENT,
        _N510_PROVIDERFRAME_PRE_LDAP_CONTENT,
    ],
}


def repair_broken_builtin_templates(session: Session) -> bool:
    """Upgrade builtin template rows whose content exactly matches a known
    superseded revision (e.g. the broken 0.7.77 N510 suffix scheme, or the
    pre-LDAP 0.7.81 revision). A user's own edits to a builtin template
    (explicitly supported - see BUILTIN_TEMPLATES comment) never match one
    of the known old texts verbatim and are left alone."""
    changed = False
    for name, old_contents in _OUTDATED_BUILTIN_CONTENTS.items():
        tpl = session.exec(
            select(ProvisioningTemplate).where(
                ProvisioningTemplate.name == name,
                ProvisioningTemplate.builtin == True,  # noqa: E712
            )
        ).first()
        if tpl and tpl.content in old_contents:
            fixed = next(t for t in BUILTIN_TEMPLATES if t["name"] == name)
            tpl.content = fixed["content"]
            session.add(tpl)
            changed = True
    if changed:
        session.commit()
    return changed


def seed_builtin_templates(session: Session) -> bool:
    """Insert starter templates once (by name). Returns True if it seeded."""
    seeded = False
    existing = {t.name for t in session.exec(select(ProvisioningTemplate)).all()}
    for t in BUILTIN_TEMPLATES:
        if t["name"] not in existing:
            session.add(ProvisioningTemplate(builtin=True, **t))
            seeded = True
    if seeded:
        session.commit()
    return seeded


_jinja_env = Environment(autoescape=False)


def _render(content: str, subs: dict) -> str:
    """Render a user-editable provisioning template. Was a flat {{key}} string
    replace; now real Jinja2 so multi-line devices can loop over `accounts`
    (see serve_provisioning) while every existing single-account template
    keeps working unchanged - they only ever used plain {{ var }} substitution,
    which Jinja2 handles identically."""
    return _jinja_env.from_string(content).render(**subs)


# ── Templates CRUD ───────────────────────────────────────────────────────────
@router.get("/provisioning/templates", response_model=List[ProvisioningTemplate])
def list_templates(session: Session = Depends(get_session)):
    return session.exec(select(ProvisioningTemplate)).all()


@router.post("/provisioning/templates", response_model=ProvisioningTemplate)
def create_template(tpl: ProvisioningTemplate, session: Session = Depends(get_session)):
    tpl.id = None
    tpl.builtin = False
    session.add(tpl)
    session.commit()
    session.refresh(tpl)
    return tpl


@router.patch("/provisioning/templates/{tpl_id}", response_model=ProvisioningTemplate)
def update_template(tpl_id: int, data: ProvisioningTemplate, session: Session = Depends(get_session)):
    existing = session.get(ProvisioningTemplate, tpl_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Template not found")
    for field in ("name", "vendor", "file_pattern", "content"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(existing, field, val)
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing


@router.delete("/provisioning/templates/{tpl_id}")
def delete_template(tpl_id: int, session: Session = Depends(get_session)):
    existing = session.get(ProvisioningTemplate, tpl_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Template not found")
    session.delete(existing)
    session.commit()
    return {"ok": True}


# ── Devices CRUD ─────────────────────────────────────────────────────────────
class DeviceOut(BaseModel):
    id: Optional[int]
    name: str
    manufacturer: str
    model: str
    mac: str
    extension_numbers: List[int]
    template_id: int
    provisioning_url: str


class DeviceCreate(BaseModel):
    name: str = ""
    manufacturer: str = ""
    model: str = ""
    mac: str
    extension_numbers: str
    template_id: int


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    mac: Optional[str] = None
    extension_numbers: Optional[str] = None
    template_id: Optional[int] = None


def _ensure_template_exists(template_id: int, session: Session) -> None:
    if template_id <= 0 or not session.get(ProvisioningTemplate, template_id):
        raise HTTPException(status_code=422, detail="Unknown template_id")


def _device_out(d: ProvisionedDevice, session: Session, lan_ip: str) -> DeviceOut:
    tpl = session.get(ProvisioningTemplate, d.template_id)
    fname = (tpl.file_pattern if tpl else "{mac}").replace("{mac}", d.mac)
    base = f"http://{lan_ip}" if lan_ip else "http://<PBX-IP>"
    return DeviceOut(
        id=d.id, name=d.name, manufacturer=d.manufacturer, model=d.model, mac=d.mac,
        extension_numbers=_parse_extension_numbers(d.extension_numbers, allow_empty=True), template_id=d.template_id,
        provisioning_url=f"{base}/api/autoprovision/{fname}",
    )


@router.get("/provisioning/devices", response_model=List[DeviceOut])
def list_devices(session: Session = Depends(get_session)):
    lan = _lan_ip()
    return [_device_out(d, session, lan) for d in session.exec(select(ProvisionedDevice)).all()]


@router.post("/provisioning/devices", response_model=DeviceOut)
def create_device(data: DeviceCreate, session: Session = Depends(get_session)):
    mac = _norm_mac(data.mac)
    if len(mac) != 12:
        raise HTTPException(status_code=400, detail="MAC muss 12 Hex-Zeichen haben.")
    _ensure_template_exists(data.template_id, session)
    extension_numbers = _validate_extension_numbers(data.extension_numbers, session)
    device = ProvisionedDevice(
        name=data.name,
        manufacturer=data.manufacturer,
        model=data.model,
        mac=mac,
        extension_numbers=extension_numbers,
        template_id=data.template_id,
    )
    session.add(device)
    session.commit()
    session.refresh(device)
    return _device_out(device, session, _lan_ip())


@router.patch("/provisioning/devices/{device_id}", response_model=DeviceOut)
def update_device(device_id: int, data: DeviceUpdate, session: Session = Depends(get_session)):
    existing = session.get(ProvisionedDevice, device_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Device not found")
    payload = data.model_dump(exclude_unset=True)
    for field in ("name", "manufacturer", "model"):
        if field in payload:
            setattr(existing, field, payload[field])
    if "template_id" in payload:
        _ensure_template_exists(payload["template_id"], session)
        existing.template_id = payload["template_id"]
    if "extension_numbers" in payload:
        existing.extension_numbers = _validate_extension_numbers(payload["extension_numbers"], session)
    if "mac" in payload:
        existing.mac = _norm_mac(payload["mac"])
        if len(existing.mac) != 12:
            raise HTTPException(status_code=400, detail="MAC muss 12 Hex-Zeichen haben.")
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return _device_out(existing, session, _lan_ip())


@router.delete("/provisioning/devices/{device_id}")
async def delete_device(device_id: int, session: Session = Depends(get_session)):
    existing = session.get(ProvisionedDevice, device_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Device not found")
    # Asterisk exposes no AMI action to force-expire an already-registered,
    # otherwise-idle SIP contact (the registration itself lingers until it
    # naturally expires or the device reconnects) - hanging up any call in
    # progress right now is the one immediate, reliable disconnect action
    # actually available, so that's what deleting a device does.
    numbers = _parse_extension_numbers(existing.extension_numbers, allow_empty=True)
    hung_up_calls = 0
    for number in numbers:
        hung_up_calls += await ami.hangup_channels_for_extension(str(number))
    session.delete(existing)
    session.commit()
    return {"ok": True, "hung_up_calls": hung_up_calls}


# ── PUBLIC provisioning endpoint (no auth — devices fetch by MAC) ─────────────
@public_router.get("/autoprovision/{path:path}")
def serve_provisioning(path: str, session: Session = Depends(get_session)):
    mac_match = re.search(r"([0-9a-fA-F]{12})", path)
    if not mac_match:
        raise HTTPException(status_code=404, detail="No MAC in request")
    mac = mac_match.group(1).lower()
    device = session.exec(select(ProvisionedDevice).where(ProvisionedDevice.mac == mac)).first()
    if not device:
        raise HTTPException(status_code=404, detail="Unknown device")
    tpl = session.get(ProvisioningTemplate, device.template_id)
    numbers = _parse_extension_numbers(device.extension_numbers, allow_empty=True)
    extensions = [
        e for number in numbers
        for e in session.exec(select(Extension).where(Extension.number == number)).all()
    ]
    if not tpl or not extensions:
        raise HTTPException(status_code=404, detail="Device not fully configured")
    accounts = [
        {
            "number": str(e.number),
            "display_name": e.display_name,
            "sip_username": str(e.number),
            "sip_auth": str(e.number),
            "sip_password": e.sip_password,
            "label": e.display_name,
        }
        for e in extensions
    ]
    first = accounts[0]
    sip_server = _lan_ip()
    sip_port = "5060"
    subs = {
        "mac": device.mac,
        "sip_server": sip_server,
        "sip_port": sip_port,
        # Multi-line devices (e.g. a DECT base with several handsets) loop
        # over `accounts` in their template to get one SIP account per
        # extension. Every pre-multi-line template only used the flat vars
        # below (mapped to the first/only assigned extension), so they keep
        # rendering exactly as before without any template changes.
        "accounts": accounts,
        "extension": first["number"],
        "display_name": first["display_name"],
        "label": first["label"],
        "sip_username": first["sip_username"],
        "sip_auth": first["sip_auth"],
        "sip_password": first["sip_password"],
        "gigaset_slots": _gigaset_slots(accounts),
        "gigaset_sip_port_hex": hex(int(sip_port)),
    }
    body = _render(tpl.content, subs)
    media = "application/xml" if path.lower().endswith(".xml") else "text/plain"
    return Response(content=body, media_type=media)
