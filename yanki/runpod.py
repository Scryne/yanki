"""RunPod: kiralık GPU sunucusunda ACE-Step (Scryne, 2026-10-10: "güçlü GPU ile çıktıları daha iyi yapalım").

Evdeki 8 GB kart XL-SFT'yi yalnız INT8 nicelemeyle çalıştırabiliyor; resmi uyumluluk tablosunda XL için 20 GB+
(nicelemesiz, offload'suz), tam kalite için 24 GB+ isteniyor (`docs/arastirma/06`). Hat evde kalır (YouTube, Spotify
istemcisi, STILLMORE konut IP'si ve Windows ister); sunucuya yalnız motor gider: aynı `motor_isci.py`, aynı iş JSON'u.

Akış: GraphQL ile saniye faturalı pod açılır (SSH anahtarı `PUBLIC_KEY` ortam değişkeniyle), ACE-Step yereldekiyle aynı
commit'te kurulur, model Hugging Face'ten iner, iş dosyaları scp ile gider, işçi `nohup` ile koşar (SSH kopsa da sürer),
sonuçlar geri alınır. `Pod` bağlam yöneticisi çıkarken pod'u her durumda siler (açık unutulan pod saatlik yanar);
açık pod kimliği `calisma/.runpod/acik_pod`'a da yazılır, düşen koşudan sonra `kapat_artiklari` temizler.

Anahtar `.env` → `RUNPOD_API_KEY` (değer hiçbir yere yazılmaz). SSH anahtarı `calisma/.runpod/` (gitignore'da).
"""

import json
import os
import shlex
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.runpod.io/graphql"
# Küçük temel imaj (0,7 GB, CUDA araç seti yok): PyTorch cu128 tekerlekleri CUDA kütüphanelerini getiriyor, sürücü
# sunucudan. Önce `runpod/pytorch` (11,8 GB) vardı: önbellekte olmayan makinede indirme 15 dk'yı aştı, SSH açılmadı
# (2026-10-10, iki koşu düştü).
IMAJ = "runpod/base:1.4.0-ubuntu2204"
ACESTEP_DEPO = "https://github.com/ace-step/ACE-Step-1.5"


class RunPodHatasi(RuntimeError):
    pass


def anahtar(kok: Path) -> str:
    from yanki.spotify import env_oku

    k = os.environ.get("RUNPOD_API_KEY") or env_oku(kok).get("RUNPOD_API_KEY", "")
    if not k:
        raise RunPodHatasi("RUNPOD_API_KEY yok (.env)")
    return k


def gql(api_anahtari: str, sorgu: str, degiskenler: dict | None = None, deneme: int = 3) -> dict:
    """GraphQL isteği. Geçici ağ hatası ve 5xx `deneme` kez denenir (SSH beklenirken tek bir kopuk yoklama pod'u
    silip koşuyu düşürüyordu); pod açan mutasyon `deneme=1` ile çağrılır (ikinci pod açılmasın). Son hata
    `RunPodHatasi`."""
    from yanki import ag

    govde = json.dumps({"query": sorgu, "variables": degiskenler or {}}).encode()
    istek = urllib.request.Request(API, data=govde, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {api_anahtari}", "User-Agent": "Yanki/0.1"})
    for i in range(deneme):
        try:
            with urllib.request.urlopen(istek, timeout=60) as r:
                cevap = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code < 500 or i == deneme - 1:
                raise RunPodHatasi(f"RunPod {e.code}: {e.read()[:300]!r}") from e
        except (*ag.GECICI, ValueError) as e:  # ValueError: yarım JSON
            if i == deneme - 1:
                raise RunPodHatasi(f"RunPod'a ulaşılamadı: {type(e).__name__}: {e}") from e
        time.sleep(5 * (i + 1))
    if cevap.get("errors"):
        raise RunPodHatasi("; ".join(x.get("message", "?") for x in cevap["errors"]))
    return cevap["data"]


def bakiye(api_anahtari: str) -> float:
    return float(gql(api_anahtari, "query { myself { clientBalance } }")["myself"]["clientBalance"])


def stok(api_anahtari: str, gpu: str) -> str | None:
    """GPU türünün güvenli bulutta stok durumu ("High", "Medium", "Low"; yoksa None)."""
    d = gql(api_anahtari, """query($id: String) { gpuTypes(input: {id: $id}) {
        lowestPrice(input: {gpuCount: 1, secureCloud: true}) { stockStatus } } }""", {"id": gpu})["gpuTypes"]
    return ((d or [{}])[0].get("lowestPrice") or {}).get("stockStatus")


def ssh_anahtari(klasor: Path) -> tuple[Path, str]:
    klasor.mkdir(parents=True, exist_ok=True)
    gizli = klasor / "id_ed25519"
    if not gizli.exists():
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "yanki-runpod", "-f", str(gizli)],
                       check=True)
    return gizli, (klasor / "id_ed25519.pub").read_text(encoding="utf-8").strip()


def kapat_artiklari(api_anahtari: str, klasor: Path) -> list[str]:
    """Önceki koşudan açık kalmış pod'ları siler (kayıttaki kimlik + adı yanki- ile başlayanlar)."""
    silinen = []
    pods = gql(api_anahtari, "query { myself { pods { id name } } }")["myself"]["pods"] or []
    kayit = klasor / "acik_pod"
    kayitli = kayit.read_text(encoding="utf-8").strip() if kayit.exists() else ""
    for p in pods:
        if p["id"] == kayitli or (p.get("name") or "").startswith("yanki-"):
            gql(api_anahtari, "mutation($id: String!) { podTerminate(input: {podId: $id}) }", {"id": p["id"]})
            silinen.append(p["id"])
    kayit.unlink(missing_ok=True)
    return silinen


class Pod:
    """`with Pod(...) as p:` pod açılır, SSH hazır olunca döner; çıkışta (hata olsa da) silinir."""

    def __init__(self, kok: Path, gpu: str = "NVIDIA A40", ad: str = "yanki-motor", disk_gb: int = 120,
                 bulut: str = "SECURE", bekleme_sn: int = 900):
        self.kok, self.gpu, self.ad, self.disk_gb = kok, gpu, ad, disk_gb
        self.bulut, self.bekleme_sn = bulut, bekleme_sn
        self.klasor = kok / "calisma" / ".runpod"
        self.api = anahtar(kok)
        self.id: str | None = None
        self.ip: str | None = None
        self.port: int | None = None
        self.acilis = 0.0

    def __enter__(self) -> "Pod":
        self.gizli, acik = ssh_anahtari(self.klasor)
        # her pod yeni host anahtarıyla gelir; eski pod'un aynı IP:port'taki kaydı bağlantıyı bozmasın
        (self.klasor / "known_hosts").unlink(missing_ok=True)
        d = gql(self.api, """mutation($girdi: PodFindAndDeployOnDemandInput) {
            podFindAndDeployOnDemand(input: $girdi) { id costPerHr machineId } }""", {"girdi": {
            "cloudType": self.bulut, "gpuCount": 1, "gpuTypeId": self.gpu, "name": self.ad, "imageName": IMAJ,
            "containerDiskInGb": self.disk_gb, "volumeInGb": 0, "ports": "22/tcp", "startSsh": True,
            "env": [{"key": "PUBLIC_KEY", "value": acik}],
            "allowedCudaVersions": ["12.8", "12.9", "13.0"]}}, deneme=1)["podFindAndDeployOnDemand"]
        if not d or not d.get("id"):
            raise RunPodHatasi(f"{self.gpu} açılamadı (stok yok olabilir)")
        self.id, self.saatlik = d["id"], float(d.get("costPerHr") or 0)
        self.acilis = time.time()
        (self.klasor / "acik_pod").write_text(self.id, encoding="utf-8")
        try:
            self._ssh_bekle()
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def _ssh_bekle(self) -> None:
        bitis = time.time() + self.bekleme_sn
        son_durum, son_hata = None, None
        while time.time() < bitis:
            p = gql(self.api, """query($id: String!) { pod(input: {podId: $id}) { desiredStatus
                runtime { uptimeInSeconds ports { ip isIpPublic privatePort publicPort type } } } }""",
                    {"id": self.id})["pod"]
            calisma = (p or {}).get("runtime") or {}
            son_durum = {"durum": (p or {}).get("desiredStatus"), "uptime": calisma.get("uptimeInSeconds"),
                         "portlar": [(x["privatePort"], x["isIpPublic"]) for x in calisma.get("ports") or []]}
            ssh = next((x for x in calisma.get("ports") or [] if x["privatePort"] == 22 and x["isIpPublic"]), None)
            if ssh:
                self.ip, self.port = ssh["ip"], int(ssh["publicPort"])
                try:
                    if self.komut("echo hazir", zaman_asimi=30, tekrar=False).strip().endswith("hazir"):
                        return
                except (RunPodHatasi, subprocess.TimeoutExpired) as e:
                    son_hata = str(e)[-300:]
            time.sleep(10)
        raise RunPodHatasi(f"pod {self.id} {self.bekleme_sn} sn içinde SSH'a açılmadı (son durum {son_durum}; "
                           f"son SSH hatası: {son_hata})")

    def _ssh(self) -> list[str]:
        # her pod yeni anahtar: bilinen sunucular projeye yazılır (/dev/null Windows OpenSSH'ta yok). BatchMode: soru
        # sorup beklemesin; ServerAlive 15 sn × 4: ölü bağlantı ~1 dk'da 255 verir
        return ["-i", str(self.gizli), "-o", "StrictHostKeyChecking=no",
                "-o", f"UserKnownHostsFile={self.klasor / 'known_hosts'}", "-o", "BatchMode=yes",
                "-o", "LogLevel=ERROR", "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=4",
                "-o", "ConnectTimeout=20"]

    # Geçici bağlantı sorunları yeniden denenir: SSH/scp 255 (2026-10-10: ~400 MB kaynak yüklenirken 7. dosyada koptu)
    # ve zaman aşımı (2026-10-10: RunPod'un TCP vekili bağlantıyı kabul edip cevap vermedi, kısa bir `mkdir` 1 saat
    # asılı kaldı; komutların zaman aşımı artık işine göre kısa).
    DENEME, BEKLEME_SN = 4, 10
    KISA_SN = 120  # basit komut

    def _tekrarla(self, arg: list[str], zaman_asimi: float, deneme: int) -> subprocess.CompletedProcess:
        for i in range(deneme):
            t = time.time()
            try:
                r = subprocess.run(arg, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   timeout=zaman_asimi, stdin=subprocess.DEVNULL)
            except subprocess.TimeoutExpired:
                r = subprocess.CompletedProcess(arg, 255, "", f"zaman aşımı ({zaman_asimi:.0f} sn)")
            self._gunluk(f"{arg[0]} {arg[-1][:80]!r} → {r.returncode} ({time.time() - t:.0f} sn)"
                         + (f" {r.stderr.strip()[-200:]}" if r.returncode else ""))
            if r.returncode != 255 or i == deneme - 1:
                return r
            time.sleep(self.BEKLEME_SN * (i + 1))
        raise AssertionError("ulaşılmaz")

    def _gunluk(self, satir: str) -> None:
        """Uzak adımların zaman çizelgesi (`calisma/gunluk/runpod.log`): koşu düşünce nerede takıldığı görünsün."""
        try:
            yol = self.kok / "calisma" / "gunluk" / "runpod.log"
            yol.parent.mkdir(parents=True, exist_ok=True)
            with open(yol, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {self.id} {satir}\n")
        except OSError:
            pass

    def komut(self, betik: str, zaman_asimi: float = KISA_SN, tekrar: bool = True) -> str:
        """`tekrar=False`: tekrarlanamayan komut (işçiyi başlatmak) bağlantı koparsa yeniden gönderilmez."""
        r = self._tekrarla(["ssh", *self._ssh(), "-p", str(self.port), f"root@{self.ip}", "bash -lc " +
                            shlex.quote(betik)], zaman_asimi, self.DENEME if tekrar else 1)
        if r.returncode != 0:
            raise RunPodHatasi(f"komut {r.returncode}: {(r.stderr or r.stdout)[-1500:]}")
        return r.stdout

    def gonder(self, yerel: Path, uzak: str, zaman_asimi: float = 900) -> None:
        r = self._tekrarla(["scp", *self._ssh(), "-P", str(self.port), "-q", str(yerel), f"root@{self.ip}:{uzak}"],
                           zaman_asimi, self.DENEME)
        if r.returncode != 0:
            raise RunPodHatasi(f"gönderilemedi ({yerel.name}, {r.returncode}): {r.stderr[-500:]}")

    def al(self, uzak: str, yerel: Path, zaman_asimi: float = 900) -> Path:
        yerel.parent.mkdir(parents=True, exist_ok=True)
        r = self._tekrarla(["scp", *self._ssh(), "-P", str(self.port), "-q", f"root@{self.ip}:{uzak}", str(yerel)],
                           zaman_asimi, self.DENEME)
        if r.returncode != 0:
            raise RunPodHatasi(f"alınamadı ({uzak}, {r.returncode}): {r.stderr[-500:]}")
        return yerel

    def maliyet(self) -> float:
        return round(self.saatlik * (time.time() - self.acilis) / 3600, 3) if self.acilis else 0.0

    def __exit__(self, *_):
        if self.id:
            for _deneme in range(3):
                try:
                    gql(self.api, "mutation($id: String!) { podTerminate(input: {podId: $id}) }", {"id": self.id})
                    (self.klasor / "acik_pod").unlink(missing_ok=True)
                    break
                except (RunPodHatasi, OSError):
                    time.sleep(5)


def acestep_kur(p: Pod, commit: str, modeller: tuple[str, ...] = ("acestep-v15-xl-sft",)) -> str:
    """ACE-Step'i yereldeki commit'le kurar, modelleri indirir. Döner: kurulum dizini."""
    hedef = "/root/ACE-Step-1.5"
    indir = " && ".join(f"uv run acestep-download --model {m}" for m in modeller)
    p.komut(f"""set -e
        command -v uv >/dev/null || (curl -LsSf https://astral.sh/uv/install.sh | sh)
        export PATH="$HOME/.local/bin:$PATH"
        [ -d {hedef} ] || git clone -q {ACESTEP_DEPO} {hedef}
        cd {hedef} && git fetch -q origin && git checkout -q {commit}
        uv sync -q
        uv run acestep-download && {indir}""", zaman_asimi=1800)
    # indirme sessizce boş geçebilir: model klasörü gerçekten dolu mu (2026-10-10 ilk denemede kurulum 40 sn sürdü)
    for m in modeller:
        boyut = (p.komut(f"du -sm {hedef}/checkpoints/{m} 2>/dev/null | cut -f1").strip() or "0").split()[0]
        if int(boyut) < 1000:
            raise RunPodHatasi(f"{m} inmemiş ({boyut} MB): {p.komut(f'ls -la {hedef}/checkpoints || true')[:500]}")
    return hedef
