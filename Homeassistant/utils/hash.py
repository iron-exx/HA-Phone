#!/usr/bin/env python3
"""RFID Hash Utility - SHA-256 Hashing für Datenschutz (D-14, D-19)"""
import hashlib
import logging

def hash_rfid(rfid_hex: str) -> str:
    """
    Erstellt einen SHA-256 Hash der RFID-Karte (nur Hex-String, nicht Klartext).
    
    Args:
        rfid_hex: RFID als Hex-String (z.B. "EFCD083E")
        
    Returns:
        SHA-256 Hash als Hex-String (64 Zeichen)
    """
    if not rfid_hex or not isinstance(rfid_hex, str):
        logging.warning("Ungültige RFID für Hash: %s", rfid_hex)
        return ""
    
    # RFID als Hex-String hashen (nicht als Klartext)
    rfid_bytes = rfid_hex.encode('utf-8')
    hash_obj = hashlib.sha256(rfid_bytes)
    return hash_obj.hexdigest()

def verify_rfid_hash(rfid_hex: str, stored_hash: str) -> bool:
    """
    Prüft ob RFID mit dem gespeicherten Hash übereinstimmt.
    
    Args:
        rfid_hex: RFID als Hex-String
        stored_hash: Gespeicherter SHA-256 Hash
        
    Returns:
        True wenn Hash übereinstimmt
    """
    if not stored_hash:
        return False
    computed_hash = hash_rfid(rfid_hex)
    return computed_hash == stored_hash
