"""Protezione legata all'account Windows corrente; nessuna chiave nel repository."""
import ctypes
import os
from ctypes import wintypes

class _Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_char))]

def _convert(payload, encrypt):
    if os.name != "nt":
        raise RuntimeError("Il salvataggio credenziali richiede Windows DPAPI")
    buffer = ctypes.create_string_buffer(payload)
    source = _Blob(len(payload), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    target = _Blob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    function = crypt32.CryptProtectData if encrypt else crypt32.CryptUnprotectData
    function.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel32.LocalFree(ctypes.cast(target.data, ctypes.c_void_p))

def protect(payload):
    return _convert(payload, True)

def unprotect(payload):
    return _convert(payload, False)
