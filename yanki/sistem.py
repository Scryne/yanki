"""Windows durum sorguları (gündüz boşta üretim için): kullanıcı ne kadardır boşta, bilgisayar prizde mi."""

import ctypes
from ctypes import wintypes


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


class _SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte), ("BatteryLifePercent", ctypes.c_byte),
                ("SystemStatusFlag", ctypes.c_byte), ("BatteryLifeTime", wintypes.DWORD),
                ("BatteryFullLifeTime", wintypes.DWORD)]


def bosta_sn() -> float:
    """Son klavye/fare girdisinden bu yana geçen süre (oturumun; zamanlanmış görev aynı oturumda çalışır)."""
    bilgi = _LASTINPUTINFO(ctypes.sizeof(_LASTINPUTINFO), 0)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(bilgi)):
        return 0.0
    # GetTickCount 49,7 günde bir başa sarar; fark 32 bit içinde alınır
    return ((ctypes.windll.kernel32.GetTickCount() - bilgi.dwTime) & 0xFFFFFFFF) / 1000


def prizde_mi() -> bool:
    """Pil varsa ve prizde değilse False (üretim pili ~30 dk'da tüketir). Bilinmiyorsa True (masaüstü)."""
    durum = _SYSTEM_POWER_STATUS()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(durum)):
        return True
    return durum.ACLineStatus != 0


def surec_yasiyor(pid: int | None) -> bool:
    """Süreç hâlâ çalışıyor mu. `os.kill(pid, 0)` Windows'ta süreci sonlandırır (sinyal yok, TerminateProcess);
    bu yüzden tanıtıcı açılıp çıkış kodu okunur. Bilinmiyorsa (erişim yok) yaşıyor sayılır: iş üst üste başlamasın."""
    if not pid:
        return False
    sorgu, still_active = 0x1000, 259  # PROCESS_QUERY_LIMITED_INFORMATION, STILL_ACTIVE
    k32 = ctypes.windll.kernel32
    tanitici = k32.OpenProcess(sorgu, False, int(pid))
    if not tanitici:
        return k32.GetLastError() == 5  # ERROR_ACCESS_DENIED: var ama erişilemiyor
    try:
        kod = wintypes.DWORD()
        if not k32.GetExitCodeProcess(tanitici, ctypes.byref(kod)):
            return True
        return kod.value == still_active
    finally:
        k32.CloseHandle(tanitici)
