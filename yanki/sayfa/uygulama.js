// Yanki dinleme odası. Derleme yok; sunucu: yanki/sunucu.py
const $ = (s, k = document) => k.querySelector(s);
const el = (etiket, ozellik = {}, ...cocuk) => {
  const e = document.createElement(etiket);
  for (const [k, v] of Object.entries(ozellik)) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) e.setAttribute(k, v === true ? "" : v);
  }
  for (const c of cocuk.flat()) if (c != null && c !== false) e.append(c);
  return e;
};
const sure = (s) => { s = Math.max(0, s || 0); return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`; };
const aralik = (a, b) => `${sure(a)}–${sure(b)}`;
const css = (ad) => getComputedStyle(document.documentElement).getPropertyValue(ad).trim();

const ASAMA = {
  yeni: "yeni", hazir: "hazır", analiz: "analizde", uretildi: "dinlemede", onarim: "onarım bekliyor",
  onaylandi: "onaylandı", paketlendi: "paketlendi", yuklendi: "yüklendi", yayinda: "yayında", hata: "hata", reddedildi: "reddedildi",
};
const KAPI = { parmak_izi: "parmak izi", dalga: "dalga", soz_wer: "söz", sure_fark: "süre", motor: "motor" };
const DAGITIM = { draft: "taslak", pending: "incelemede", approved: "onaylandı", live: "mağazalarda", rejected: "reddedildi",
  takedown: "kaldırıldı", takedown_requested: "kaldırılıyor", taken_down: "kaldırıldı" };
const DAGITIMCI = { tunearo: "Tunearo", routenote: "RouteNote", distrokid: "DistroKid" };

// kapak: sunucu adres verdiyse küçük resim, yoksa dalga işaretli boş kare (olmayan kapağa istek atılmaz)
function kapakImg(url, sinif = "kapak-kucuk", boyut = 96) {
  if (!url) return el("span", { class: `${sinif} bos`, "aria-hidden": "true" }, dalgaIsareti());
  return el("img", { class: sinif, src: `${url}&boyut=${boyut}`, alt: "", loading: "lazy", decoding: "async", width: 32, height: 32 });
}
function dalgaIsareti() {
  const ns = "http://www.w3.org/2000/svg", svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 32 32"); svg.setAttribute("width", "16"); svg.setAttribute("height", "16");
  const yol = document.createElementNS(ns, "path");
  yol.setAttribute("d", "M6 16h3M11 10v12M16 6v20M21 11v10M26 15v2"); yol.setAttribute("stroke", "currentColor");
  yol.setAttribute("stroke-width", "2.4"); yol.setAttribute("stroke-linecap", "round"); yol.setAttribute("fill", "none");
  svg.append(yol);
  return svg;
}

function bildir(mesaj, hata = false) {
  const b = $("#bildirim");
  b.textContent = mesaj; b.classList.toggle("hata", hata); b.classList.add("acik");
  clearTimeout(bildir.t); bildir.t = setTimeout(() => b.classList.remove("acik"), 4000);
}

async function api(yol, govde) {
  const r = await fetch(yol, govde ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(govde) } : {});
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    // 422: alan doğrulaması liste döner
    const ayrinti = Array.isArray(d.detail) ? `Geçersiz değer: ${d.detail.map((x) => x.loc?.at(-1)).join(", ")}` : d.detail;
    throw new Error(ayrinti || `${r.status}`);
  }
  return r.json();
}

// ---- dalga şeridi ----
let calan = null; // aynı anda tek ses
class Serit {
  constructor({ kimlik, dosya, secilebilir = false, vurgu = null, kucuk = false, etiket }) {
    this.kimlik = kimlik; this.dosya = dosya; this.secilebilir = secilebilir; this.vurgu = vurgu;
    this.secim = null; this.tepe = []; this.toplam = 0;
    this.ses = el("audio", { preload: "none", src: `/ses/${kimlik}/${dosya}` });
    this.tuval = el("canvas", { role: "img", "aria-label": `${etiket} dalga formu` + (secilebilir ? "; sürükleyerek aralık seç" : "") });
    this.kap = el("div", { class: "dalga-kap" + (kucuk ? " kucuk" : ""), tabindex: "0", "aria-label": `${etiket}: boşluk çal/durdur` + (secilebilir ? ", Shift+ok seçimi genişletir, Esc temizler" : "") }, this.tuval);
    this.zaman = el("span", { class: "zaman" }, "0:00");
    this.secimYazi = el("span", { class: "secim", "aria-live": "polite" });
    this.calDugme = el("button", { class: "dugme", type: "button", onclick: () => this.cal() }, "Çal");
    this.ses.addEventListener("timeupdate", () => this.ciz());
    this.ses.addEventListener("play", () => { this.calDugme.textContent = "Durdur"; });
    this.ses.addEventListener("pause", () => { this.calDugme.textContent = "Çal"; });
    this.ses.addEventListener("ended", () => { this.calDugme.textContent = "Çal"; });
    this.kap.addEventListener("keydown", (e) => this.tus(e));
    this.fareBagla();
    new ResizeObserver(() => this.ciz()).observe(this.kap);
    this.yukle();
  }
  async yukle() {
    try { const d = await api(`/api/dalga/${this.kimlik}/${this.dosya}`); this.tepe = d.tepe; this.toplam = d.sure; this.ciz(); }
    catch (e) { this.zaman.textContent = "dalga okunamadı"; }
  }
  sn(x) { const r = this.tuval.getBoundingClientRect(); return Math.min(1, Math.max(0, (x - r.left) / r.width)) * this.toplam; }
  fareBagla() {
    let bas = null, tasindi = false;
    this.tuval.addEventListener("pointerdown", (e) => { bas = this.sn(e.clientX); tasindi = false; this.tuval.setPointerCapture(e.pointerId); });
    this.tuval.addEventListener("pointermove", (e) => {
      if (bas == null || !this.secilebilir) return;
      const s = this.sn(e.clientX);
      if (Math.abs(s - bas) > 0.25) { tasindi = true; this.secimKoy(Math.min(bas, s), Math.max(bas, s)); }
    });
    this.tuval.addEventListener("pointerup", (e) => {
      if (bas != null && !tasindi) { this.ses.currentTime = this.sn(e.clientX); this.ciz(); }
      bas = null;
    });
  }
  secimKoy(a, b) {
    this.secim = a == null ? null : [Math.max(0, a), Math.min(this.toplam, b)];
    this.secimYazi.textContent = this.secim ? `seçim ${aralik(...this.secim)}` : "";
    this.onSecim?.(this.secim); this.ciz();
  }
  tus(e) {
    if (e.key === " ") { e.preventDefault(); this.cal(); }
    else if (e.key === "Escape") this.secimKoy(null);
    else if (this.secilebilir && e.shiftKey && (e.key === "ArrowRight" || e.key === "ArrowLeft")) {
      e.preventDefault();
      const t = this.ses.currentTime, [a, b] = this.secim || [t, t];
      this.secimKoy(e.key === "ArrowLeft" ? a - 0.5 : a, e.key === "ArrowRight" ? b + 0.5 : b);
    } else if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault(); this.ses.currentTime += e.key === "ArrowRight" ? 5 : -5;
    }
  }
  cal(bas, son) {
    if (calan && calan !== this) calan.ses.pause();
    calan = this;
    if (bas != null) { this.ses.currentTime = bas; this.dur = son; }
    if (this.ses.paused || bas != null) this.ses.play().catch((e) => bildir(`Çalınamadı: ${e.message}`, true));
    else this.ses.pause();
  }
  ciz() {
    const t = this.tuval, dpr = devicePixelRatio || 1, w = t.clientWidth, h = t.clientHeight;
    if (!w) return;
    if (t.width !== w * dpr) { t.width = w * dpr; t.height = h * dpr; }
    const c = t.getContext("2d"); c.setTransform(dpr, 0, 0, dpr, 0, 0); c.clearRect(0, 0, w, h);
    const x = (s) => (s / (this.toplam || 1)) * w;
    for (const [a, b, renk] of [[...(this.vurgu || []), css("--primary-zayif")], [...(this.secim || []), css("--primary-zayif")]]) {
      if (a == null) continue;
      c.fillStyle = renk; c.fillRect(x(a), 0, x(b) - x(a), h);
      c.strokeStyle = css("--primary"); c.lineWidth = 1; c.strokeRect(x(a) + .5, .5, x(b) - x(a) - 1, h - 1);
    }
    const an = this.ses.currentTime || 0, n = this.tepe.length, orta = h / 2;
    for (let i = 0; i < n; i++) {
      const px = (i / n) * w, y = Math.max(1, this.tepe[i] * (h / 2 - 4));
      c.fillStyle = (i / n) * this.toplam <= an ? css("--dalga-calinan") : css("--dalga");
      c.fillRect(px, orta - y, Math.max(1, w / n - 0.5), y * 2);
    }
    c.fillStyle = css("--oynatma"); c.fillRect(x(an), 0, 2, h);
    this.zaman.textContent = `${sure(an)} / ${sure(this.toplam)}`;
    if (this.dur != null && an >= this.dur) { this.ses.pause(); this.dur = null; }
  }
}

// ---- şarkı ekranı ----
async function sarkiGoster(kimlik) {
  const ana = $("#ana");
  let d;
  try { d = await api(`/api/sarki/${kimlik}`); } catch (e) { ana.replaceChildren(el("p", { class: "ipucu" }, `Şarkı açılamadı: ${e.message}`)); return; }
  const k = d.kunye || {};
  const y = d.yukleme;
  const parcalar = [
    el("div", { class: "sarki-ust" },
      kapakKutu(d),
      el("div", {},
        el("header", { class: "baslik" }, el("h1", {}, d.ad), el("span", { class: "sanatci" }, d.sanatci),
          el("span", { class: "asama", "data-a": d.asama }, ASAMA[d.asama] || d.asama)),
        el("p", { class: "kunye" },
          el("span", {}, "Yazarlar: ", el("b", {}, (k.yazarlar || []).join(", ") || "bulunamadı")),
          el("span", {}, "Stil: ", el("b", {}, d.analiz?.stil || "—")),
          el("span", {}, "Tempo/ton: ", el("b", {}, [d.analiz?.bpm && `${d.analiz.bpm} BPM`, d.analiz?.ton].filter(Boolean).join(" · ") || "—")),
          el("span", {}, "Kaynak: ", el("b", {}, d.kaynak?.baslik || "—"))),
        y ? el("p", { class: "kunye" },
          el("span", {}, "Dağıtım: ", el("b", {}, DAGITIMCI[y.dagitimci] || y.dagitimci || "—")),
          y.dagitim_durumu ? el("span", {}, "Durum: ", el("b", {}, DAGITIM[y.dagitim_durumu] || y.dagitim_durumu)) : null,
          el("span", {}, "Çıkış: ", el("b", {}, tarih(y.yayin_tarihi))),
          y.isrc ? el("span", {}, "ISRC: ", el("b", {}, y.isrc)) : null, y.upc ? el("span", {}, "UPC: ", el("b", {}, y.upc)) : null) : null)),
  ];
  if (d.hata) parcalar.push(el("p", { class: "uyari", role: "alert" }, d.hata));
  if (d.onay_engeli) parcalar.push(el("p", { class: "not" },
    `Bu şarkı kendiliğinden onaylanmaz (${d.onay_engeli}). Sen karar verene kadar yayına girmez.`));
  if (d.otomatik_onay) parcalar.push(el("p", { class: "ipucu bekleyen" },
    `Karar vermezsen ${new Date(d.otomatik_onay.zaman).toLocaleString("tr-TR", { weekday: "long", hour: "2-digit", minute: "2-digit" })}`
    + ` aday ${d.otomatik_onay.aday} kendiliğinden onaylanır (sözü en anlaşılır olan). Onaylamak, onarım istemek ya da reddetmek bunu iptal eder.`));
  const duzenlenebilir = ["uretildi", "onarim"].includes(d.asama);
  panelTus = null;
  parcalar.push(karsilastirma(d, duzenlenebilir));
  if (["uretildi", "hata"].includes(d.asama) && d.analiz?.stil) parcalar.push(stilKutu(d));
  if (d.asama === "analiz" && d.adaylar.length) parcalar.push(el("p", { class: "ipucu bekleyen" },
    "Yeni adaylar sırada; sonraki koşuda üretilir. O zamana kadar mevcut adaylar yalnız dinlenebilir."));
  if (d.kaynak?.dosya) parcalar.push(seritKutu({ kimlik, dosya: d.kaynak.dosya, baslik: "Orijinal", alt: "karşılaştırma için" }));
  const stilFarkli = new Set(d.adaylar.map((a) => a.stil || "")).size > 1;
  for (const a of d.adaylar) parcalar.push(adayKutu(d, a, duzenlenebilir, stilFarkli));
  if (!d.adaylar.length && !d.hata) parcalar.push(el("p", { class: "ipucu" }, "Adaylar henüz üretilmedi. Üretim GPU boşken arka planda çalışır."));
  if (!["reddedildi", "yuklendi", "yayinda"].includes(d.asama)) {
    parcalar.push(el("div", { class: "alt-cubuk" },
      el("span", { class: "ipucu" }, d.asama === "onaylandi" ? `Onaylanan: aday ${d.secilen}. Paket sonraki koşuda hazırlanır.` : "Dalga üzerinde sürükle: aralık seç · Boşluk: çal/durdur"),
      el("span", { class: "bosluk" }),
      el("button", { class: "dugme tehlike", type: "button", onclick: () => reddet(d) }, "Şarkıyı reddet")));
  } else if (d.asama === "reddedildi") {
    parcalar.push(el("div", { class: "alt-cubuk" },
      el("span", { class: "ipucu" }, "Bu şarkıyı reddettin. Geri alırsan reddetmeden önceki aşamasına döner; adaylar yerinde."),
      el("span", { class: "bosluk" }),
      el("button", { class: "dugme ikincil", type: "button",
        onclick: () => eylem(d, "geri-al", {}, `"${d.ad}" yeniden listede, reddetmeden önceki aşamasında.`) }, "Reddi geri al")));
  }
  ana.replaceChildren(...parcalar.filter(Boolean));
}

function kapakKutu(d) {
  const degisir = ["uretildi", "onarim", "onaylandi", "paketlendi"].includes(d.asama) && !d.kapak_elle;
  const gorsel = d.kapak ? el("img", { class: "kapak-buyuk", src: `${d.kapak}&boyut=480`, alt: `${d.ad} kapağı`, width: 132, height: 132 })
    : el("div", { class: "kapak-buyuk kapak-yok" }, degisir ? "Kapak paketlemede Pinterest'ten seçilir" : "Kapak yok");
  const bilgi = d.kapak_elle ? "elle seçilen (kapak_ozel.jpg)"
    : d.kapak_bilgi?.aciklama ? `Pinterest: ${d.kapak_bilgi.aciklama}` : null;
  const dugme = degisir ? el("button", { class: "dugme ikincil kucuk", type: "button",
    onclick: (e) => kapakDegistir(d, e.currentTarget) }, d.kapak ? "Başka kapak" : "Kapak bul") : null;
  return el("div", { class: "kapak-kutu" }, gorsel, bilgi && el("p", { class: "ipucu", title: bilgi }, bilgi), dugme);
}

async function kapakDegistir(d, dugme) {
  dugme.disabled = true; dugme.setAttribute("aria-busy", "true");
  const eski = dugme.textContent; dugme.textContent = d.asama === "paketlendi" ? "Kapak ve paket yenileniyor…" : "Aranıyor…";
  try {
    const r = await api(`/api/sarki/${d.kimlik}/kapak`, {});
    bildir(`Yeni kapak: ${r.kapak_bilgi?.aciklama || "Pinterest"}. Eskisi bir daha seçilmez.`);
    await yenile(d.kimlik);
  } catch (e) { bildir(e.message, true); dugme.disabled = false; dugme.removeAttribute("aria-busy"); dugme.textContent = eski; }
}

// ---- hızlı karşılaştırma: aynı kesit, adaylar arasında konumu koruyarak geçiş ----
// Tam dinleme şarkı başı ~15 dk; burada 3 kesit × aday. Sıra söz WER'ine göre (yalnız öneri, ±0,04 oynuyor).
let panelTus = null;
addEventListener("keydown", (e) => {
  if (!panelTus || e.ctrlKey || e.altKey || e.metaKey) return;
  if (e.target.closest?.("input, textarea, select, summary, .dalga-kap")) return;
  if (e.key === " " && e.target.closest?.("button, a")) return; // odaktaki düğmenin kendi tıklaması
  panelTus(e);
});

function karsilastirma(d, duzenlenebilir) {
  const wer = (a) => a.kapilar?.soz_wer?.deger ?? Infinity;
  const adaylar = d.adaylar.filter((a) => a.gecti && a.dosya).sort((x, y) => wer(x) - wer(y));
  if (!d.kesitler?.length || !adaylar.length) return null;
  const izler = [
    ...(d.kaynak?.dosya ? [{ tus: "0", ad: "Orijinal", dosya: d.kaynak.dosya }] : []),
    ...adaylar.map((a) => ({ tus: a.no <= 9 ? String(a.no) : null, ad: `Aday ${a.no}`, dosya: a.dosya, aday: a })),
  ];
  let k = 0, aktif = null, sirayla = false;
  const kesit = () => d.kesitler[k];

  const zaman = el("span", { class: "zaman" }, "0:00 / 0:00");
  const cubuk = el("span", { class: "ilerleme-dolu" });
  const calDugme = el("button", { class: "dugme", type: "button", onclick: () => calDurdur() }, "Çal");
  const siraDugme = el("button", { class: "dugme", type: "button", onclick: () => siraylaBasla() }, "Sırayla çal");
  const onayDugme = el("button", { class: "dugme birincil", type: "button", disabled: true, onclick: () => aktif?.aday && onayVer(d, aktif.aday) }, "Onayla");
  const kesitDugmeleri = d.kesitler.map((x, i) => el("button", { class: "kesit", type: "button", "aria-pressed": i === 0 ? "true" : "false", onclick: () => kesitSec(i) },
    x.ad, el("span", { class: "kesit-zaman" }, aralik(x.bas, x.son))));

  const goster = () => {
    const kx = kesit(), t = aktif ? aktif.ses.currentTime : kx.bas;
    const oran = Math.min(1, Math.max(0, (t - kx.bas) / (kx.son - kx.bas)));
    cubuk.style.transform = `scaleX(${oran})`;
    zaman.textContent = `${sure(Math.max(0, t - kx.bas))} / ${sure(kx.son - kx.bas)}`;
    const caliyor = aktif && !aktif.ses.paused;
    calDugme.textContent = caliyor ? "Durdur" : "Çal";
    siraDugme.setAttribute("aria-pressed", sirayla ? "true" : "false");
    for (const iz of izler) iz.dugme.setAttribute("aria-pressed", iz === aktif ? "true" : "false");
    const a = aktif?.aday, bekleyen = a?.onarimlar.some((o) => o.durum === "bekliyor");
    onayDugme.disabled = !duzenlenebilir || !a || bekleyen;
    onayDugme.textContent = a ? `Onayla: aday ${a.no}` : "Onayla";
    onayDugme.title = bekleyen ? "Bu adayın bekleyen onarımı var" : "";
  };
  const oynat = (iz, konum) => {
    if (aktif && aktif !== iz) aktif.ses.pause();
    if (calan && calan.ses !== iz.ses) calan.ses.pause();
    calan = { ses: iz.ses };
    aktif = iz;
    const kx = kesit();
    iz.ses.currentTime = Math.min(kx.son - 0.25, Math.max(kx.bas, konum));
    iz.ses.play().catch((e) => bildir(`Çalınamadı: ${e.message}`, true));
    goster();
  };
  const gec = (iz) => oynat(iz, aktif ? aktif.ses.currentTime : kesit().bas);
  const calDurdur = () => {
    if (!aktif) return oynat(izler.find((iz) => iz.aday) || izler[0], kesit().bas);
    if (aktif.ses.paused) oynat(aktif, aktif.ses.currentTime >= kesit().son - 0.25 ? kesit().bas : aktif.ses.currentTime);
    else aktif.ses.pause();
  };
  const siraylaBasla = () => { sirayla = true; oynat(izler.find((iz) => iz.aday), kesit().bas); };
  const kesitSec = (i) => {
    const caliyor = aktif && !aktif.ses.paused;
    k = (i + d.kesitler.length) % d.kesitler.length;
    kesitDugmeleri.forEach((b, j) => b.setAttribute("aria-pressed", j === k ? "true" : "false"));
    if (caliyor) oynat(aktif, kesit().bas);
    else { if (aktif) aktif.ses.currentTime = kesit().bas; goster(); }
  };
  const sonaGeldi = (iz) => {
    const sonraki = sirayla && izler.slice(izler.indexOf(iz) + 1).find((x) => x.aday);
    if (sonraki) return oynat(sonraki, kesit().bas);
    sirayla = false; iz.ses.pause(); iz.ses.currentTime = kesit().bas; goster();
  };

  for (const iz of izler) {
    iz.ses = el("audio", { preload: "none", src: `/ses/${d.kimlik}/${iz.dosya}` });
    iz.ses.addEventListener("timeupdate", () => {
      if (iz !== aktif) return;
      if (iz.ses.currentTime >= kesit().son) sonaGeldi(iz); else goster();
    });
    for (const olay of ["play", "pause"]) iz.ses.addEventListener(olay, () => iz === aktif && goster());
    const w = iz.aday ? wer(iz.aday) : null;
    iz.dugme = el("button", { class: "iz" + (iz.aday ? "" : " orijinal"), type: "button", "aria-pressed": "false",
      onclick: () => { sirayla = false; gec(iz); } },
      el("kbd", {}, iz.tus ?? "·"), el("span", { class: "iz-ad" }, iz.ad),
      iz.aday ? el("span", { class: "iz-deger" }, Number.isFinite(w) ? `söz ${String(w).replace(".", ",")}` : "söz —", ` · tohum ${iz.aday.tohum}`)
        : el("span", { class: "iz-deger" }, "karşılaştırma için"));
  }

  panelTus = (e) => {
    const iz = izler.find((x) => x.tus === e.key);
    if (iz) { e.preventDefault(); sirayla = false; gec(iz); }
    else if (e.key === " ") { e.preventDefault(); calDurdur(); }
    else if (e.key === "ArrowRight" || e.key === "ArrowLeft") { e.preventDefault(); kesitSec(k + (e.key === "ArrowRight" ? 1 : -1)); }
    else if (e.key === "s" || e.key === "S") { e.preventDefault(); siraylaBasla(); }
  };

  const kutu = el("section", { class: "serit karsilastir", "aria-label": "Hızlı karşılaştırma" },
    el("div", { class: "serit-ust" }, el("h2", {}, "Hızlı karşılaştırma"),
      el("span", { class: "ipucu kucuk-ipucu" }, "Adaylar söz hatasına göre sıralı; geçişte konum korunur")),
    el("div", { class: "kesitler", role: "group", "aria-label": "Kesit" }, kesitDugmeleri),
    el("ol", { class: "izler" }, izler.map((iz) => el("li", {}, iz.dugme))),
    el("div", { class: "ilerleme", "aria-hidden": "true" }, cubuk),
    el("div", { class: "serit-alt" }, calDugme, siraDugme, zaman, el("span", { class: "bosluk" }), duzenlenebilir ? onayDugme : null),
    el("p", { class: "ipucu kucuk-ipucu kisayol" }, el("kbd", {}, "0–9"), " iz · ", el("kbd", {}, "←"), el("kbd", {}, "→"), " kesit · ",
      el("kbd", {}, "Boşluk"), " çal/durdur · ", el("kbd", {}, "S"), " sırayla"),
    izler.map((iz) => iz.ses));
  goster();
  return kutu;
}

function seritKutu({ kimlik, dosya, baslik, alt }) {
  const s = new Serit({ kimlik, dosya, etiket: baslik });
  return el("section", { class: "serit", "aria-label": baslik },
    el("div", { class: "serit-ust" }, el("h2", {}, baslik), alt && el("span", { class: "tohum" }, alt)),
    s.kap, el("div", { class: "serit-alt" }, s.calDugme, s.zaman, s.ses));
}

function stilKutu(d) {
  const an = d.analiz;
  const stil = el("textarea", { id: "stil-metin", rows: 3, maxlength: 500, required: true }, an.stil);
  const bpm = el("input", { id: "stil-bpm", type: "number", min: 30, max: 300, inputmode: "numeric", value: an.bpm ?? "" });
  const ton = el("input", { id: "stil-ton", type: "text", maxlength: 20, placeholder: "ör. A major", value: an.ton || "" });
  const gonder = (e) => {
    e.preventDefault();
    eylem(d, "stil", { stil: stil.value, bpm: bpm.value ? +bpm.value : null, ton: ton.value },
      "Yeni stil kaydedildi. Adaylar sonraki koşuda üretilecek; mevcut adaylar yerinde kalır.");
  };
  return el("details", { class: "stil-duzen" },
    el("summary", {}, "Stili düzenle ve yeniden üret"),
    el("form", { onsubmit: gonder },
      el("label", { for: "stil-metin" }, "Stil tanımı ", el("span", { class: "ipucu" }, "(İngilizce; tür, vokal, çalgılar, hava)")),
      stil,
      el("div", { class: "stil-satir" },
        el("label", { for: "stil-bpm" }, "BPM", bpm),
        el("label", { for: "stil-ton" }, "Ton", ton),
        el("span", { class: "bosluk" }),
        el("button", { class: "dugme ikincil", type: "submit" }, "Bu stille yeniden üret")),
      el("p", { class: "ipucu" }, "Mevcut adaylar silinmez; yeni adaylar onların ardından eklenir. Boş bırakılan BPM ve ton modele bırakılır.")));
}

function rozetler(kapilar) {
  return Object.entries(kapilar || {}).map(([ad, v]) => el("span", { class: `rozet ${v.gecti ? "ok" : "no"}` },
    `${KAPI[ad] || ad} ${v.deger != null ? String(v.deger).replace(".", ",") : ""} ${v.gecti ? "✓" : "✗"}`));
}

function adayKutu(d, a, duzenlenebilir, stilFarkli) {
  const baslik = `Aday ${a.no}`;
  if (!a.dosya) return el("section", { class: "serit dusen" }, el("div", { class: "serit-ust" }, el("h2", {}, baslik), ...rozetler(a.kapilar)));
  const s = new Serit({ kimlik: d.kimlik, dosya: a.dosya, secilebilir: duzenlenebilir && a.gecti, etiket: baslik });
  const onar = el("button", { class: "dugme punch", type: "button", disabled: true, onclick: () => onarimIste(d, a, s.secim) }, "Bu aralığı onar");
  const secimCal = el("button", { class: "dugme", type: "button", disabled: true, onclick: () => s.cal(Math.max(0, s.secim[0] - 3), s.secim[1] + 3) }, "Seçimi çal");
  s.onSecim = (sec) => { onar.disabled = !sec; secimCal.disabled = !sec; };
  const bekleyen = a.onarimlar.some((o) => o.durum === "bekliyor");
  const onayla = el("button", { class: "dugme birincil", type: "button", disabled: !(duzenlenebilir && a.gecti) || bekleyen, onclick: () => onayVer(d, a) }, "Bu adayı onayla");
  const kutu = el("section", { class: "serit" + (a.gecti ? "" : " dusen"), "aria-label": baslik },
    el("div", { class: "serit-ust" }, el("h2", {}, baslik), el("span", { class: "tohum" }, `tohum ${a.tohum}`),
      ...rozetler(a.kapilar), !a.gecti && el("span", { class: "rozet no" }, "kapıdan geçmedi")),
    stilFarkli && el("p", { class: "aday-stil" }, "Stil: ", a.stil || "ilk otomatik tanım"),
    s.kap,
    el("div", { class: "serit-alt" }, s.calDugme, s.zaman, s.secimYazi, el("span", { class: "bosluk" }),
      a.gecti && duzenlenebilir ? [secimCal, onar, onayla] : null, s.ses));
  const onarimlar = a.onarimlar.filter((o) => o.durum !== "ret");
  if (onarimlar.length) kutu.append(el("div", { class: "onarimlar" }, onarimlar.map((o) => onarimKutu(d, a, o))));
  return kutu;
}

function onarimKutu(d, a, o) {
  const [bas, son] = o.bolge;
  const etiket = el("div", { class: "etiket" }, `${aralik(bas, son)} · tohum ${o.tohum} · `,
    { bekliyor: "üretim bekliyor", hazir: "dinlemeye hazır", kabul: "kabul edildi", hata: `hata: ${o.hata || ""}` }[o.durum] || o.durum);
  if (o.durum !== "hazir" && o.durum !== "kabul") return el("div", { class: "onarim", "data-d": o.durum }, etiket);
  const s = new Serit({ kimlik: d.kimlik, dosya: o.dosya, vurgu: [bas, son], kucuk: true, etiket: `Onarım ${aralik(bas, son)}` });
  const bolgeCal = el("button", { class: "dugme", type: "button", onclick: () => s.cal(Math.max(0, bas - 3), son + 3) }, "Bölgeyi çal");
  const kabul = o.durum === "hazir" ? el("button", { class: "dugme punch", type: "button", onclick: () => onarimKabul(d, a, o) }, "Bunu kabul et") : null;
  return el("div", { class: "onarim", "data-d": o.durum }, etiket, s.kap,
    el("div", { class: "serit-alt" }, bolgeCal, s.zaman, ...rozetler(o.kapilar), el("span", { class: "bosluk" }), kabul, s.ses));
}

async function eylem(d, yol, govde, basari) {
  try { await api(`/api/sarki/${d.kimlik}/${yol}`, govde); bildir(basari); await yenile(d.kimlik); }
  catch (e) { bildir(e.message, true); }
}
const onarimIste = (d, a, sec) => eylem(d, "onar", { aday: a.no, bas: +sec[0].toFixed(2), son: +sec[1].toFixed(2) },
  `Aday ${a.no}, ${aralik(...sec)} onarım sırasına alındı. Hat iki sürüm üretecek; hazır olunca burada dinlersin.`);
const onarimKabul = (d, a, o) => eylem(d, "onarim-kabul", { aday: a.no, onarim: o.id }, `Onarım kabul edildi: aday ${a.no} artık bu sürüm.`);
// onay ve ret şarkıyı dinlemeden çıkarır: dinlemedeki sıradaki şarkıya geç
async function eylemSonraki(d, yol, govde, basari) {
  try {
    await api(`/api/sarki/${d.kimlik}/${yol}`, govde);
    const liste = await api("/api/sarkilar");
    const i = liste.findIndex((s) => s.kimlik === d.kimlik);
    const bekleyen = liste.filter((s) => s.asama === "uretildi" && s.kimlik !== d.kimlik);
    const sonraki = bekleyen.find((s) => liste.indexOf(s) > i) || bekleyen[0];
    bildir(sonraki ? `${basari} Sıradaki: ${sonraki.ad}.` : `${basari} Dinlemede başka şarkı kalmadı.`);
    if (sonraki) location.hash = sonraki.kimlik; else await yenile(d.kimlik);
  } catch (e) { bildir(e.message, true); }
}
const onayVer = (d, a) => eylemSonraki(d, "onayla", { aday: a.no }, `Aday ${a.no} onaylandı, paketi sonraki koşu hazırlar.`);
function reddet(d) {
  const neden = prompt(`"${d.ad}" reddedilsin mi? İstersen nedenini yaz (boş bırakabilirsin).`);
  if (neden === null) return;
  eylemSonraki(d, "reddet", { neden }, `"${d.ad}" reddedildi.`);
}

// ---- görünümler: keşif ve yayın (#_kesif, #_yayin; şarkı kimliğinde "_" geçmez) ----
const kisaSayi = (n) => n == null ? "—" : n >= 1e9 ? `${(n / 1e9).toFixed(1)} mr` : n >= 1e6 ? `${(n / 1e6).toFixed(1)} mn`
  : n >= 1e3 ? `${Math.round(n / 1e3)} bin` : String(n);
const saatYazi = (sn) => sn >= 3600 ? `${Math.floor(sn / 3600)} sa ${Math.floor((sn % 3600) / 60)} dk` : `${Math.max(1, Math.ceil(sn / 60))} dk`;
const tarih = (iso) => iso ? new Date(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "short" }) : "—";

function kotaSatiri(k) {
  if (!k.bagli) return el("p", { class: "uyari" }, "Spotify anahtarı yok: keşif doğrulaması ve yayın takibi kapalı. Kurulum README'de.");
  if (k.kilit_sn) return el("p", { class: "uyari" }, `Spotify istek sınırı: ${saatYazi(k.kilit_sn)} sonra açılır. Ölçümler o zamana kadar bekler; bu sayfadaki kayıtlar son ölçümden.`);
  return el("p", { class: "ipucu kota" }, `Spotify bugün ${k.bugun}/${k.tavan} istek kullandı. Ölçümleri gece koşusu yapar; bu sayfa istek atmaz.`);
}

const SUZGEC = {
  oneri: { ad: "Önerilen", f: (x) => x.puan > 0 && !x.listede && !x.elendi,
    bos: "Şu an önerilecek aday yok. Gece koşusu keşfe devam ediyor; Tümü'nde elenenlerin nedenini görebilirsin." },
  listede: { ad: "Listede", f: (x) => x.listede, bos: "Keşiften listeye eklenmiş şarkı yok." },
  elenen: { ad: "Elenen", f: (x) => x.elendi && !x.listede, bos: "Elediğin aday yok." },
  hepsi: { ad: "Tümü", f: () => true, bos: "Keşif henüz çalışmadı: uv run yanki kesif" },
};
let suzgec = "oneri";

async function kesifGoster() {
  const ana = $("#ana");
  let d;
  try { d = await api("/api/kesif"); } catch (e) { ana.replaceChildren(el("p", { class: "ipucu" }, `Keşif açılamadı: ${e.message}`)); return; }
  // ilk açılışta öneri yoksa boş ekran yerine tüm kayıtlar (neden elendikleri görünsün)
  if (!kesifGoster.acildi && !d.adaylar.some(SUZGEC.oneri.f)) suzgec = "hepsi";
  kesifGoster.acildi = true;
  const ciz = () => {
    const gorunen = d.adaylar.filter(SUZGEC[suzgec].f);
    ana.replaceChildren(
      el("header", { class: "baslik" }, el("h1", {}, "Keşif"),
        el("span", { class: "sanatci" }, "Spotify'dan kalkmış, hâlâ aranan şarkılar")),
      kotaSatiri(d.kota),
      el("div", { class: "kesitler", role: "group", "aria-label": "Süzgeç" }, ...Object.entries(SUZGEC).map(([k, s]) =>
        el("button", { class: "kesit", type: "button", "aria-pressed": k === suzgec ? "true" : "false", onclick: () => { suzgec = k; ciz(); } },
          s.ad, el("span", { class: "kesit-zaman" }, String(d.adaylar.filter(s.f).length))))),
      gorunen.length ? el("ul", { class: "kayitlar" }, ...gorunen.map((x) => kesifSatiri(x, async (yeni) => {
        Object.assign(x, yeni); ciz(); gorunumSayilari();
      }))) : el("p", { class: "ipucu" }, SUZGEC[suzgec].bos));
  };
  ciz();
}

function kesifSatiri(x, guncelle) {
  const iyi = x.puan > 0 && !x.elendi;
  const pazar = x.bakilan_pazarlar?.length ? `${x.kapali_pazarlar.length}/${x.bakilan_pazarlar.length}` : "—";
  const dinle = x.youtube_id ? `https://www.youtube.com/watch?v=${encodeURIComponent(x.youtube_id)}`
    : `https://www.youtube.com/results?search_query=${encodeURIComponent(`${x.sanatci} ${x.ad}`)}`;
  const islem = async (yol, govde, basari) => {
    try { guncelle(await api(`/api/kesif/${x.kimlik}/${yol}`, govde)); bildir(basari); } catch (e) { bildir(e.message, true); }
  };
  return el("li", { class: "kayit" + (iyi || x.listede ? "" : " soluk") },
    el("div", { class: "kayit-ad" }, el("span", { class: "ad" }, x.ad), el("span", { class: "sanatci" }, x.sanatci)),
    el("div", { class: "olculer" },
      el("span", { class: "rozet " + (iyi ? "ok" : "no") }, x.elendi ? "elendi" : x.hal),
      el("span", { title: "YouTube'daki orijinal yüklemenin izlenmesi" }, "YouTube ", el("b", {}, kisaSayi(x.youtube_izlenme))),
      el("span", { title: "Aynı adla Spotify'da çalınabilen başka parça sayısı" }, "rakip ", el("b", {}, x.rakip_cover ?? "—")),
      el("span", { title: "Kapalı olduğu pazar / bakılan pazar" }, "pazar ", el("b", {}, pazar)),
      x.turler?.length ? el("span", { title: "Sanatçının Deezer türleri; hattın denemediği türdeki aday kendiliğinden listeye girmez" },
        "tür ", el("b", {}, x.turler[0])) : null),
    el("div", { class: "kayit-eylem" },
      el("a", { class: "dugme", href: dinle, target: "_blank", rel: "noopener" }, "Dinle"),
      // amber yalnız önerilende; boşluğu kapanmış (geri gelmiş) ya da düzenleme olan şarkı eklenemez
      x.listede ? el("span", { class: "rozet ok" }, "listede")
        : x.geri_geldi || x.hal === "düzenleme" ? null
        : el("button", { class: iyi ? "dugme ikincil" : "dugme", type: "button",
          onclick: () => islem("ekle", null, `"${x.ad}" listeye eklendi; adaylar sonraki gece koşusunda üretilir.`) },
          iyi ? "Listeye ekle" : "Yine de ekle"),
      x.listede ? null : el("button", { class: "dugme tehlike", type: "button",
        onclick: () => islem("ele", { elendi: !x.elendi }, x.elendi ? `"${x.ad}" yeniden aday.` : `"${x.ad}" elendi; gece koşusu onu listeye eklemez.`) },
        x.elendi ? "Geri al" : "Ele")));
}

async function yayinGoster() {
  const ana = $("#ana");
  let d;
  try { d = await api("/api/yayin"); } catch (e) { ana.replaceChildren(el("p", { class: "ipucu" }, `Yayın durumu açılamadı: ${e.message}`)); return; }
  const parcalar = [
    el("header", { class: "baslik" }, el("h1", {}, "Yayın"), el("span", { class: "sanatci" }, "Yüklenenler Spotify'da çıktı mı, adı arandığında kaçıncı")),
    kotaSatiri(d.kota),
  ];
  if (d.profiller.length > 1) parcalar.push(el("p", { class: "uyari", role: "alert" },
    `Sanatçı profili bölünmüş: parçalar ${d.profiller.length} ayrı Spotify profilinde. Dağıtımcıdan birleştirme iste.`));
  parcalar.push(d.sarkilar.length ? el("ul", { class: "kayitlar" }, ...d.sarkilar.map(yayinSatiri))
    : el("p", { class: "ipucu" }, "Henüz yüklenmiş şarkı yok. Paketi yükleyince: yanki yuklendi <kimlik>"));
  parcalar.push(takvimBolumu(d.takvim));
  if (d.olaylar?.length) parcalar.push(el("section", { class: "bolum", "aria-label": "Son bildirimler" },
    el("h2", { class: "bolum-baslik" }, "Son bildirimler"),
    el("ul", { class: "olaylar" }, ...d.olaylar.map((o) => el("li", {},
      el("span", { class: "olay-zaman" }, tarih(o.zaman)), el("b", {}, o.baslik), " ", el("span", { class: "olay-metin" }, o.metin))))));
  ana.replaceChildren(...parcalar.filter(Boolean));
}

// paketlenmiş şarkıların yükleme sırası (yanki/dagitim.py; ölçüm değil, durumdan hesap)
function takvimBolumu(t) {
  if (!t) return null;
  const ust = el("h2", { class: "bolum-baslik" }, "Yükleme sırası", el("span", { class: "g-sayi" }, t.sira.length ? String(t.sira.length) : ""));
  const not = t.hata ? el("p", { class: "uyari" }, `Takvim okunamadı: ${t.hata}`)
    : t.beklemede ? el("p", { class: "ipucu" }, `Takvim bekliyor: ${t.beklemede}. Tarihler o zamana kadar öneri.`) : null;
  const sira = t.sira.length ? el("ol", { class: "kayitlar" }, ...t.sira.map((x, i) => el("li", { class: "kayit kapakli" + (t.beklemede ? " soluk" : "") },
    kapakImg(x.kapak, "kapak-kucuk kapak-orta"),
    el("div", { class: "kayit-ad" }, el("a", { class: "ad", href: `#${x.kimlik}` }, x.ad), el("span", { class: "sanatci" }, x.sanatci)),
    el("div", { class: "olculer" },
      el("span", { class: "rozet " + (i === 0 && !t.beklemede ? "ok" : "") }, i === 0 ? "sıradaki" : `${i + 1}.`),
      el("span", {}, "yükle ", el("b", {}, tarih(x.yukleme))),
      el("span", {}, "yayın ", el("b", {}, tarih(x.yayin_tarihi))),
      x.kesif ? el("span", { class: "rozet ok", title: "Keşiften: Spotify'da kaldırılmış, hâlâ aranan şarkı" }, "keşif") : null),
    el("div", { class: "kayit-eylem" }))))
    : el("p", { class: "ipucu" }, "Kuyrukta paket yok. Onayladığın şarkılar paketlenince buraya girer.");
  const duzeltme = t.duzeltme?.length ? el("p", { class: "uyari" },
    `Dağıtımcının reddettiği, düzeltilmeyi bekleyen: ${t.duzeltme.join(", ")}. Düzeltip yanki paketle --yeniden deyince sıraya döner.`) : null;
  return el("section", { class: "bolum", "aria-label": "Yükleme sırası" }, ust, not, duzeltme, sira);
}

function yayinSatiri(s) {
  const son = s.son;
  const hal = !son ? ["ölçülmedi", ""] : son.kayip ? ["kayıp", "no"] : son.canli ? ["yayında", "ok"] : ["yayın bekliyor", ""];
  const siralar = Object.entries(son?.siralar || {});
  const dd = s.dagitim_durumu;
  return el("li", { class: "kayit kapakli" },
    kapakImg(s.kapak, "kapak-kucuk kapak-orta"),
    el("div", { class: "kayit-ad" }, el("a", { class: "ad", href: `#${s.kimlik}` }, s.ad), el("span", { class: "sanatci" }, s.sanatci)),
    el("div", { class: "olculer" },
      el("span", { class: "rozet " + hal[1] }, hal[0]),
      el("span", {}, DAGITIMCI[s.dagitimci] || s.dagitimci || "—", dd ? [" · ", el("b", {}, DAGITIM[dd] || dd)] : null),
      s.geri_cek ? el("span", { class: "rozet", title: "Geri çekilmesi istendi; inceleme bitince hat kaldırır ve şarkıyı yeniden sıraya alır" }, "geri çekilecek") : null,
      el("span", {}, "çıkış ", el("b", {}, tarih(s.yayin_tarihi))),
      el("span", {}, "son bakış ", el("b", {}, tarih(son?.zaman))),
      siralar.length ? el("span", { class: "siralar", title: `Şarkının adı arandığında ilk ${son.arama_limiti} sonuçtaki sıramız` },
        ...siralar.map(([m, n]) => el("span", { class: "sira" + (n && n <= 3 ? " iyi" : "") }, `${m} ${n ?? "—"}`))) : null),
    el("div", { class: "kayit-eylem" },
      son?.spotify_id ? el("a", { class: "dugme", href: `https://open.spotify.com/track/${son.spotify_id}`, target: "_blank", rel: "noopener" }, "Spotify'da aç") : null));
}

async function gorunumSayilari() {
  try {
    const [k, y, p] = await Promise.all([api("/api/kesif"), api("/api/yayin"), api("/api/pano")]);
    const bekleyen = p.kulak.length + p.hatada.length;
    $("#g-pano").textContent = bekleyen ? String(bekleyen) : "";
    $("#g-pano").classList.toggle("dikkat", bekleyen > 0);
    $("#g-pano").title = bekleyen ? "Senden beklenen" : "";
    $("#g-kesif").textContent = String(k.adaylar.filter(SUZGEC.oneri.f).length || "");
    $("#g-yayin").textContent = y.sarkilar.length ? `${y.sarkilar.filter((s) => s.son?.canli).length}/${y.sarkilar.length}` : "";
  } catch { /* sayılar ikincil: sunucu yoksa ana hata zaten bildirilir */ }
}

// ---- pano: hattın sinyal zinciri, senden beklenenler, dağıtım, kazanç, son gece koşusu ----
const saatDakika = (iso) => iso ? new Date(iso).toLocaleString("tr-TR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";
const ZINCIR_HEDEF = { "Keşif": "#_kesif", "Dinleme": null, "İnceleme": "#_yayin", "Yayında": "#_yayin" };

async function panoGoster() {
  const ana = $("#ana");
  let p;
  try { p = await api("/api/pano"); } catch (e) { ana.replaceChildren(el("p", { class: "ipucu" }, `Pano açılamadı: ${e.message}`)); return; }
  const ilkDinleme = (await api("/api/sarkilar").catch(() => [])).find((s) => s.asama === "uretildi");
  const zincir = el("section", { class: "cam zincir", "aria-label": "Hat" }, ...p.hat.map((d) => {
    const hedef = d.ad === "Dinleme" ? (ilkDinleme ? `#${ilkDinleme.kimlik}` : null) : ZINCIR_HEDEF[d.ad];
    const dikkat = d.ad === "Dinleme" && d.sayi > 0;
    return el(hedef ? "a" : "div", { class: "durak" + (dikkat ? " dikkat" : d.sayi ? " dolu" : ""), href: hedef || false,
      "aria-label": `${d.ad}: ${d.sayi} ${d.alt}` },
      el("span", { class: "durak-isik", "aria-hidden": "true" }),
      el("span", { class: "durak-sayi" + (d.sayi ? " gumus-yazi" : "") }, String(d.sayi)),
      el("span", { class: "durak-ad" }, d.ad), el("span", { class: "durak-alt" }, d.alt));
  }));

  const ayar = p.ayarlar || {};
  const ozet = [ayar.takvim_acik === false ? "yayın takvimi kapalı" : ayar.haftada ? `haftada ${ayar.haftada} yayın` : null,
    ayar.oto_onay ? `${ayar.oto_onay_saat} saatte karar yoksa kendiliğinden onay` : "onay sende"].filter(Boolean).join(" · ");

  ana.replaceChildren(
    el("header", { class: "pano-ust" }, el("h1", { class: "gumus-yazi" }, "Kontrol odası"), el("p", { class: "ipucu" }, ozet)),
    zincir,
    el("div", { class: "pano-izgara" },
      el("div", { class: "pano-sol" }, beklenenBolumu(p), dagitimBolumu(p.dagitim), takvimBolumu(p.takvim),
        p.olaylar?.length ? el("section", { class: "bolum", "aria-label": "Son bildirimler" },
          el("h2", { class: "bolum-baslik" }, "Son bildirimler"),
          el("ul", { class: "olaylar" }, ...p.olaylar.map((o) => el("li", {},
            el("span", { class: "olay-zaman" }, saatDakika(o.zaman)),
            el("span", {}, el("b", {}, o.baslik), " ", el("span", { class: "olay-metin" }, o.metin)))))) : null),
      el("div", { class: "pano-sag" }, kazancPaneli(), gecePaneli(p.gece), ayarPaneli(ayar, p.kota))));
}

function beklenenBolumu(p) {
  const satirlar = [
    ...p.kulak.map((s) => ({ s, rozet: ["dinlemen gerekiyor", "amber"], metin: s.neden })),
    ...p.hatada.map((s) => ({ s, rozet: ["hata", "no"], metin: s.hata })),
    ...p.yakinda.map((s) => ({ s, rozet: ["kendiliğinden onaylanacak", "gumus"], metin: saatDakika(s.zaman) })),
  ];
  return el("section", { class: "bolum", "aria-label": "Senden beklenen" },
    el("h2", { class: "bolum-baslik" }, "Senden beklenen", satirlar.length ? el("span", { class: "g-sayi dikkat" }, String(satirlar.length)) : null),
    satirlar.length ? el("ul", { class: "kayitlar" }, ...satirlar.map(({ s, rozet, metin }) => el("li", { class: "kayit kapakli" },
      kapakImg(s.kapak, "kapak-kucuk kapak-orta"),
      el("div", { class: "kayit-ad" }, el("a", { class: "ad", href: `#${s.kimlik}` }, s.ad), el("span", { class: "sanatci" }, s.sanatci)),
      el("div", { class: "olculer" }, el("span", { class: `rozet ${rozet[1]}` }, rozet[0]), el("span", {}, metin || "")),
      el("div", { class: "kayit-eylem" }, el("a", { class: "dugme ikincil", href: `#${s.kimlik}` }, "Aç")))))
      : el("p", { class: "bos-kutu" }, "Şu an senden beklenen bir şey yok. Hat kendi kendine çalışıyor."));
}

function dagitimBolumu(liste) {
  if (!liste?.length) return null;
  return el("section", { class: "bolum", "aria-label": "Dağıtımda" },
    el("h2", { class: "bolum-baslik" }, "Dağıtımda", el("span", { class: "g-sayi" }, String(liste.length))),
    el("ul", { class: "kayitlar" }, ...liste.map((s) => {
      const dd = s.dagitim_durumu, hal = s.geri_cek ? ["geri çekilecek", "gumus"] : s.canli ? ["Spotify'da", "ok"] : dd === "rejected" ? ["reddedildi", "no"]
        : dd === "approved" || dd === "live" ? [DAGITIM[dd], "ok"] : [DAGITIM[dd] || "incelemede", "gumus"];
      return el("li", { class: "kayit kapakli" },
        kapakImg(s.kapak, "kapak-kucuk kapak-orta"),
        el("div", { class: "kayit-ad" }, el("a", { class: "ad", href: `#${s.kimlik}` }, s.ad), el("span", { class: "sanatci" }, s.sanatci)),
        el("div", { class: "olculer" }, el("span", { class: `rozet ${hal[1]}` }, hal[0]),
          el("span", {}, DAGITIMCI[s.dagitimci] || s.dagitimci || "—"), el("span", {}, "çıkış ", el("b", {}, tarih(s.yayin_tarihi)))),
        el("div", { class: "kayit-eylem" }));
    })));
}

function kazancPaneli() {
  const kutu = el("section", { class: "cam yan-panel", "aria-label": "Kazanç" }, el("h2", {}, "Kazanç"),
    el("p", { class: "kazanc-alt" }, "Yükleniyor…"));
  const para = (n, birim) => new Intl.NumberFormat("tr-TR", { style: "currency", currency: birim || "GBP" }).format(n || 0);
  api("/api/kazanc").then((k) => {
    if (!k.bagli) { kutu.replaceChildren(el("h2", {}, "Kazanç"), el("p", { class: "kazanc-alt" }, "Tunearo anahtarı yok (.env).")); return; }
    const enCok = Math.max(...k.kaynaklar.map((x) => x.tutar), 0.01);
    kutu.replaceChildren(el("h2", {}, "Kazanç"),
      el("p", { class: "kazanc-toplam gumus-yazi" }, para(k.toplam, k.para)),
      el("p", { class: "kazanc-alt" }, `bu ay ${para(k.bu_ay, k.para)} · ${k.yayinlar.length} yayın · aylık raporla güncellenir`),
      k.kaynaklar.length ? el("ul", { class: "cubuklar" }, ...k.kaynaklar.slice(0, 6).map((x) => el("li", {},
        el("span", {}, x.kaynak), el("b", {}, para(x.tutar, k.para)),
        el("span", { class: "cubuk", "aria-hidden": "true" }, el("i", { style: `width:${Math.round((x.tutar / enCok) * 100)}%` })))))
        : el("p", { class: "ipucu", style: "margin:0;font-size:12px" }, "İlk rapor, parçalar mağazalarda dinlendikten sonraki ay gelir."));
  }).catch((e) => kutu.replaceChildren(el("h2", {}, "Kazanç"), el("p", { class: "kazanc-alt" }, e.message)));
  return kutu;
}

function gecePaneli(g) {
  const kutu = el("section", { class: "cam yan-panel", "aria-label": "Son gece koşusu" }, el("h2", {}, "Son gece koşusu"));
  if (!g) { kutu.append(el("p", { class: "kazanc-alt" }, "Henüz koşu yok.")); return kutu; }
  const sorun = !g.suruyor && (g.kod || g.sorunlu);
  const durum = g.suruyor ? `sürüyor · ${g.adim || "başlıyor"}` : sorun ? `sorunlu: ${g.sorunlu || `kod ${g.kod}`}` : "sorunsuz bitti";
  kutu.append(el("p", { class: "gece-satir" }, el("span", { class: "nokta" + (g.suruyor ? " suruyor" : sorun ? " sorun" : "") }), durum),
    el("p", { class: "kazanc-alt" }, `${saatDakika(g.bas)}${g.bit ? ` → ${new Date(g.bit).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}` : ""}`));
  return kutu;
}

function ayarPaneli(a, kota) {
  const satir = (ad, deger) => [el("dt", {}, ad), el("dd", {}, deger)];
  return el("section", { class: "cam yan-panel", "aria-label": "Otomasyon" }, el("h2", {}, "Otomasyon"),
    el("dl", { class: "ayar-listesi" },
      ...satir("Dağıtımcı", DAGITIMCI[a.dagitimci] || a.dagitimci || "—"),
      ...satir("Takvim", !a.takvim_acik ? "kapalı" : a.haftada >= 7 ? "açık · her gün" : `açık · haftada ${a.haftada}`),
      ...satir("Otomatik onay", a.oto_onay ? `${a.oto_onay_saat} sa` : "kapalı"),
      ...satir("Kapak", a.kapak === "pinterest" ? "Pinterest" : "üretilen"),
      ...satir("Spotify", !kota?.bagli ? "bağlı değil" : kota.kilit_sn ? `kilitli · ${saatYazi(kota.kilit_sn)}` : `${kota.bugun}/${kota.tavan} istek`)));
}

// ---- kuyruk ----
async function listeGoster(secili) {
  for (const a of document.querySelectorAll(".gorunumler a")) {
    if (a.dataset.g === secili) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  }
  const liste = await api("/api/sarkilar");
  $("#liste-bos").hidden = liste.length > 0;
  const dinlemede = liste.filter((s) => s.asama === "uretildi").length;
  $("#sayac").textContent = dinlemede ? `${dinlemede} şarkı dinlemede` : "";
  $("#liste").replaceChildren(...liste.map((s) => el("li", {},
    el("a", { href: `#${s.kimlik}`, "aria-current": s.kimlik === secili ? "page" : false },
      kapakImg(s.kapak),
      el("span", { class: "ad" }, s.ad),
      el("span", { class: "alt" }, s.sanatci, el("span", { class: "asama", "data-a": s.asama }, ASAMA[s.asama] || s.asama))))));
}

const GORUNUM = { _pano: panoGoster, _kesif: kesifGoster, _yayin: yayinGoster };
async function yenile(kimlik = decodeURIComponent(location.hash.slice(1)) || "_pano") {
  await listeGoster(kimlik);
  gorunumSayilari();
  if (GORUNUM[kimlik]) await GORUNUM[kimlik]();
  else await sarkiGoster(kimlik);
}
addEventListener("hashchange", () => { calan?.ses.pause(); yenile().then(() => $("#ana").focus()); });
yenile().catch((e) => bildir(`Sunucuya ulaşılamadı: ${e.message}`, true));
// arka planda ilerleyen aşamaları kuyrukta göster (oynatmayı bölmeden yalnız listeyi yeniler)
setInterval(() => listeGoster(decodeURIComponent(location.hash.slice(1)) || "_pano").catch(() => {}), 30000);
