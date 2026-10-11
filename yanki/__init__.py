"""Yanki: listedeki şarkıların cover'ını üretip yükleme paketi hazırlayan yarı otomatik hat."""

# Ad çözümleme düzeltmesi (`ag._cozumle`) her dış istekten önce yerinde olsun: Spotify, TypeSafe, RunPod istemcileri
# `ag`'yi kendileri içe aktarmıyor.
from yanki import ag as _ag  # noqa: F401
