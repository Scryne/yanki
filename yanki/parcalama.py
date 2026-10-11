"""Parçalı üretim: tam şarkıyı vokal boşluklarından ~90 sn'lik parçalara böl, parçaları birleştir.

Neden: 290 sn şarkı XL INT8 100 adımda tek parça ~57 dk (adım başı 34 sn; 90 sn'de ~1 sn) ve ACE-Step'in 600 sn iç
zaman aşımına takılıyor (Faz 2 ölçümü). Scryne'ın onayladığı sonuçlar zaten 90 sn'lik parçalardı.

Kesim noktası: LRCLIB'in zaman damgalı sözlerinde iki satır başı arasındaki aralığın sonuna yakın (bir sonraki satır
başlamadan KESIM_ONCESI sn önce) — önceki satır bitmiş, yenisi başlamamış olur. Parçalar BINDIRME sn üst üste biner,
birleştirmede eşit güçlü geçişle (equal-power crossfade) dikilir.
"""

from dataclasses import dataclass

import numpy as np

from yanki import sozler

KESIM_ONCESI = 0.8
BINDIRME = 1.0  # kesimin iki yanına
KISA_PARCA_PAYI_SN = 1.0  # motor çıktısı planlanandan bu kadar kısa olabilir (kare yuvarlaması)


@dataclass(frozen=True)
class Parca:
    no: int
    bas: float  # bindirme dahil üretim aralığı
    son: float
    cekirdek_bas: float  # bindirmesiz sınırlar (söz dağıtımı ve dikiş için)
    cekirdek_son: float


def kesimler(sure: float, satir_baslari: list[float], hedef: float = 90, en_az: float = 60,
             en_cok: float = 110) -> list[float]:
    """Kesim noktaları. Aday: her satır başından KESIM_ONCESI önce; en uzun boşluğu tercih eder."""
    basl = sorted(satir_baslari)
    adaylar = []  # (kesim, önceki satırdan beri geçen süre = boşluk vekili)
    for i in range(1, len(basl)):
        adaylar.append((basl[i] - KESIM_ONCESI, basl[i] - basl[i - 1]))
    noktalar, p = [], 0.0
    while sure - p > en_cok:
        uygun = [(k, b) for k, b in adaylar if p + en_az <= k <= p + en_cok]
        if uygun:
            # en uzun boşluk; eşitse hedefe yakın olan
            k = max(uygun, key=lambda x: (round(x[1], 1), -abs(x[0] - (p + hedef))))[0]
        else:
            k = p + hedef  # sözsüz uzun bölüm: düz kes
        noktalar.append(round(k, 2))
        p = k
    # son parça çok kısa kalırsa son kesimi kaldır (bir önceki parça en_cok'u biraz aşar)
    if noktalar and sure - noktalar[-1] < en_az / 2:
        noktalar.pop()
    return noktalar


def plan(sure: float, satir_baslari: list[float], **k) -> list[Parca]:
    sinirlar = [0.0, *kesimler(sure, satir_baslari, **k), sure]
    return [Parca(i + 1, max(0.0, sinirlar[i] - BINDIRME), min(sure, sinirlar[i + 1] + BINDIRME),
                  sinirlar[i], sinirlar[i + 1]) for i in range(len(sinirlar) - 1)]


def soz_dagit(parcalar: list[Parca], satirlar: list[tuple[float, str]], sure_sn: float | None = None,
              ad: str = "") -> list[str]:
    """Her parçaya çekirdek aralığında başlayan satırlar, bölüm etiketleriyle. Boş parça: enstrümantal etiketi."""
    return [sozler.aralik_sozu(satirlar, p.cekirdek_bas, p.cekirdek_son, sure_sn, ad) or "[Instrumental]"
            for p in parcalar]


def birlestir(sesler: list[np.ndarray], parcalar: list[Parca], sr: int) -> np.ndarray:
    """Parçaları kaynak zaman çizgisine yerleştirir; bindirmede eşit güçlü geçiş. sesler: (n, kanal)."""
    toplam = int(round(parcalar[-1].son * sr))
    kanal = sesler[0].shape[1]
    cikti = np.zeros((toplam, kanal), dtype=np.float32)
    for i, (s, p) in enumerate(zip(sesler, parcalar, strict=True)):
        # kısa çıkan parça şarkının ortasında sessizlik bırakırdı; toplam süre doğru kaldığı için süre kapısı
        # görmüyordu. Aday birleştirme hatasıyla düşer (son parçanın kuyruğu kısa olabilir: yalnız ara parçalar)
        eksik = (p.son - p.bas) - len(s) / sr
        if i < len(parcalar) - 1 and eksik > KISA_PARCA_PAYI_SN:
            raise ValueError(f"parça {p.no} beklenenden {eksik:.1f} sn kısa")
        bas = int(round(p.bas * sr))
        s = s[: toplam - bas].astype(np.float32)
        kazanc = np.ones(len(s), dtype=np.float32)
        if i > 0:  # giriş: önceki parçayla bindirme
            n = min(len(s), int(round((parcalar[i - 1].son - p.bas) * sr)))
            kazanc[:n] = np.sin(np.linspace(0, np.pi / 2, n))
        if i < len(parcalar) - 1:  # çıkış
            n = min(len(s), int(round((p.son - parcalar[i + 1].bas) * sr)))
            kazanc[len(s) - n:] *= np.cos(np.linspace(0, np.pi / 2, n))
        cikti[bas: bas + len(s)] += s * kazanc[:, None]
    return cikti
