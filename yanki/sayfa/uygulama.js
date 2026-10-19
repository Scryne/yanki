// Yanki dinleme odası. Derleme yok; sunucu: yanki/sunucu.py
const $ = (s, k = document) => k.querySelector(s);
const el = (etiket, ozellik = {}, ...cocuk) => {
  const e = document.createElement(etiket);
  for (const [k, v] of Object.entries(ozellik)) {
    if (k === "class") e.className = v;
    else if (k === "style" && typeof v === "object") Object.assign(e.style, v);
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) e.setAttribute(k, v === true ? "" : v);
  }
  for (const c of cocuk.flat()) if (c != null && c !== false) e.append(c);
  return e;
};
// replaceChildren boş değerleri "null" metni olarak ekler: koşullu parçalar (cond ? el : null) süzülür
const doldur = (e, ...c) => e.replaceChildren(...c.flat().filter((x) => x != null && x !== false));
const sure = (s) => { s = Math.max(0, s || 0); return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`; };
const aralik = (a, b) => `${sure(a)}–${sure(b)}`;
const virgul = (n, basamak) => n == null ? "—" : String(basamak == null ? n : Number(n).toFixed(basamak)).replace(".", ",");
// şarkı klasörü içindeki göreli yol (adaylar/1/aday.flac): her parça ayrı kodlanır, "#", "?" ya da boşluk adresi bölmez
const yolKodla = (yol) => String(yol).split("/").map(encodeURIComponent).join("/");
const css = (ad) => getComputedStyle(document.documentElement).getPropertyValue(ad).trim();
const azHareket = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const depo = {
  oku(k, varsayilan) { try { const v = localStorage.getItem(`yanki.${k}`); return v == null ? varsayilan : JSON.parse(v); } catch { return varsayilan; } },
  yaz(k, v) { try { localStorage.setItem(`yanki.${k}`, JSON.stringify(v)); } catch { /* gizli pencere: yalnız bu oturum */ } },
};

const ASAMA = {
  yeni: "yeni", hazir: "hazır", analiz: "üretimde", uretildi: "dinlemede", onarim: "onarım bekliyor",
  onaylandi: "onaylandı", paketlendi: "paketlendi", yuklendi: "yüklendi", yayinda: "yayında", hata: "hata", reddedildi: "reddedildi",
};
const KAPI = { parmak_izi: "parmak izi", dalga: "dalga", soz_wer: "söz", sure_fark: "süre", motor: "motor", birlestirme: "birleştirme" };
const KAPI_ACIKLAMA = {
  parmak_izi: "Orijinal kayda parmak izi benzerliği; eşiğin altında kalmalı (içerik tanıma)",
  dalga: "Orijinal kayda dalga benzerliği (300 Hz üstü); eşiğin altında kalmalı",
  soz_wer: "Sözün Whisper'la ölçülen hata oranı; eşik orijinal kaydın kendi hatasına göre",
  sure_fark: "Orijinalle süre farkı (sn)",
};
const DAGITIM = { draft: "taslak", pending: "incelemede", gonderildi: "incelemede", action_needed: "düzeltme istiyor", approved: "onaylandı", live: "mağazalarda", rejected: "reddedildi",
  takedown: "kaldırıldı", takedown_requested: "kaldırılıyor", taken_down: "kaldırıldı" };
const DAGITIMCI = { tunearo: "Tunearo", routenote: "RouteNote", distrokid: "DistroKid" };
const DIL = { en: "İngilizce", es: "İspanyolca", ko: "Korece", ja: "Japonca", tl: "Tagalogca", tr: "Türkçe", pt: "Portekizce",
  fr: "Fransızca", de: "Almanca", it: "İtalyanca", zh: "Çince", yue: "Kantonca", th: "Tayca", hi: "Hintçe", id: "Endonezce" };
const BOLUM = { Intro: "Giriş", Verse: "Kıta", "Pre-Chorus": "Ön nakarat", Chorus: "Nakarat", "Post-Chorus": "Nakarat sonu",
  Bridge: "Köprü", Instrumental: "Enstrümantal", Outro: "Çıkış" };
const bolumAdi = (ad) => { const [kok, no] = ad.split(/ (?=\d+$)/); return `${BOLUM[kok] || kok}${no ? ` ${no}` : ""}`; };
const AY = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
// eğitim adı "20261012-0808" → "12 Eki"
const loraTarihi = (ad) => { const m = /^(\d{4})(\d{2})(\d{2})/.exec(ad || ""); return m ? `${+m[3]} ${AY[+m[2] - 1]}` : ad; };

// kapak: sunucu adres verdiyse küçük resim, yoksa dalga işaretli boş kare (olmayan kapağa istek atılmaz)
function kapakImg(url, sinif = "kapak-kucuk", boyut = 96) {
  if (!url) return el("span", { class: `${sinif} bos`, "aria-hidden": "true" }, dalgaIsareti());
  return el("img", { class: sinif, src: `${url}&boyut=${boyut}`, alt: "", loading: "lazy", decoding: "async", width: 32, height: 32 });
}
function dalgaIsareti(boyut = 16) {
  const ns = "http://www.w3.org/2000/svg", svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 32 32"); svg.setAttribute("width", boyut); svg.setAttribute("height", boyut);
  const yol = document.createElementNS(ns, "path");
  yol.setAttribute("d", "M6 16h3M11 10v12M16 6v20M21 11v10M26 15v2"); yol.setAttribute("stroke", "currentColor");
  yol.setAttribute("stroke-width", "2.4"); yol.setAttribute("stroke-linecap", "round"); yol.setAttribute("fill", "none");
  svg.append(yol);
  return svg;
}

function bildir(mesaj, hata = false) {
  const b = $("#bildirim");
  b.textContent = mesaj; b.classList.toggle("hata", hata); b.classList.add("acik");
  clearTimeout(bildir.t); bildir.t = setTimeout(() => b.classList.remove("acik"), hata ? 7000 : 4500);
}

// gövde verilen her çağrı POST (boş gövde de: `{}`); verilmeyen GET
async function api(yol, govde) {
  const r = await fetch(yol, govde !== undefined && govde !== null ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(govde) } : {});
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    // 422: alan doğrulaması liste döner
    const ayrinti = Array.isArray(d.detail) ? `Geçersiz değer: ${d.detail.map((x) => x.loc?.at(-1)).join(", ")}` : d.detail;
    throw new Error(ayrinti || `${r.status}`);
  }
  return r.json();
}

// ---- tek ses: sayfada aynı anda yalnız bir kayıt çalar; çalanın zamanı sözleri yürütür ----
let calan = null; // { ses, dosya }
document.addEventListener("play", (e) => {
  if (!(e.target instanceof HTMLAudioElement)) return;
  for (const s of document.querySelectorAll("audio")) if (s !== e.target && !s.paused) s.pause();
  calan = { ses: e.target, dosya: e.target.dataset.dosya };
}, true);
document.addEventListener("timeupdate", (e) => { if (e.target === calan?.ses) sozYuru?.(e.target.currentTime); }, true);
let sozYuru = null; // şarkı ekranındaki söz rayının güncelleyicisi
// klavyeyle panoda gezinen birinin odağı 30 sn'lik tazelemede sayfanın başına düşmesin
// (yalnız klavye odağı: fareyle tıklanan özet ya da düğme tazelemeyi durdurmaz)
const anadaOdak = () => { const o = document.activeElement, ana = $("#ana"); return !!o && o !== ana && ana.contains(o) && o.matches(":focus-visible"); };
const sesCaliyor = () => !!calan && !calan.ses.paused && document.contains(calan.ses);

// ---- dalga şeridi ----
const seritler = new Map(); // dosya → Serit (şarkı ekranında; söz satırına tıklayınca o kayıtta oraya gidilir)
class Serit {
  constructor({ kimlik, dosya, secilebilir = false, vurgu = null, kucuk = false, etiket }) {
    this.kimlik = kimlik; this.dosya = dosya; this.secilebilir = secilebilir; this.vurgu = vurgu;
    this.secim = null; this.tepe = []; this.toplam = 0;
    this.ses = el("audio", { preload: "none", src: `/ses/${kimlik}/${yolKodla(dosya)}`, "data-dosya": dosya });
    this.tuval = el("canvas", { role: "img", "aria-label": `${etiket} dalga formu` + (secilebilir ? "; sürükleyerek aralık seç" : "") });
    this.kap = el("div", { class: "dalga-kap yukleniyor" + (kucuk ? " kucuk" : ""), tabindex: "0", "aria-label": `${etiket}: boşluk çal/durdur, oklar 5 sn` + (secilebilir ? ", Shift+ok seçimi genişletir, Esc temizler" : "") }, this.tuval);
    this.zaman = el("span", { class: "zaman" }, "0:00");
    this.secimYazi = el("span", { class: "secim", "aria-live": "polite" });
    this.calDugme = el("button", { class: "dugme cal", type: "button", onclick: () => this.cal() }, "Çal");
    this.ses.addEventListener("timeupdate", () => this.ciz());
    for (const [olay, yazi] of [["play", "Durdur"], ["pause", "Çal"], ["ended", "Çal"]])
      this.ses.addEventListener(olay, () => { this.calDugme.textContent = yazi; this.calDugme.setAttribute("aria-pressed", olay === "play" ? "true" : "false"); });
    this.kap.addEventListener("keydown", (e) => this.tus(e));
    this.fareBagla();
    new ResizeObserver(() => this.ciz()).observe(this.kap);
    if (!kucuk) seritler.set(dosya, this);
    this.yukle();
  }
  async yukle() {
    try { const d = await api(`/api/dalga/${this.kimlik}/${yolKodla(this.dosya)}`); this.tepe = d.tepe; this.toplam = d.sure; this.ciz(); }
    catch (e) { this.zaman.textContent = "dalga okunamadı"; }
    finally { this.kap.classList.remove("yukleniyor"); }
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
    this.secim = a == null ? null : [Math.max(0, a), Math.min(this.toplam || b, b)];
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
    if (bas != null) { this.ses.currentTime = Math.max(0, bas); this.dur = son; }
    if (this.ses.paused || bas != null) this.ses.play().catch((e) => bildir(`Çalınamadı: ${e.message}`, true));
    else this.ses.pause();
  }
  ciz() {
    const t = this.tuval, dpr = devicePixelRatio || 1, w = t.clientWidth, h = t.clientHeight;
    if (!w) return;
    if (t.width !== Math.round(w * dpr)) { t.width = Math.round(w * dpr); t.height = Math.round(h * dpr); }
    const c = t.getContext("2d"); c.setTransform(dpr, 0, 0, dpr, 0, 0); c.clearRect(0, 0, w, h);
    const x = (s) => (s / (this.toplam || 1)) * w;
    for (const [a, b] of [this.vurgu || [], this.secim || []]) {
      if (a == null) continue;
      c.fillStyle = css("--primary-zayif"); c.fillRect(x(a), 0, x(b) - x(a), h);
      c.strokeStyle = css("--primary"); c.lineWidth = 1; c.strokeRect(x(a) + .5, .5, x(b) - x(a) - 1, h - 1);
    }
    const an = this.ses.currentTime || 0, n = this.tepe.length, orta = h / 2;
    const calinan = css("--dalga-calinan"), bos = css("--dalga");
    for (let i = 0; i < n; i++) {
      const px = (i / n) * w, y = Math.max(1, this.tepe[i] * (h / 2 - 4));
      c.fillStyle = (i / n) * this.toplam <= an ? calinan : bos;
      c.fillRect(px, orta - y, Math.max(1, w / n - 0.5), y * 2);
    }
    if (an > 0 || !this.ses.paused) { c.fillStyle = css("--oynatma"); c.fillRect(x(an), 0, 2, h); }
    this.zaman.textContent = `${sure(an)} / ${sure(this.toplam)}`;
    if (this.dur != null && an >= this.dur) { this.ses.pause(); this.dur = null; }
  }
}

// ---- şarkı ekranı ----
let acikSarki = null; // { kimlik, guncel }: arka planda değişirse (yeni adaylar) sayfa kendini yeniler
async function sarkiGoster(kimlik) {
  const ana = $("#ana");
  let d;
  try { d = await api(`/api/sarki/${kimlik}`); } catch (e) { doldur(ana, bosEkran("Şarkı açılamadı", e.message)); return; }
  acikSarki = { kimlik, guncel: d.guncel, asama: d.asama };
  if (!["uretildi", "onarim"].includes(d.asama)) d.oneri = null; // karar verilmiş şarkıda öneri gürültü
  seritler.clear(); sozYuru = null; panelTus = null;
  const duzenlenebilir = ["uretildi", "onarim"].includes(d.asama);
  const ust = [sarkiBasi(d)];
  if (d.hata) ust.push(el("p", { class: "uyari", role: "alert" }, d.hata));
  if (d.onay_engeli) ust.push(el("p", { class: "not" },
    el("b", {}, "Karar senin. "), `Bu şarkı kendiliğinden onaylanmaz (${d.onay_engeli}); sen karar verene kadar yayına girmez.`));
  if (d.otomatik_onay) ust.push(el("p", { class: "not bekleyen" },
    `Karar vermezsen ${new Date(d.otomatik_onay.zaman).toLocaleString("tr-TR", { weekday: "long", hour: "2-digit", minute: "2-digit" })}`
    + ` aday ${d.otomatik_onay.aday} kendiliğinden onaylanır. Onaylamak, onarım istemek ya da reddetmek bunu iptal eder.`));
  if (d.asama === "analiz") ust.push(el("p", { class: "not canli" }, el("span", { class: "nabiz", "aria-hidden": "true" }),
    d.adaylar.length ? "Yeni adaylar üretim sırasında. Gelince bu sayfa kendiliğinden yenilenir; o zamana kadar mevcut adaylar yalnız dinlenebilir."
      : "Adaylar üretim sırasında. Gelince bu sayfa kendiliğinden yenilenir."));

  const ana_ = [karsilastirma(d, duzenlenebilir)];
  if (["uretildi", "hata"].includes(d.asama) && d.analiz?.stil) ana_.push(stilKutu(d));
  if (d.kaynak?.dosya) ana_.push(seritKutu({ kimlik, dosya: d.kaynak.dosya, baslik: "Orijinal", alt: "karşılaştırma için" }));
  const guncelStil = d.analiz?.stil || "";
  const yeniler = d.adaylar.filter((a) => a.tarif), eskiler = d.adaylar.filter((a) => !a.tarif);
  // yeni hatla üretilenler üstte: eski adaylar başlığın altında, sönük
  for (const a of yeniler.length ? yeniler : eskiler) ana_.push(adayKutu(d, a, duzenlenebilir, guncelStil));
  if (yeniler.length && eskiler.length) {
    ana_.push(el("h2", { class: "ara-baslik" }, "Önceki hatla üretilenler", el("span", { class: "g-sayi" }, String(eskiler.length))));
    for (const a of eskiler) ana_.push(adayKutu(d, a, duzenlenebilir, guncelStil, true));
  }
  if (!d.adaylar.length && !d.hata && d.asama !== "analiz") ana_.push(el("p", { class: "ipucu" }, "Adaylar henüz üretilmedi."));

  const ray = sozRayi(d);
  const parcalar = [...ust, el("div", { class: "sarki-izgara" + (ray ? "" : " tek") }, el("div", { class: "sarki-ana" }, ...ana_.filter(Boolean)), ray)];
  if (!["reddedildi", "yuklendi", "yayinda"].includes(d.asama)) {
    parcalar.push(el("div", { class: "alt-cubuk" },
      el("span", { class: "ipucu" }, d.asama === "onaylandi" ? `Onaylanan: aday ${d.secilen}. Paket sonraki koşuda hazırlanır.`
        : duzenlenebilir ? ["Dalgada sürükle: aralık seç · ", el("kbd", {}, "?"), " kısayollar"] : ["", el("kbd", {}, "?"), " kısayollar"]),
      el("span", { class: "bosluk" }),
      el("button", { class: "dugme tehlike", type: "button", onclick: () => reddet(d) }, "Şarkıyı reddet")));
  } else if (d.asama === "reddedildi") {
    parcalar.push(el("div", { class: "alt-cubuk" },
      el("span", { class: "ipucu" }, "Bu şarkıyı reddettin. Sesleri gece temizliğinde silinir; o zamana kadar geri alırsan reddetmeden önceki aşamasına döner."),
      el("span", { class: "bosluk" }),
      el("button", { class: "dugme ikincil", type: "button",
        onclick: () => eylem(d, "geri-al", {}, `"${d.ad}" yeniden listede, reddetmeden önceki aşamasında.`) }, "Reddi geri al")));
  }
  doldur(ana, ...parcalar.filter(Boolean));
}

function sarkiBasi(d) {
  const k = d.kunye || {}, an = d.analiz || {}, y = d.yukleme;
  const cip = (ad, deger, title) => deger ? el("span", { class: "cip", title: title || false }, el("span", { class: "cip-ad" }, ad), deger) : null;
  const betim = an.betim ? el("details", { class: "betim" },
    el("summary", {}, el("span", { class: "betim-etiket" }, "Betim"), el("span", { class: "betim-ozet" }, an.betim)),
    el("p", {}, an.betim),
    an.stil && an.stil !== an.betim ? el("p", { class: "ipucu" }, el("b", {}, "Üretime giden stil: "), an.stil) : null,
    el("p", { class: "ipucu kucuk-ipucu" }, "ACE-Step'in betimleyicisi orijinal kaydı dinleyip yazdı; stil tanımı buradan kurulur."))
    : an.stil ? el("p", { class: "stil-satiri" }, el("span", { class: "betim-etiket" }, "Stil"), an.stil) : null;
  return el("header", { class: "sarki-ust" },
    d.kapak ? el("img", { class: "fon", src: `${d.kapak}&boyut=96`, alt: "", "aria-hidden": "true" }) : null,
    kapakKutu(d),
    el("div", { class: "sarki-kimlik" },
      el("p", { class: "ust-satir" }, el("span", { class: "asama", "data-a": d.asama }, ASAMA[d.asama] || d.asama),
        d.analiz?.stil_kaynak === "betim" ? el("span", { class: "rozet gumus", title: "Stil şarkının kendi betiminden" }, "betimli") : null),
      el("h1", {}, d.ad),
      el("p", { class: "sanatci-buyuk" }, d.sanatci),
      el("div", { class: "cipler" },
        cip("dil", DIL[an.dil] || an.dil),
        cip("süre", d.kaynak?.sure_sn ? sure(d.kaynak.sure_sn) : null),
        cip("tempo", an.bpm ? `${an.bpm} BPM` : null), cip("ton", an.ton),
        cip("söz kaynağı", d.soz?.kaynak === "lrclib" ? "LRCLIB" : d.soz?.kaynak),
        cip("yazarlar", (k.yazarlar || []).join(", ") || null),
        cip("orijinal", d.kaynak?.baslik ? "YouTube" : null, d.kaynak?.baslik)),
      y ? el("div", { class: "cipler" },
        cip("dağıtım", DAGITIMCI[y.dagitimci] || y.dagitimci), cip("durum", DAGITIM[y.dagitim_durumu] || y.dagitim_durumu),
        cip("çıkış", tarih(y.yayin_tarihi)), cip("ISRC", y.isrc), cip("UPC", y.upc)) : null,
      betim));
}

function kapakKutu(d) {
  const degisir = ["uretildi", "onarim", "onaylandi", "paketlendi"].includes(d.asama) && !d.kapak_elle;
  const gorsel = d.kapak ? el("img", { class: "kapak-buyuk", src: `${d.kapak}&boyut=480`, alt: `${d.ad} kapağı`, width: 168, height: 168 })
    : el("div", { class: "kapak-buyuk kapak-yok" }, dalgaIsareti(28), el("span", {}, degisir ? "Kapak paketlemede seçilir" : "Kapak yok"));
  const bilgi = d.kapak_elle ? "elle seçilen (kapak_ozel.jpg)"
    : d.kapak_bilgi?.aciklama ? `Pinterest: ${d.kapak_bilgi.aciklama}` : null;
  const dugme = degisir ? el("button", { class: "dugme ikincil kucuk", type: "button",
    onclick: (e) => kapakDegistir(d, e.currentTarget) }, d.kapak ? "Başka kapak" : "Kapak bul") : null;
  return el("div", { class: "kapak-kutu" }, gorsel, bilgi && el("p", { class: "ipucu kapak-bilgi", title: bilgi }, bilgi), dugme);
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

// ---- sözler: bölüm yapısıyla, çalan kayıtla birlikte akar; satıra tıklayınca oraya gidilir ----
function sozRayi(d) {
  const bolumler = (d.bolumler || []).filter((b) => b.satirlar.length || b.bas != null);
  if (!bolumler.length) return null;
  const satirlar = []; // { t, son, dugme }
  const icerik = bolumler.map((b) => {
    const dugmeler = b.satirlar.map(([t, metin]) => {
      const dugme = el("button", { class: "soz-satir", type: "button", disabled: t == null,
        title: t == null ? false : "Tıkla: buradan çal · Shift+tık: bu satırı seç (onarım için)" },
        el("span", { class: "soz-zaman" }, t == null ? "" : sure(t)), el("span", { class: "soz-metin" }, metin));
      if (t != null) {
        const kayit = { t, dugme };
        dugme.addEventListener("click", (e) => sozTik(kayit, e.shiftKey));
        satirlar.push(kayit);
      }
      return dugme;
    });
    const enst = !b.satirlar.length;
    return el("section", { class: "soz-bolum" + (enst ? " enst" : ""), "data-bolum": b.ad.split(" ")[0] },
      el("h3", {}, el("span", { class: "bolum-cip" }, bolumAdi(b.ad)), b.bas != null ? el("span", { class: "soz-zaman" }, sure(b.bas)) : null),
      ...dugmeler);
  });
  satirlar.sort((a, b) => a.t - b.t);
  satirlar.forEach((s, i) => { s.son = satirlar[i + 1]?.t ?? s.t + 6; });
  const liste = el("div", { class: "soz-liste" }, ...icerik);
  let aktif = null, uzerinde = false;
  liste.addEventListener("pointerenter", () => { uzerinde = true; });
  liste.addEventListener("pointerleave", () => { uzerinde = false; });
  sozYuru = (t) => {
    let i = satirlar.length - 1;
    while (i >= 0 && satirlar[i].t > t + 0.15) i--;
    const yeni = i >= 0 && t < satirlar[i].son + 1 ? satirlar[i] : null;
    if (yeni === aktif) return;
    aktif?.dugme.classList.remove("simdi");
    aktif = yeni;
    if (!aktif) return;
    aktif.dugme.classList.add("simdi");
    if (!uzerinde) { // kendi kutusu içinde kaydır (sayfayı oynatmaz)
      const hedef = aktif.dugme.offsetTop - liste.clientHeight / 2 + aktif.dugme.offsetHeight / 2;
      liste.scrollTo({ top: Math.max(0, hedef), behavior: azHareket() ? "auto" : "smooth" });
    }
  };
  const sozTik = (s, sec) => {
    // çalan kaydın şeridinde (hızlı karşılaştırmadan çalıyorsa aynı dosyanın şeridinde); çalan yoksa önerilen aday
    const oneri = d.adaylar.find((a) => a.no === d.oneri?.aday) || d.adaylar.find((a) => a.gecti && a.dosya);
    const dosya = calan && document.contains(calan.ses) ? calan.dosya : oneri?.dosya || d.kaynak?.dosya;
    const serit = seritler.get(dosya);
    if (!serit) return;
    if (sec) {
      if (!serit.secilebilir) { bildir("Bu kayıtta aralık seçilemez: yalnız dinlemedeki, kapıdan geçmiş adayda."); return; }
      serit.secimKoy(s.t - 0.3, s.son);
      serit.kap.scrollIntoView({ block: "center", behavior: azHareket() ? "auto" : "smooth" });
      bildir(`Seçildi: ${aralik(s.t - 0.3, s.son)}. Onarmak için adayın altında "Bu aralığı onar".`);
      return;
    }
    serit.cal(s.t - 0.4);
  };
  return el("aside", { class: "soz-ray", "aria-label": "Sözler" },
    el("div", { class: "ray-ust" }, el("h2", {}, "Sözler"), el("span", { class: "ipucu kucuk-ipucu" }, "çalan kayıtla akar")),
    liste,
    el("p", { class: "ipucu kucuk-ipucu ray-alt" }, "Tık: oradan çal · ", el("kbd", {}, "Shift"), "+tık: satırı seç"));
}

// ---- hızlı karşılaştırma: aynı kesit, adaylar arasında konumu koruyarak geçiş ----
// Tam dinleme şarkı başı ~15 dk; burada 3 kesit × aday. Sıra söz WER'ine göre, hattın önerisi işaretli.
let panelTus = null;
addEventListener("keydown", (e) => {
  if (e.ctrlKey || e.altKey || e.metaKey) return;
  if (e.target.closest?.("input, textarea, select, dialog")) return;
  if (e.key === "?") { e.preventDefault(); kisayolPenceresi(); return; }
  if (e.key === "/") { e.preventDefault(); $("#ara")?.focus(); return; }
  if (!panelTus || e.target.closest?.("summary, .dalga-kap")) return;
  // odaktaki düğmenin, bağlantının, anahtarın kendi tıklaması (Enter başka bir düğmede onay vermesin)
  if ((e.key === " " || e.key === "Enter") && e.target.closest?.("button, a, [role=switch], summary")) return;
  panelTus(e);
});

function karsilastirma(d, duzenlenebilir) {
  const wer = (a) => a.kapilar?.soz_wer?.deger ?? Infinity;
  const yeniVar = d.adaylar.some((a) => a.tarif);
  const adaylar = d.adaylar.filter((a) => a.gecti && a.dosya && (!yeniVar || a.tarif)).sort((x, y) => wer(x) - wer(y));
  if (!d.kesitler?.length || !adaylar.length) return null;
  const izler = [
    ...(d.kaynak?.dosya ? [{ tus: "0", ad: "Orijinal", dosya: d.kaynak.dosya }] : []),
    ...adaylar.map((a) => ({ tus: a.no <= 9 ? String(a.no) : null, ad: `Aday ${a.no}`, dosya: a.dosya, aday: a })),
  ];
  let k = 0, aktif = null, sirayla = false;
  const kesit = () => d.kesitler[k];

  const zaman = el("span", { class: "zaman" }, "0:00 / 0:00");
  const cubuk = el("span", { class: "ilerleme-dolu" });
  const calDugme = el("button", { class: "dugme cal", type: "button", onclick: () => calDurdur() }, "Çal");
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
    aktif = iz;
    const kx = kesit();
    iz.ses.currentTime = Math.min(kx.son - 0.25, Math.max(kx.bas, konum));
    iz.ses.play().catch((e) => bildir(`Çalınamadı: ${e.message}`, true));
    goster();
  };
  const gec = (iz) => oynat(iz, aktif ? aktif.ses.currentTime : kesit().bas);
  const ilkAday = () => izler.find((iz) => iz.aday?.no === d.oneri?.aday) || izler.find((iz) => iz.aday) || izler[0];
  const calDurdur = () => {
    if (!aktif) return oynat(ilkAday(), kesit().bas);
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
    iz.ses = el("audio", { preload: "none", src: `/ses/${d.kimlik}/${yolKodla(iz.dosya)}`, "data-dosya": iz.dosya });
    iz.ses.addEventListener("timeupdate", () => {
      if (iz !== aktif) return;
      if (iz.ses.currentTime >= kesit().son) sonaGeldi(iz); else goster();
    });
    for (const olay of ["play", "pause"]) iz.ses.addEventListener(olay, () => iz === aktif && goster());
    const w = iz.aday ? wer(iz.aday) : null;
    const onerilen = iz.aday && iz.aday.no === d.oneri?.aday;
    iz.dugme = el("button", { class: "iz" + (iz.aday ? "" : " orijinal") + (onerilen ? " onerilen" : ""), type: "button", "aria-pressed": "false",
      onclick: () => { sirayla = false; gec(iz); } },
      el("kbd", {}, iz.tus ?? "·"),
      el("span", { class: "iz-ad" }, iz.ad, onerilen ? el("span", { class: "oneri-isaret", title: `Hattın önerisi: ${d.oneri.neden}` }, "öneri") : null),
      iz.aday ? el("span", { class: "iz-deger" }, Number.isFinite(w) ? `söz ${virgul(w)}` : "söz —", ` · tohum ${iz.aday.tohum}`)
        : el("span", { class: "iz-deger" }, "karşılaştırma için"));
  }

  panelTus = (e) => {
    const iz = izler.find((x) => x.tus === e.key);
    if (iz) { e.preventDefault(); sirayla = false; gec(iz); }
    else if (e.key === " ") { e.preventDefault(); calDurdur(); }
    else if (e.key === "ArrowRight" || e.key === "ArrowLeft") { e.preventDefault(); kesitSec(k + (e.key === "ArrowRight" ? 1 : -1)); }
    else if (e.key === "s" || e.key === "S") { e.preventDefault(); siraylaBasla(); }
    else if ((e.key === "Enter") && aktif?.aday && !onayDugme.disabled) { e.preventDefault(); onayVer(d, aktif.aday); }
  };

  const kutu = el("section", { class: "serit karsilastir", "aria-label": "Hızlı karşılaştırma" },
    el("div", { class: "serit-ust" }, el("h2", {}, "Hızlı karşılaştırma"),
      el("span", { class: "ipucu kucuk-ipucu" }, yeniVar ? "Yeni hatla üretilen adaylar; söz hatasına göre sıralı, geçişte konum korunur"
        : "Söz hatasına göre sıralı; geçişte konum korunur")),
    el("div", { class: "kesitler", role: "group", "aria-label": "Kesit" }, kesitDugmeleri),
    el("ol", { class: "izler" }, izler.map((iz) => el("li", {}, iz.dugme))),
    el("div", { class: "ilerleme", "aria-hidden": "true" }, cubuk),
    el("div", { class: "serit-alt" }, calDugme, siraDugme, zaman, el("span", { class: "bosluk" }), duzenlenebilir ? onayDugme : null),
    d.oneri ? el("p", { class: "ipucu kucuk-ipucu oneri-not" }, el("b", {}, `Hattın önerisi aday ${d.oneri.aday}`),
      ` (${d.oneri.neden}). Söz hatası en düşük iki aday arasından ACE-Step söz hizalaması yüksek olan; senin 21 seçiminin 14'ünü tuttu. Karar kulağının.`) : null,
    izler.map((iz) => iz.ses));
  goster();
  return kutu;
}

function seritKutu({ kimlik, dosya, baslik, alt }) {
  const s = new Serit({ kimlik, dosya, etiket: baslik });
  return el("section", { class: "serit orijinal-serit", "aria-label": baslik },
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

// kapı ölçerleri: hepsinde düşük iyi; dolgu değerin eşiğe oranı (eşiği geçen tam dolar, mercan)
function olcerler(kapilar) {
  return Object.entries(kapilar || {}).map(([ad, v]) => {
    if (v.deger == null || v.esik == null) return el("span", { class: `rozet ${v.gecti ? "ok" : "no"}`, title: v.hata || false },
      `${KAPI[ad] || ad} ${v.gecti ? "✓" : "✗"}`);
    const oran = Math.min(1, Math.max(0.04, v.deger / v.esik));
    return el("span", { class: `olcer ${v.gecti ? "ok" : "no"}`, title: `${KAPI_ACIKLAMA[ad] || KAPI[ad] || ad}: ${virgul(v.deger)} (eşik ${virgul(v.esik)})` },
      el("span", { class: "olcer-ad" }, KAPI[ad] || ad),
      el("span", { class: "olcer-cubuk", "aria-hidden": "true" }, el("i", { style: { transform: `scaleX(${oran})` } })),
      el("span", { class: "olcer-deger" }, virgul(v.deger), v.gecti ? " ✓" : " ✗"));
  });
}

function tarifCipi(a, karisik) {
  if (!a.tarif && !karisik) return null;
  if (!a.tarif) return el("span", { class: "rozet", title: "Bu aday kendi LoRA'mız ve tarif kaydı gelmeden önce üretildi" }, "önceki hat");
  const t = a.tarif;
  return el("span", { class: "rozet tarif", title: `${t.model}${t.lora ? ` + LoRA ${t.lora} (ölçek ${virgul(t.lora_olcek)})` : ""}; stil ${t.stil_kaynak === "betim" ? "betimden" : t.stil_kaynak || "listeden"}; ${t.tarih?.replace("T", " ")}` },
    t.lora ? `LoRA · ${loraTarihi(t.lora)}` : "temel model");
}

function adayKutu(d, a, duzenlenebilir, guncelStil, eski = false) {
  const baslik = `Aday ${a.no}`;
  const onerilen = a.no === d.oneri?.aday;
  const ust = el("div", { class: "serit-ust" }, el("h2", {}, baslik),
    onerilen ? el("span", { class: "rozet oneri", title: d.oneri.neden }, "hattın önerisi") : null,
    el("span", { class: "tohum" }, `tohum ${a.tohum}`), tarifCipi(a, d.adaylar.some((x) => x.tarif)),
    d.secilen === a.no ? el("span", { class: "rozet ok" }, "onaylanan") : null,
    el("span", { class: "bosluk" }),
    el("span", { class: "olcerler" }, ...olcerler(a.kapilar)));
  if (!a.dosya) return el("section", { class: "serit dusen" }, ust);
  const s = new Serit({ kimlik: d.kimlik, dosya: a.dosya, secilebilir: duzenlenebilir && a.gecti, etiket: baslik });
  const onar = el("button", { class: "dugme punch", type: "button", disabled: true, onclick: () => onarimIste(d, a, s.secim) }, "Bu aralığı onar");
  const secimCal = el("button", { class: "dugme", type: "button", disabled: true, onclick: () => s.cal(Math.max(0, s.secim[0] - 3), s.secim[1] + 3) }, "Seçimi çal");
  s.onSecim = (sec) => { onar.disabled = !sec; secimCal.disabled = !sec; };
  const bekleyen = a.onarimlar.some((o) => o.durum === "bekliyor");
  const onayla = el("button", { class: "dugme birincil", type: "button", disabled: !(duzenlenebilir && a.gecti) || bekleyen, onclick: () => onayVer(d, a) }, "Bu adayı onayla");
  const farkliStil = a.stil && a.stil !== guncelStil;
  const kutu = el("section", { class: "serit aday" + (a.gecti ? "" : " dusen") + (onerilen ? " onerilen" : "") + (eski ? " eski" : ""), "aria-label": baslik },
    ust,
    farkliStil ? el("details", { class: "aday-stil" }, el("summary", {}, "Farklı stille üretildi"), el("p", {}, a.stil)) : null,
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
    el("div", { class: "serit-alt" }, bolgeCal, s.zaman, el("span", { class: "olcerler" }, ...olcerler(o.kapilar)), el("span", { class: "bosluk" }), kabul, s.ses));
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

// ---- pencereler (yerel <dialog>: odak tuzağı, Esc ve arka plan tarayıcıdan) ----
function pencere(baslik, govde, eylemler, sinif = "") {
  const dlg = el("dialog", { class: `pencere ${sinif}`, "aria-labelledby": "pencere-baslik" },
    el("h2", { id: "pencere-baslik" }, baslik), ...govde, el("div", { class: "pencere-eylem" }, ...eylemler));
  dlg.addEventListener("close", () => dlg.remove());
  dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); }); // arka plana tık
  document.body.append(dlg);
  dlg.showModal();
  return dlg;
}

// RouteNote'ta ne gördüğünü kaydeden tek tıklar (gönderildi / taslakta) şarkıyı aşamadan aşamaya taşır; yanlış tık
// takibi ve takvimi bozar, odadan geri alınmaz: önce ne olacağı söylenir
function gonderimSonucuSor(ad, gonderildi, isle) {
  const dlg = pencere(gonderildi ? `"${ad}" gönderildi diye kaydedilsin mi?` : `"${ad}" taslakta diye kaydedilsin mi?`, [
    el("p", { class: "ipucu" }, gonderildi
      ? "Yalnız RouteNote panelinde yayın incelemede görünüyorsa. Şarkı \"incelemede\"ye geçer, takip Spotify'da çıkmasını bekler; hat bu yayını bir daha göndermez."
      : "Panelde yayın hâlâ taslaksa. Hat onu yine göndermez: panelden gönder ya da sil (sonra yanki routenote taslak-silindi)."),
  ], [
    el("button", { class: "dugme", type: "button", onclick: () => dlg.close() }, "Vazgeç"),
    el("button", { class: "dugme punch", type: "button", onclick: () => { dlg.close(); isle(); } }, gonderildi ? "Gönderildi, kaydet" : "Taslakta, kaydet"),
  ]);
}

const RET_NEDENLERI = ["vokal kötü", "beat/düzenleme kötü", "söz anlaşılmıyor", "orijinale fazla benziyor", "tür uymuyor", "kaynak ses kötü"];
function reddet(d) {
  const metin = el("textarea", { id: "ret-neden", rows: 3, maxlength: 300, placeholder: "İsteğe bağlı; hattın neyi kaçırdığı sonraki ayarlara girer" });
  const cipler = RET_NEDENLERI.map((n) => el("button", { class: "kesit", type: "button", "aria-pressed": "false", onclick: (e) => {
    const b = e.currentTarget, secili = b.getAttribute("aria-pressed") !== "true";
    b.setAttribute("aria-pressed", secili ? "true" : "false");
    const parcalar = metin.value.split(/;\s*/).filter(Boolean).filter((x) => x !== n);
    metin.value = (secili ? [...parcalar, n] : parcalar).join("; ");
  } }, n));
  const dlg = pencere(`"${d.ad}" reddedilsin mi?`, [
    el("p", { class: "ipucu" }, "Şarkı listeden çıkar ve yayına girmez. Adaylar silinmez; istersen sonra geri alabilirsin."),
    el("div", { class: "kesitler", role: "group", "aria-label": "Hazır nedenler" }, cipler),
    el("label", { for: "ret-neden", class: "gizli" }, "Ret nedeni"), metin,
  ], [
    el("button", { class: "dugme", type: "button", onclick: () => dlg.close() }, "Vazgeç"),
    el("button", { class: "dugme tehlike dolu", type: "button", onclick: () => { dlg.close(); eylemSonraki(d, "reddet", { neden: metin.value.trim() }, `"${d.ad}" reddedildi.`); } }, "Şarkıyı reddet"),
  ]);
  cipler[0]?.focus();
}

function kisayolPenceresi() {
  if ($("dialog.kisayollar")) return;
  const satir = (tuslar, metin) => el("li", {}, el("span", { class: "tuslar" }, ...tuslar.map((t) => el("kbd", {}, t))), el("span", {}, metin));
  const dlg = pencere("Kısayollar", [
    el("h3", {}, "Hızlı karşılaştırma"),
    el("ul", { class: "kisayol-listesi" },
      satir(["0"], "orijinal kayıt"), satir(["1", "…", "9"], "aday (konum korunur)"), satir(["Boşluk"], "çal / durdur"),
      satir(["←", "→"], "önceki / sonraki kesit"), satir(["S"], "adayları sırayla çal"), satir(["Enter"], "çalan adayı onayla")),
    el("h3", {}, "Dalga şeridi (odaktayken)"),
    el("ul", { class: "kisayol-listesi" },
      satir(["Boşluk"], "çal / durdur"), satir(["←", "→"], "5 sn geri / ileri"), satir(["Shift", "←→"], "seçimi 0,5 sn genişlet"),
      satir(["Esc"], "seçimi temizle")),
    el("h3", {}, "Genel"),
    el("ul", { class: "kisayol-listesi" }, satir(["/"], "şarkı ara"), satir(["?"], "bu pencere")),
  ], [el("button", { class: "dugme ikincil", type: "button", onclick: () => dlg.close() }, "Kapat")], "kisayollar");
}

// ---- görünümler: keşif ve yayın (#_kesif, #_yayin; şarkı kimliğinde "_" geçmez) ----
const kisaSayi = (n) => n == null ? "—" : n >= 1e9 ? `${virgul(n / 1e9, 1)} mr` : n >= 1e6 ? `${virgul(n / 1e6, 1)} mn`
  : n >= 1e3 ? `${Math.round(n / 1e3)} bin` : String(Math.round(n));
const saatYazi = (sn) => sn >= 3600 ? `${Math.floor(sn / 3600)} sa ${Math.floor((sn % 3600) / 60)} dk` : `${Math.max(1, Math.ceil(sn / 60))} dk`;
const tarih = (iso) => iso ? new Date(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "short" }) : "—";
const bosEkran = (baslik, metin) => el("div", { class: "bos-ekran" }, dalgaIsareti(32), el("h2", {}, baslik), metin ? el("p", { class: "ipucu" }, metin) : null);

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
let suzgec = "oneri", turSuzgec = null;

async function kesifGoster() {
  const ana = $("#ana");
  let d;
  try { d = await api("/api/kesif"); } catch (e) { doldur(ana, bosEkran("Keşif açılamadı", e.message)); return; }
  // ilk açılışta öneri yoksa boş ekran yerine tüm kayıtlar (neden elendikleri görünsün)
  if (!kesifGoster.acildi && !d.adaylar.some(SUZGEC.oneri.f)) suzgec = "hepsi";
  kesifGoster.acildi = true;
  const tur = (x) => (x.turler?.[0] || "").toLocaleLowerCase("tr");
  const ciz = () => {
    const suzulen = d.adaylar.filter(SUZGEC[suzgec].f);
    const turler = Object.entries(suzulen.reduce((s, x) => { const t = tur(x); if (t) s[t] = (s[t] || 0) + 1; return s; }, {}))
      .sort((a, b) => b[1] - a[1]).slice(0, 10);
    if (turSuzgec && !turler.some(([t]) => t === turSuzgec)) turSuzgec = null;
    const gorunen = suzulen.filter((x) => !turSuzgec || tur(x) === turSuzgec);
    doldur(ana, 
      el("header", { class: "sayfa-ust" }, el("h1", {}, "Keşif"),
        el("p", { class: "ipucu" }, "Spotify'dan kalkmış ama hâlâ aranan şarkılar. Puan = talep (YouTube ya da eski Spotify dinlenmesi) × kapalı pazar oranı ÷ (1 + rakip cover).")),
      kotaSatiri(d.kota),
      el("div", { class: "kesitler", role: "group", "aria-label": "Süzgeç" }, ...Object.entries(SUZGEC).map(([k, s]) =>
        el("button", { class: "kesit", type: "button", "aria-pressed": k === suzgec ? "true" : "false", onclick: () => { suzgec = k; ciz(); } },
          s.ad, el("span", { class: "kesit-zaman" }, String(d.adaylar.filter(s.f).length))))),
      turler.length > 1 ? el("div", { class: "kesitler tur-suzgec", role: "group", "aria-label": "Tür" },
        el("span", { class: "ipucu kucuk-ipucu" }, "Tür:"),
        ...turler.map(([t, n]) => el("button", { class: "kesit kucuk", type: "button", "aria-pressed": t === turSuzgec ? "true" : "false",
          onclick: () => { turSuzgec = turSuzgec === t ? null : t; ciz(); } }, t, el("span", { class: "kesit-zaman" }, String(n))))) : null,
      gorunen.length ? el("ul", { class: "kayitlar" }, ...gorunen.map((x) => kesifSatiri(x, async (yeni) => {
        Object.assign(x, yeni); ciz(); gorunumSayilari();
      }))) : el("p", { class: "bos-kutu" }, SUZGEC[suzgec].bos));
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
      iyi ? el("span", { title: "Keşif puanı" }, "puan ", el("b", {}, kisaSayi(x.puan))) : null,
      el("span", { title: "YouTube'daki orijinal yüklemenin izlenmesi" }, "YouTube ", el("b", {}, kisaSayi(x.youtube_izlenme))),
      el("span", { title: "Aynı adla Spotify'da çalınabilen başka parça sayısı" }, "rakip ", el("b", {}, x.rakip_cover ?? "—")),
      el("span", { title: "Kapalı olduğu pazar / bakılan pazar" }, "pazar ", el("b", {}, pazar)),
      x.turler?.length ? el("span", { title: "Sanatçının Deezer türleri; hattın denemediği türdeki aday kendiliğinden listeye girmez" },
        "tür ", el("b", {}, x.turler[0])) : null),
    el("div", { class: "kayit-eylem" },
      el("a", { class: "dugme", href: dinle, target: "_blank", rel: "noopener" }, "Dinle"),
      // boşluğu kapanmış (geri gelmiş) ya da düzenleme olan şarkı eklenemez
      x.listede ? el("span", { class: "rozet ok" }, "listede")
        : x.geri_geldi || x.hal === "düzenleme" ? null
        : el("button", { class: iyi ? "dugme ikincil" : "dugme", type: "button",
          onclick: () => islem("ekle", {}, `"${x.ad}" listeye eklendi; adaylar sonraki gece koşusunda üretilir.`) },
          iyi ? "Listeye ekle" : "Yine de ekle"),
      x.listede ? null : el("button", { class: "dugme tehlike", type: "button",
        onclick: () => islem("ele", { elendi: !x.elendi }, x.elendi ? `"${x.ad}" yeniden aday.` : `"${x.ad}" elendi; gece koşusu onu listeye eklemez.`) },
        x.elendi ? "Geri al" : "Ele")));
}

async function yayinGoster() {
  const ana = $("#ana");
  let d, p = null;
  try { [d, p] = await Promise.all([api("/api/yayin"), api("/api/performans").catch(() => null)]); }
  catch (e) { doldur(ana, bosEkran("Yayın durumu açılamadı", e.message)); return; }
  const canli = d.sarkilar.filter((s) => s.son?.canli).length;
  const parcalar = [
    el("header", { class: "sayfa-ust" }, el("h1", {}, "Yayın"),
      el("p", { class: "ipucu" }, `${d.sarkilar.length} yüklenen şarkı, ${canli} tanesi Spotify'da. Adı arandığında kaçıncı çıktığımız pazar pazar.`)),
    kotaSatiri(d.kota),
  ];
  if (d.profiller.length > 1) parcalar.push(el("p", { class: "uyari", role: "alert" },
    `Sanatçı profili bölünmüş: parçalar ${d.profiller.length} ayrı Spotify profilinde. Dağıtımcıdan birleştirme iste.`));
  parcalar.push(d.sarkilar.length ? el("ul", { class: "kayitlar" }, ...d.sarkilar.map(yayinSatiri))
    : el("p", { class: "bos-kutu" }, "Henüz yüklenmiş şarkı yok. Paketler Sanatçı görünümünden RouteNote'a gönderilir."));
  if (p) parcalar.push(performansBolumu(p));
  parcalar.push(takvimBolumu(d.takvim));
  if (d.olaylar?.length) parcalar.push(olayBolumu(d.olaylar));
  doldur(ana, ...parcalar.filter(Boolean));
}

// yayından sonra: dinlenme (takip), kazanç (aylık RouteNote raporu), türlere göre keşif çarpanı, RouteNote e-postaları
// (yanki/performans.py, kazanc.py, eposta.py; RouteNote paneli botla okunmaz)
const EPOSTA_SINIF = { onay: ["onay", "ok"], aksiyon: ["düzeltme", "amber"], red: ["red", "no"] };
function performansBolumu(p) {
  const t = p.turler, k = p.kazanc;
  const olculen = p.sarkilar.filter((s) => s.dinlenme != null);
  const toplam = olculen.reduce((n, s) => n + s.dinlenme, 0);
  const turler = Object.entries(t.turler).sort((a, b) => b[1].gunluk - a[1].gunluk);
  const para = Object.entries(k.toplam || {}).sort((a, b) => b[1] - a[1])[0];
  const tutar = (n, birim) => { try { return new Intl.NumberFormat("tr-TR", { style: "currency", currency: birim }).format(n); } catch { return `${virgul(n, 2)} ${birim}`; } };
  return el("section", { class: "bolum", "aria-label": "Performans" },
    el("h2", { class: "bolum-baslik" }, "Performans"),
    el("p", { class: "ipucu bolum-not" }, "Hangi türde şarkılarımız dinleniyor: keşif o türdeki adayları öne alır. Dinlenme her gece Spotify uygulamasından, kazanç RouteNote'un aylık raporundan."),
    el("div", { class: "sonuc-olcu cam" },
      el("div", {}, el("span", { class: "olcu-sayi" + (toplam ? " gumus-yazi" : "") }, kisaSayi(toplam)), el("span", { class: "olcu-ad" }, `toplam dinlenme · ${olculen.length} şarkı ölçüldü`)),
      el("div", {}, el("span", { class: "olcu-sayi" + (para ? " gumus-yazi" : "") }, para ? tutar(para[1], para[0].length === 3 ? para[0] : "USD") : "—"),
        el("span", { class: "olcu-ad" }, k.dosya ? `kazanç · ${k.aylar.length} ay rapor${k.eslesmeyen ? ` · ${k.eslesmeyen} satır eşleşmedi` : ""}` : "kazanç · rapor yok"))),
    turler.length ? el("ul", { class: "kayitlar" }, ...turler.map(([ad, v]) => el("li", { class: "kayit" },
      el("div", { class: "kayit-ad" }, el("span", { class: "ad" }, ad), el("span", { class: "sanatci" }, `${v.sarki} şarkı`)),
      el("div", { class: "olculer" }, el("span", {}, "günlük ", el("b", {}, kisaSayi(v.gunluk))),
        el("span", { class: "rozet " + (v.carpan > 1 ? "ok" : v.carpan < 1 ? "no" : ""), title: "Bu türdeki keşif adayının puanı bununla çarpılır" }, `keşif × ${virgul(v.carpan, 2)}`)),
      el("div", { class: "kayit-eylem" }))))
      : null,
    t.yeterli ? null : el("p", { class: "ipucu kucuk-ipucu" }, `Keşif çarpanı için en az 4 şarkı, her biri 14 gün yayında ölçülmeli (şimdi ${t.sarki}); o zamana kadar bütün türler × 1.`),
    k.dosya ? null : el("p", { class: "ipucu kucuk-ipucu" }, "Kazanç: ayda bir RouteNote → Performance → Reports'tan Monthly Sales Report'u indir, girdi/kazanc/ klasörüne koy. Rapor ay sonundan ~45 gün sonra gelir."),
    k.hatalar?.length ? el("p", { class: "uyari" }, `Okunamayan rapor: ${k.hatalar.join(" · ")}`) : null,
    p.eposta.ayarli
      ? el("div", {}, el("h3", { class: "ara-baslik" }, "RouteNote e-postaları"),
        p.eposta.son.length ? el("ul", { class: "olaylar" }, ...p.eposta.son.map((e) => el("li", {},
          el("span", { class: "olay-zaman" }, tarih(e.tarih)),
          el("span", {}, EPOSTA_SINIF[e.sinif] ? el("span", { class: `rozet ${EPOSTA_SINIF[e.sinif][1]}` }, EPOSTA_SINIF[e.sinif][0]) : el("span", { class: "rozet" }, "?"),
            " ", el("b", {}, e.konu), e.eylem && e.eylem !== "bildirildi" ? el("span", { class: "olay-metin" }, ` · ${e.eylem}`) : null))))
          : el("p", { class: "ipucu kucuk-ipucu" }, "Henüz RouteNote e-postası gelmedi. Onay, düzeltme isteği ve red geldikçe burada ve bildirimde görünür."))
      : el("p", { class: "not" }, "RouteNote e-postaları okunmuyor: .env'ye EPOSTA_KULLANICI ve EPOSTA_SIFRE (Gmail uygulama şifresi) eklenince onay ve red kendiliğinden işlenir."));
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
      el("span", {}, "yayın ", el("b", {}, x.yayin_tarihi ? tarih(x.yayin_tarihi) : "onaylanınca")),
      x.kesif ? el("span", { class: "rozet ok", title: "Keşiften: Spotify'da kaldırılmış, hâlâ aranan şarkı" }, "keşif") : null,
      x.dusus ? el("span", { class: "rozet no", title: x.dusus.hata }, `yükleme ${x.dusus.sayi} kez düştü`) : null,
      x.dusus ? el("span", { class: "duz" }, x.dusus.sonraki ? `sonraki deneme ${saatDakika(x.dusus.sonraki)}` : "sonraki koşuda denenecek") : null),
    el("div", { class: "kayit-eylem" }, x.dusus?.sonraki ? el("button", { class: "dugme ikincil kucuk", type: "button",
      title: "Bekleme süresini sil: sonraki koşu (en geç 30 dk) yeniden dener",
      onclick: async () => { try { bildir((await api(`/api/takvim/${x.kimlik}/yeniden-dene`, {})).mesaj); } catch (e) { bildir(e.message, true); } yenile(); } }, "Şimdi yeniden dene") : null))))
    : el("p", { class: "bos-kutu" }, "Kuyrukta paket yok. Onayladığın şarkılar paketlenince buraya girer.");
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
      el("span", {}, "çıkış ", el("b", {}, s.yayin_tarihi ? tarih(s.yayin_tarihi) : "onaylanınca")),
      s.dinlenme != null ? el("span", { title: "Spotify sayacı (takip her gece Spotify uygulamasından okur)" }, "dinlenme ", el("b", {}, kisaSayi(s.dinlenme))) : null,
      s.gunluk != null ? el("span", { title: "Son 28 günün ortalama günlük dinlenmesi" }, "günlük ", el("b", {}, kisaSayi(s.gunluk))) : null,
      el("span", {}, "son bakış ", el("b", {}, tarih(son?.zaman))),
      siralar.length ? el("span", { class: "siralar", title: `Şarkının adı arandığında ilk ${son.arama_limiti} sonuçtaki sıramız` },
        ...siralar.map(([m, n]) => el("span", { class: "sira" + (n && n <= 3 ? " iyi" : "") }, `${m} ${n ?? "—"}`))) : null),
    el("div", { class: "kayit-eylem" },
      son?.spotify_id ? el("a", { class: "dugme", href: `https://open.spotify.com/track/${son.spotify_id}`, target: "_blank", rel: "noopener" }, "Spotify'da aç") : null));
}

// bildirimler: metin iki satırda kesilir, tıklayınca açılır
function olayBolumu(olaylar, tamZaman = false) {
  return el("section", { class: "bolum", "aria-label": "Son bildirimler" },
    el("h2", { class: "bolum-baslik" }, "Son bildirimler"),
    el("ul", { class: "olaylar" }, ...olaylar.map((o) => {
      const metin = el("span", { class: "olay-metin" }, o.metin);
      return el("li", {},
        el("span", { class: "olay-zaman" }, tamZaman ? saatDakika(o.zaman) : tarih(o.zaman)),
        el("button", { class: "olay-govde", type: "button", "aria-expanded": "false", onclick: (e) => {
          const b = e.currentTarget, acik = b.getAttribute("aria-expanded") !== "true";
          b.setAttribute("aria-expanded", acik ? "true" : "false");
        } }, el("b", {}, o.baslik), " ", metin));
    })));
}

async function gorunumSayilari() {
  try {
    const [k, y, p, ku] = await Promise.all([api("/api/kesif"), api("/api/yayin"), api("/api/pano"), api("/api/kulak")]);
    const kalan = ku.reduce((n, x) => n + x.ozet.toplam - x.ozet.oylanan, 0);
    $("#g-kulak").textContent = kalan ? String(kalan) : "";
    $("#g-kulak").classList.toggle("dikkat", kalan > 0);
    $("#g-kulak").closest("li").hidden = !kalan; // karşılaştırma yalnız dinlenecek kayıt varken menüde
    const bekleyen = p.kulak.length + p.hatada.length + (p.takvim?.yazarsiz?.length || 0);
    $("#g-pano").textContent = bekleyen ? String(bekleyen) : "";
    $("#g-pano").classList.toggle("dikkat", bekleyen > 0);
    $("#g-pano").title = bekleyen ? "Senden beklenen" : "";
    $("#g-kesif").textContent = String(k.adaylar.filter(SUZGEC.oneri.f).length || "");
    $("#g-yayin").textContent = y.sarkilar.length ? `${y.sarkilar.filter((s) => s.son?.canli).length}/${y.sarkilar.length}` : "";
    simdiDurum(p.simdi);
    const sn = await api("/api/sanatci");
    const hazir = sn.katalog.filter((x) => x.hal === "taslak_hazir").length;
    $("#g-sanatci").textContent = hazir ? String(hazir) : "";
    $("#g-sanatci").title = hazir ? "Gönderime hazır taslak" : "";
  } catch { /* sayılar ikincil: sunucu yoksa ana hata zaten bildirilir */ }
}

// kenar çubuğundaki canlı durum: koşu sürüyor mu, kiralık GPU açık mı
function simdiDurum(s) {
  const yer = $("#simdi");
  if (!yer || !s) return;
  if (!s.suruyor && !s.pod) { doldur(yer, el("span", { class: "nokta" }), "Hat boşta"); yer.dataset.d = "bos"; return; }
  yer.dataset.d = "suruyor";
  doldur(yer, el("span", { class: "nabiz", "aria-hidden": "true" }),
    s.pod ? `Kiralık GPU'da üretim · ${s.pod.dakika} dk` : "Koşu sürüyor");
}

// ---- karşılaştırma: deneme çıktılarının kör kulak testi (yanki/kulak.py) ----
// Kollar şarkıdan şarkıya karışık sırayla A/B/C; hangisinin hangisi olduğu oy verilince açılır. Geçişte konum korunur.
async function kulakGoster() {
  const ana = $("#ana");
  let setler;
  try { setler = await api("/api/kulak"); } catch (e) { doldur(ana, bosEkran("Karşılaştırma açılamadı", e.message)); return; }
  acikSarki = null;
  setler = setler.filter((s) => s.sarkilar.length); // kayıtları silinmiş set (oylar kulak.json'da kalır)
  if (!setler.length) { doldur(ana, bosEkran("Karşılaştırılacak kayıt yok", "Yeni bir deneme çıkınca burada ve menüde görünür.")); return; }
  const ozetler = new Map();
  const ozetCiz = (s) => {
    const o = s.ozet, yer = ozetler.get(s.kimlik);
    const oran = o.toplam ? o.oylanan / o.toplam : 0;
    const sayim = Object.entries(o.sayim).filter(([, n]) => n).map(([k, n]) =>
      el("span", { class: "rozet" + (k === "hepsi_kotu" ? " no" : k in o.kollar && /yeni/.test(o.kollar[k]) ? " tarif" : "") },
        `${o.kollar[k] || { fark_yok: "fark yok", hepsi_kotu: "hepsi kötü" }[k]} ${n}`));
    doldur(yer, 
      el("div", { class: "butce-ust" }, el("span", {}, `${o.oylanan}/${o.toplam} şarkı dinlendi`),
        o.yayinlanir ? el("b", {}, `${o.yayinlanir} yayınlanabilir`) : null),
      el("span", { class: "cubuk", "aria-hidden": "true" }, el("i", { style: { transform: `scaleX(${oran})` } })),
      sayim.length ? el("div", { class: "kulak-sayim" }, el("span", { class: "ipucu kucuk-ipucu" }, "En iyi seçilen:"), ...sayim) : null);
  };
  const bolumler = setler.map((s) => {
    const ozet = el("div", { class: "butce kulak-ozet" });
    ozetler.set(s.kimlik, ozet);
    ozetCiz(s);
    const guncelle = (yeni) => {
      const ys = yeni.find((x) => x.kimlik === s.kimlik);
      if (ys) { Object.assign(s, ys); ozetCiz(s); }
      gorunumSayilari();
      return ys;
    };
    return el("section", { class: "bolum", "aria-label": s.ad },
      el("h2", { class: "bolum-baslik" }, s.ad), el("p", { class: "ipucu kucuk-ipucu kulak-aciklama" }, s.aciklama), ozet,
      el("ol", { class: "kulak-liste" }, ...s.sarkilar.map((x) => el("li", {}, kulakKarti(s, x, guncelle)))));
  });
  doldur(ana, 
    el("header", { class: "sayfa-ust" }, el("h1", {}, "Karşılaştırma"),
      el("p", { class: "ipucu" }, "Kör test: her şarkının kayıtları A, B, C diye karışık sırayla gelir; hangisinin eski, hangisinin yeni model olduğu sen seçince açılır. Senin seçimlerin bir sonraki eğitimin ve tarifin yönünü belirler.")),
    el("p", { class: "ipucu kucuk-ipucu kisayol" }, "Kartın içindeyken: ", el("kbd", {}, "0"), " orijinal · ", el("kbd", {}, "1"), el("kbd", {}, "2"), el("kbd", {}, "3"),
      " A/B/C (konum korunur) · ", el("kbd", {}, "Boşluk"), " çal/durdur · ", el("kbd", {}, "←"), el("kbd", {}, "→"), " 5 sn"),
    ...bolumler);
}

function kulakKarti(s, x, guncelle) {
  const izler = [...(x.orijinal ? [{ kol: "orijinal", harf: "O", tus: "0" }] : []),
    ...x.kollar.map((k, i) => ({ ...k, tus: String(i + 1) }))];
  let aktif = null;
  const zaman = el("span", { class: "zaman" }, "0:00 / 0:00");
  const ilerleme = el("input", { class: "kulak-ilerleme", type: "range", min: 0, max: 1000, value: 0, step: 1, "aria-label": `${x.ad} konum` });
  const calDugme = el("button", { class: "dugme cal", type: "button", onclick: () => calDurdur() }, "Çal");
  const goster = () => {
    const ses = aktif?.ses, t = ses?.currentTime || 0, sure_ = ses?.duration || 0;
    if (document.activeElement !== ilerleme) ilerleme.value = sure_ ? Math.round((t / sure_) * 1000) : 0;
    zaman.textContent = `${sure(t)} / ${sure(sure_)}`;
    calDugme.textContent = ses && !ses.paused ? "Durdur" : "Çal";
    for (const iz of izler) iz.dugme.setAttribute("aria-pressed", iz === aktif ? "true" : "false");
  };
  const gec = (iz) => {
    const konum = aktif ? aktif.ses.currentTime : 0, caliyordu = aktif && !aktif.ses.paused;
    if (aktif && aktif !== iz) aktif.ses.pause();
    aktif = iz;
    const d = iz.ses.duration;
    iz.ses.currentTime = Number.isFinite(d) ? Math.min(konum, d - 0.25) : konum;
    if (caliyordu || iz.ses.paused) iz.ses.play().catch((e) => bildir(`Çalınamadı: ${e.message}`, true));
    goster();
  };
  const calDurdur = () => {
    if (!aktif) return gec(izler.find((iz) => iz.kol !== "orijinal") || izler[0]);
    if (aktif.ses.paused) aktif.ses.play().catch((e) => bildir(`Çalınamadı: ${e.message}`, true)); else aktif.ses.pause();
  };
  for (const iz of izler) {
    iz.ses = el("audio", { preload: "none", src: `/kulak-ses/${s.kimlik}/${x.kimlik}/${encodeURIComponent(iz.kol)}`, "data-dosya": `${s.kimlik}/${x.kimlik}/${iz.kol}` });
    for (const olay of ["timeupdate", "play", "pause", "loadedmetadata", "ended"]) iz.ses.addEventListener(olay, () => iz === aktif && goster());
    iz.etiket = el("span", { class: "iz-ad" });
    iz.dugme = el("button", { class: "iz kulak-iz" + (iz.kol === "orijinal" ? " orijinal" : ""), type: "button", "aria-pressed": "false", onclick: () => gec(iz) },
      el("kbd", {}, iz.tus), iz.etiket);
  }
  ilerleme.addEventListener("input", () => {
    if (!aktif) gec(izler.find((iz) => iz.kol !== "orijinal") || izler[0]);
    const d = aktif.ses.duration;
    if (d) aktif.ses.currentTime = (ilerleme.value / 1000) * d;
  });
  const atla = (sn) => { if (aktif) { aktif.ses.currentTime = Math.max(0, aktif.ses.currentTime + sn); goster(); } };

  // oy alanı: oy verilince kolların adı açılır
  const oyAlani = el("div", { class: "kulak-oy" });
  const notKutusu = el("input", { class: "kulak-not", type: "text", maxlength: 500, placeholder: "Not (isteğe bağlı): ör. vokal metalik, nakarat düz", value: x.oy?.not || "",
    "aria-label": `${x.ad} için not` });
  const gonder = async (govde, basari) => {
    try {
      const ys = guncelle(await api(`/api/kulak/${s.kimlik}/${x.kimlik}`, govde));
      const yeni = ys?.sarkilar.find((y) => y.kimlik === x.kimlik);
      if (yeni) { Object.assign(x, yeni); x.kollar.forEach((k, i) => Object.assign(izler.find((iz) => iz.kol === k.kol), k)); ciz(); }
      if (basari) bildir(basari);
    } catch (e) { bildir(e.message, true); }
  };
  notKutusu.addEventListener("change", () => gonder({ not: notKutusu.value }, "Not kaydedildi."));
  const ciz = () => {
    const oy = x.oy || {};
    for (const iz of izler) doldur(iz.etiket, iz.kol === "orijinal" ? "Orijinal" : iz.harf,
      iz.ad ? el("span", { class: "kulak-acik" + (/yeni/.test(iz.ad) ? " yeni" : "") }, iz.ad) : null,
      oy.en_iyi === iz.kol ? el("span", { class: "rozet oneri" }, "seçtiğin") : null);
    const secenek = (deger, yazi, sinif = "") => el("button", { class: `kesit kucuk ${sinif}`, type: "button", "aria-pressed": oy.en_iyi === deger ? "true" : "false",
      onclick: () => gonder({ en_iyi: deger }, null) }, yazi);
    const kollar = x.kollar.map((k) => secenek(k.kol, `${k.harf} daha iyi`));
    doldur(oyAlani, 
      el("div", { class: "kesitler", role: "group", "aria-label": "Hangisi daha iyi" }, el("span", { class: "ipucu kucuk-ipucu" }, "Hangisi daha iyi?"),
        ...kollar, secenek("fark_yok", "Fark yok"), secenek("hepsi_kotu", x.kollar.length > 2 ? "Hepsi kötü" : "İkisi de kötü", "kotu")),
      oy.en_iyi && !["fark_yok", "hepsi_kotu"].includes(oy.en_iyi) ? el("div", { class: "kesitler", role: "group", "aria-label": "Yayınlanır mı" },
        el("span", { class: "ipucu kucuk-ipucu" }, "Seçtiğin yayınlanabilir mi?"),
        el("button", { class: "kesit kucuk", type: "button", "aria-pressed": oy.yayinlanir === true ? "true" : "false", onclick: () => gonder({ yayinlanir: true }, null) }, "Evet"),
        el("button", { class: "kesit kucuk", type: "button", "aria-pressed": oy.yayinlanir === false ? "true" : "false", onclick: () => gonder({ yayinlanir: false }, null) }, "Hayır")) : null,
      notKutusu);
    kart.classList.toggle("oylandi", !!oy.en_iyi);
  };

  const kart = el("article", { class: "serit kulak-kart", tabindex: "-1", "aria-label": `${x.sanatci} — ${x.ad}` },
    el("div", { class: "serit-ust" }, el("h3", { class: "kulak-ad" }, x.ad), el("span", { class: "tohum" }, x.sanatci),
      x.tur ? el("span", { class: "rozet gumus" }, x.tur) : null),
    el("div", { class: "kulak-izler" }, ...izler.map((iz) => iz.dugme)),
    el("div", { class: "serit-alt" }, calDugme,
      el("button", { class: "dugme kucuk", type: "button", onclick: () => atla(-10), "aria-label": "10 saniye geri" }, "−10"),
      ilerleme,
      el("button", { class: "dugme kucuk", type: "button", onclick: () => atla(10), "aria-label": "10 saniye ileri" }, "+10"), zaman),
    oyAlani, izler.map((iz) => iz.ses));
  kart.addEventListener("keydown", (e) => {
    if (e.ctrlKey || e.altKey || e.metaKey || e.target.closest("input")) return;
    const iz = izler.find((z) => z.tus === e.key);
    if (iz) { e.preventDefault(); gec(iz); }
    else if (e.key === " " && !e.target.closest("button")) { e.preventDefault(); calDurdur(); }
    else if (e.key === "ArrowRight" || e.key === "ArrowLeft") { if (e.target === ilerleme) return; e.preventDefault(); atla(e.key === "ArrowRight" ? 5 : -5); }
  });
  ciz(); goster();
  return kart;
}

// ---- pano: hattın sinyal zinciri, şu an, senden beklenenler, dağıtım, kazanç, tarif ----
const saatDakika = (iso) => iso ? new Date(iso).toLocaleString("tr-TR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";
const ZINCIR_HEDEF = { "Keşif": "#_kesif", "Dinleme": null, "İnceleme": "#_yayin", "Yayında": "#_yayin" };

async function panoGoster() {
  const ana = $("#ana");
  let p;
  try { p = await api("/api/pano"); } catch (e) { doldur(ana, bosEkran("Pano açılamadı", e.message)); return; }
  acikSarki = null;
  const ilkDinleme = (await api("/api/sarkilar").catch(() => [])).find((s) => s.asama === "uretildi");
  const zincir = el("section", { class: "cam zincir", "aria-label": "Hat" }, ...p.hat.map((d) => {
    const hedef = d.ad === "Dinleme" ? (ilkDinleme ? `#${ilkDinleme.kimlik}` : null) : ZINCIR_HEDEF[d.ad];
    const dikkat = d.ad === "Dinleme" && d.sayi > 0;
    const canli = d.ad === "Üretim" && p.simdi?.suruyor;
    return el(hedef ? "a" : "div", { class: "durak" + (dikkat ? " dikkat" : d.sayi ? " dolu" : "") + (canli ? " canli" : ""), href: hedef || false,
      "aria-label": `${d.ad}: ${d.sayi} ${d.alt}${canli ? ", şu an üretiliyor" : ""}` },
      el("span", { class: "durak-isik", "aria-hidden": "true" }),
      el("span", { class: "durak-sayi" + (d.sayi ? " gumus-yazi" : "") }, String(d.sayi)),
      el("span", { class: "durak-ad" }, d.ad), el("span", { class: "durak-alt" }, canli ? "üretiliyor" : d.alt));
  }));

  const ayar = p.ayarlar || {};
  const ozet = [ayar.uretim_acik === false ? "üretim duraklatıldı" : null,
    !ayar.dagitimci ? "dağıtımcı seçilmedi: paketler bekler" : ayar.takvim_acik === false ? "yayın takvimi kapalı" : ayar.haftada === 0 ? "sırası gelen her paket hemen yüklenir" : ayar.haftada ? `haftada ${ayar.haftada} yayın` : null,
    ayar.oto_onay ? `${ayar.oto_onay_saat} saatte karar yoksa kendiliğinden onay` : "onay sende"].filter(Boolean).join(" · ");
  const saat = new Date().getHours();
  const selam = saat < 6 ? "İyi geceler" : saat < 12 ? "Günaydın" : saat < 18 ? "İyi günler" : "İyi akşamlar";

  doldur(ana, 
    el("header", { class: "pano-ust" },
      el("div", {}, el("p", { class: "ust-satir ipucu" }, `${selam}, Scryne`), el("h1", { class: "gumus-yazi" }, "Kontrol odası")),
      el("p", { class: "ipucu" }, ozet)),
    zincir,
    simdiBolumu(p.simdi),
    el("div", { class: "pano-izgara" },
      el("div", { class: "pano-sol" }, beklenenBolumu(p), dagitimBolumu(p.dagitim), takvimBolumu(p.takvim),
        p.olaylar?.length ? olayBolumu(p.olaylar, true) : null),
      el("div", { class: "pano-sag" }, kazancPaneli(), tarifPaneli(ayar), gecePaneli(p.gece), ayarPaneli(ayar, p.kota))));
}

function simdiBolumu(s) {
  if (!s || (!s.suruyor && !s.pod && !s.uretimde?.length)) return null;
  const durumYazi = s.pod ? `Kiralık GPU açık · ${s.pod.dakika} dk` : s.suruyor ? "Koşu sürüyor"
    : s.uretim_acik === false ? "Üretim duraklatıldı; sırada bekliyor" : s.otomatik_kapali ? "Sırada; otomatik koşu kapalı"
    : s.engel ? "Kiralık GPU açılamıyor; sırada bekliyor (Senden beklenen)" : "Sırada, sonraki koşuyu bekliyor";
  const bekliyor = (s.uretim_acik === false || !!s.engel) && !s.suruyor && !s.pod;
  return el("section", { class: "simdi-serit" + (s.suruyor || s.pod ? " canli" : ""), "aria-label": "Şu an" },
    el("div", { class: "simdi-baslik" }, s.suruyor || s.pod ? el("span", { class: "nabiz", "aria-hidden": "true" }) : el("span", { class: "nokta" }),
      el("div", {}, el("b", {}, "Şu an"), el("span", { class: "ipucu" }, durumYazi))),
    s.uretimde?.length ? el("ul", { class: "simdi-liste" }, ...s.uretimde.map((x) => el("li", {},
      el("a", { href: `#${x.kimlik}` }, kapakImg(x.kapak), el("span", { class: "ad" }, x.ad),
        el("span", { class: "ipucu" }, x.asama === "onarim" ? (bekliyor ? "onarım sırada" : "onarım")
          : bekliyor ? "sırada" : x.gecen_aday ? "yeni adaylar üretiliyor" : "adaylar üretiliyor"))))) : null);
}

function beklenenBolumu(p) {
  const satirlar = [
    ...p.kulak.map((s) => ({ s, rozet: ["dinlemen gerekiyor", "amber"], metin: s.neden })),
    ...p.hatada.map((s) => ({ s, rozet: ["hata", "no"], metin: s.hata })),
    // süre dolmuş ama koşu olmamışsa (otomatik koşu kapalı) geçmiş saat yazmak yanıltıyordu
    ...p.yakinda.map((s) => ({ s, rozet: ["kendiliğinden onaylanacak", "gumus"],
      metin: new Date(s.zaman) <= new Date() ? "süre doldu; ilk koşuda onaylanır" : saatDakika(s.zaman) })),
    ...(p.takvim?.yazarsiz || []).map((s) => ({ s, rozet: ["yazar gerekli", "amber"],
      metin: "Orijinal söz yazarı bulunamadı; dağıtımcılar yazarsız cover almıyor. girdi/liste.toml'da şarkıya yazarlar = [\"Ad Soyad\"] ekle, paket sonraki koşuda yenilenip sıraya girer." })),
  ];
  const uyarilar = (p.uyarilar || []).map((u) => el("li", { class: "kayit uyari-kayit" },
    el("div", { class: "kayit-ad" }, el("span", { class: "ad" }, u.baslik)),
    el("div", { class: "olculer" }, el("span", { class: "rozet amber" }, u.etiket || "hat"), el("span", { class: "duz" }, u.metin))));
  const sayi = satirlar.length + uyarilar.length;
  return el("section", { class: "bolum", "aria-label": "Senden beklenen" },
    el("h2", { class: "bolum-baslik" }, "Senden beklenen", sayi ? el("span", { class: "g-sayi dikkat" }, String(sayi)) : null),
    sayi ? el("ul", { class: "kayitlar" }, ...uyarilar, ...satirlar.map(({ s, rozet, metin }) => el("li", { class: "kayit kapakli" },
      kapakImg(s.kapak, "kapak-kucuk kapak-orta"),
      el("div", { class: "kayit-ad" }, el("a", { class: "ad", href: `#${s.kimlik}` }, s.ad), el("span", { class: "sanatci" }, s.sanatci)),
      el("div", { class: "olculer" }, el("span", { class: `rozet ${rozet[1]}` }, rozet[0]), el("span", { class: "duz" }, metin || "")),
      el("div", { class: "kayit-eylem" }, el("a", { class: "dugme ikincil", href: `#${s.kimlik}` }, "Aç")))))
      : el("p", { class: "bos-kutu" }, "Şu an senden beklenen bir şey yok. Hat kendi kendine çalışıyor."));
}

// dağıtımdakiler kapak duvarı: 21 aynı satır yerine tek bakışta
function dagitimBolumu(liste) {
  if (!liste?.length) return null;
  const hal = (s) => s.geri_cek ? ["geri çekilecek", "gumus"] : s.canli ? ["Spotify'da", "ok"] : s.dagitim_durumu === "rejected" ? ["reddedildi", "no"]
    : ["approved", "live"].includes(s.dagitim_durumu) ? [DAGITIM[s.dagitim_durumu], "ok"] : [DAGITIM[s.dagitim_durumu] || "incelemede", ""];
  const ozet = Object.entries(liste.reduce((o, s) => { const h = hal(s); o[h[0]] = o[h[0]] || [0, h[1]]; o[h[0]][0]++; return o; }, {}));
  return el("section", { class: "bolum", "aria-label": "Dağıtımda" },
    el("h2", { class: "bolum-baslik" }, "Dağıtımda", el("span", { class: "g-sayi" }, String(liste.length)),
      el("span", { class: "bosluk" }), ...ozet.map(([ad, [n, sinif]]) => el("span", { class: `rozet ${sinif}` }, `${n} ${ad}`))),
    el("ul", { class: "kapak-duvari" }, ...liste.map((s) => {
      const [yazi, sinif] = hal(s);
      return el("li", {}, el("a", { href: `#${s.kimlik}`, class: `duvar-kapak ${sinif}`, title: `${s.ad} — ${s.sanatci} · ${yazi} · çıkış ${tarih(s.yayin_tarihi)}` },
        s.kapak ? el("img", { src: `${s.kapak}&boyut=480`, alt: "", loading: "lazy", decoding: "async" }) : el("span", { class: "duvar-bos" }, dalgaIsareti(24)),
        el("span", { class: "duvar-durum", "data-s": sinif || "bekliyor" }, yazi),
        el("span", { class: "duvar-ad" }, s.ad), el("span", { class: "duvar-sanatci" }, s.sanatci)));
    })));
}

function kazancPaneli() {
  const kutu = el("section", { class: "cam yan-panel", "aria-label": "Kazanç" }, el("h2", {}, "Kazanç"),
    el("p", { class: "kazanc-alt" }, "Yükleniyor…"));
  const para = (n, birim) => new Intl.NumberFormat("tr-TR", { style: "currency", currency: birim || "GBP" }).format(n || 0);
  api("/api/kazanc").then((k) => {
    if (!k.bagli) { doldur(kutu, el("h2", {}, "Kazanç"), el("p", { class: "kazanc-alt" }, k.mesaj
      || "Dağıtımcının kazanç raporu bağlı değil.")); return; }
    if (k.ulasilamadi) {
      doldur(kutu, el("h2", {}, "Kazanç"), el("p", { class: "kazanc-toplam soluk-sayi" }, "—"),
        el("p", { class: "kazanc-alt", title: k.hata }, k.erisim_kapali ? "Tunearo API erişimi kapalı. Hesap sahibi açınca raporlar burada görünür."
          : "Tunearo'ya şu an ulaşılamıyor; sonra yeniden denenir."));
      return;
    }
    const enCok = Math.max(...k.kaynaklar.map((x) => x.tutar), 0.01);
    doldur(kutu, el("h2", {}, "Kazanç"),
      el("p", { class: "kazanc-toplam gumus-yazi" }, para(k.toplam, k.para)),
      el("p", { class: "kazanc-alt" }, `${k.son_ay ? `son rapor (${k.son_ay})` : "bu ay"} ${para(k.bu_ay, k.para)} · ${k.yayinlar.length} yayın · aylık raporla güncellenir`),
      k.kaynaklar.length ? el("ul", { class: "cubuklar" }, ...k.kaynaklar.slice(0, 6).map((x) => el("li", {},
        el("span", {}, x.kaynak), el("b", {}, para(x.tutar, k.para)),
        el("span", { class: "cubuk", "aria-hidden": "true" }, el("i", { style: { width: `${Math.round((x.tutar / enCok) * 100)}%` } })))))
        : el("p", { class: "kazanc-alt" }, "İlk rapor, parçalar mağazalarda dinlendikten sonraki ay gelir."));
  }).catch((e) => doldur(kutu, el("h2", {}, "Kazanç"), el("p", { class: "kazanc-alt" }, e.message)));
  return kutu;
}

// üretim tarifi: şarkıların hangi modelle ve ayarla üretildiği (config/motor.toml)
function tarifPaneli(a) {
  const t = a.tarif;
  if (!t) return null;
  const satir = (ad, deger, title) => [el("dt", {}, ad), el("dd", { title: title || false }, deger)];
  return el("section", { class: "cam yan-panel", "aria-label": "Üretim tarifi" }, el("h2", {}, "Üretim tarifi"),
    el("p", { class: "tarif-model" }, "ACE-Step 1.5 ", el("b", {}, t.model.includes("xl") ? "XL-SFT 4B" : t.model),
      t.lora ? el("span", { class: "rozet tarif" }, `+ LoRA ${loraTarihi(t.lora)}`) : null),
    el("dl", { class: "ayar-listesi" },
      ...satir("Stil", t.betim ? "şarkının betiminden" : "listeden"),
      ...satir("Aday", `${t.aday} × ${t.adim} adım`),
      ...satir("Cover gücü", virgul(t.guc)),
      ...(t.lora ? satir("LoRA ölçeği", virgul(t.lora_olcek), "95 çok türlü şarkı, cover görevinde eğitildi; beat'in orijinal ritmi izlemesi 0,23 → 0,57") : [])));
}

function gecePaneli(g) {
  const kutu = el("section", { class: "cam yan-panel", "aria-label": "Son koşu" }, el("h2", {}, "Son koşu"));
  if (!g) { kutu.append(el("p", { class: "kazanc-alt" }, "Henüz koşu yok.")); return kutu; }
  const sorun = !g.suruyor && (g.kod || g.sorunlu);
  const durum = g.suruyor ? `sürüyor · ${g.adim || "başlıyor"}` : sorun ? `sorunlu: ${g.sorunlu || `kod ${g.kod}`}` : "sorunsuz bitti";
  kutu.append(el("p", { class: "gece-satir" }, el("span", { class: "nokta" + (g.suruyor ? " suruyor" : sorun ? " sorun" : "") }), durum),
    el("p", { class: "kazanc-alt" }, `${saatDakika(g.bas)}${g.bit ? ` → ${new Date(g.bit).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}` : ""}`));
  return kutu;
}

function ayarPaneli(a, kota) {
  const satir = (ad, deger) => [el("dt", {}, ad), el("dd", {}, deger)];
  const butce = a.uzak_ay_usd != null && a.uzak_butce ? Math.min(1, a.uzak_ay_usd / a.uzak_butce) : null;
  return el("section", { class: "cam yan-panel", "aria-label": "Otomasyon" }, el("h2", {}, "Otomasyon"),
    butce != null ? el("div", { class: "butce" + (butce > 0.85 ? " dar" : "") },
      el("div", { class: "butce-ust" }, el("span", {}, "Bu ay GPU"), el("b", {}, `${a.uzak_ay_usd.toFixed(2)} $ / ${a.uzak_butce} $`)),
      el("span", { class: "cubuk", "aria-hidden": "true" }, el("i", { style: { transform: `scaleX(${butce})` } }))) : null,
    el("dl", { class: "ayar-listesi" },
      ...satir("Üretim", a.uretim_acik === false ? "duraklatıldı" : a.uretim || "—"),
      ...satir("Dağıtımcı", DAGITIMCI[a.dagitimci] || a.dagitimci || "seçilmedi"),
      ...satir("Takvim", !a.takvim_acik ? "kapalı" : a.haftada === 0 ? "açık · sınırsız" : a.haftada >= 7 ? "açık · her gün" : `açık · haftada ${a.haftada}`),
      ...satir("Otomatik onay", (a.oto_onay ? `${a.oto_onay_saat} sa` : "kapalı") + (a.oto_isabet?.sarki ? ` · isabet ${a.oto_isabet.isabet}/${a.oto_isabet.sarki}` : "")
        + (a.oto_estetik?.sarki ? ` · estetik ${a.oto_estetik.isabet}/${a.oto_estetik.sarki}` : "") + (a.oto_secici === "estetik" ? " · öneri estetikten" : "")),
      ...satir("Kapak", a.kapak === "pinterest" ? "Pinterest" : "üretilen"),
      ...satir("Spotify", !kota?.bagli ? "bağlı değil" : kota.kilit_sn ? `kilitli · ${saatYazi(kota.kilit_sn)}` : `${kota.bugun}/${kota.tavan} istek`)));
}

// ---- Sanatçı (#_sanatci): Orvane'ın kataloğu dağıtımda, dağıtım ayarları, odadan başlatılan işler ----
const RN = "https://www.routenote.com/rn";
const HAL = {
  kontrol: { ad: "Kontrol et", rozet: ["gönderim yarıda", "amber"], aciklama: "Son tıktan sonra iş yarıda kaldı. RouteNote panelinde yayına bak ve ne gördüğünü seç; hat yeniden göndermez." },
  taslak_hazir: { ad: "Gönderime hazır", rozet: ["taslak hazır", "gumus"], aciklama: "RouteNote'ta dört adımı tamam. Önceki oturumda hazırlandığı için otomasyon gönderemez: \"RouteNote\" ile taslağı aç, Distribute'a bas, sonra \"Panelde gönderdim\"." },
  taslak_yarim: { ad: "Yarım taslak", rozet: ["yarım", "amber"], aciklama: "Bir adımda kaldı; tamamlayınca aynı taslaktan sürer, yeni taslak açılmaz." },
  kuyruk: { ad: "Kuyrukta", rozet: ["paket hazır", ""], aciklama: "Paketlendi, RouteNote'a dokunulmadı." },
  inceleme: { ad: "İncelemede", rozet: ["incelemede", ""], aciklama: "RouteNote'a gönderildi; yayın tarihinde mağazalara çıkar." },
  yayinda: { ad: "Yayında", rozet: ["yayında", "ok"], aciklama: "Spotify'da dinlenebilir." },
};
const ADIM = { olusturuldu: "taslak açıldı", album: "albüm bilgisi", ses_kaydedildi: "ses yüklendi", ses: "ses ve parça", kapak: "kapak", hazir: "dört adım tamam", gonderiliyor: "gönderiliyor", gonderildi: "gönderildi" };
const IS_ADI = { taslak: "Taslak", gonder: "Gönderim", giris: "RouteNote girişi", elle_gonder: "Elle yayın gönderimi", elle_taslak: "Elle yayın taslağı" };
let isIzle = null;

async function sanatciGoster() {
  const ana = $("#ana");
  let s;
  try { s = await api("/api/sanatci"); } catch (e) { doldur(ana, bosEkran("Sanatçı görünümü açılamadı", e.message)); return; }
  acikSarki = null;
  const say = (h) => s.katalog.filter((x) => x.hal === h).length;
  const isSuruyor = !!s.is?.suruyor;
  const kapaklar = s.katalog.filter((x) => x.kapak).slice(0, 6);
  const profil = s.ayar.spotify_sanatci_id || s.profiller[0];
  const durak = (ad, n, alt, dikkat) => el("div", { class: "durak" + (dikkat ? " dikkat" : n ? " dolu" : ""), "aria-label": `${ad}: ${n} ${alt}` },
    el("span", { class: "durak-isik", "aria-hidden": "true" }),
    el("span", { class: "durak-sayi" + (n ? " gumus-yazi" : "") }, String(n)),
    el("span", { class: "durak-ad" }, ad), el("span", { class: "durak-alt" }, alt));
  doldur(ana,
    el("header", { class: "sanatci-ust" },
      el("div", { class: "mozaik", "aria-hidden": "true" }, ...Array.from({ length: 6 }, (_, i) => kapaklar[i]
        ? el("img", { src: `${kapaklar[i].kapak}&boyut=96`, alt: "", loading: "lazy", width: 48, height: 48 }) : el("span", { class: "mozaik-bos" }))),
      el("div", { class: "sanatci-kimlik" },
        el("p", { class: "ust-satir ipucu" }, "Sanatçı"),
        el("h1", { class: "gumus-yazi" }, s.ad || "Sanatçı adı yok"),
        el("p", { class: "ipucu" }, [DAGITIMCI[s.dagitimci] || "dağıtımcı seçilmedi",
          profil ? "Spotify profili bağlı" : "Spotify profili ilk yayınla oluşur",
          s.profiller.length > 1 ? `${s.profiller.length} ayrı profil: birleştirme gerekli` : null].filter(Boolean).join(" · ")),
        profil ? el("a", { class: "dugme ikincil kucuk", href: `https://open.spotify.com/artist/${profil}`, target: "_blank", rel: "noopener" }, "Spotify profilini aç") : null)),
    el("section", { class: "cam zincir zincir-4", "aria-label": "Katalog" },
      durak("Kuyruk", say("kuyruk"), "paket"),
      durak("Taslak", say("taslak_hazir") + say("taslak_yarim"), "RouteNote'ta", say("taslak_hazir") > 0),
      durak("İnceleme", say("inceleme"), "gönderildi"),
      durak("Yayında", say("yayinda"), "Spotify")),
    el("div", { class: "pano-izgara" },
      el("div", { class: "pano-sol" },
        ...Object.keys(HAL).map((h) => [h, s.katalog.filter((x) => x.hal === h)]).filter(([, l]) => l.length).map(([h, l]) => defterBolumu(h, l, s, isSuruyor)),
        s.katalog.length ? null : el("p", { class: "bos-kutu" }, "Katalog boş. Onayladığın şarkılar paketlenince burada görünür.")),
      el("div", { class: "pano-sag" }, isPaneli(s.is), oturumPaneli(s.oturum, isSuruyor), dagitimAyarPaneli(s))));
  isTakip(s.is);
}

function defterBolumu(h, liste, s, isSuruyor) {
  return el("section", { class: "bolum", "aria-label": HAL[h].ad },
    el("h2", { class: "bolum-baslik" }, HAL[h].ad, el("span", { class: "g-sayi" + (h === "taslak_hazir" ? " dikkat" : "") }, String(liste.length))),
    el("p", { class: "ipucu bolum-not" }, HAL[h].aciklama),
    el("ul", { class: "kayitlar" }, ...liste.map((x) => defterSatiri(x, s, isSuruyor))));
}

function defterSatiri(x, s, isSuruyor) {
  const h = HAL[x.hal];
  const ad = x.kimlik ? el("a", { class: "ad", href: `#${x.kimlik}` }, x.ad) : el("span", { class: "ad" }, x.ad);
  const eylem = [];
  const isBaslat = (yol, mesaj) => async (e) => {
    const b = e.currentTarget; b.setAttribute("aria-busy", "true"); b.disabled = true;
    try { await api(yol, {}); bildir(mesaj); } catch (err) { bildir(err.message, true); }
    sanatciGoster();
  };
  // RouteNote yayın sayfası yalnız taslağı dolduran oturumda dolu: ayrı "Taslağı hazırla" + "Gönder" ikinci adımda boş
  // sayfaya düşer (2026-10-16, lovely). Kuyruktaki paket tek işte açılıp gönderilir; hazır taslak panelden gönderilir.
  if (x.kimlik && x.hal === "taslak_yarim")
    eylem.push(el("button", { class: "dugme ikincil kucuk", type: "button", disabled: isSuruyor,
      onclick: isBaslat(`/api/sanatci/${x.kimlik}/taslak`, `"${x.ad}" için RouteNote taslağı tamamlanıyor; bir tarayıcı penceresi açılabilir.`) },
      "Taslağı tamamla"));
  if (x.kimlik && x.hal === "kuyruk")
    eylem.push(el("button", { class: "dugme tehlike kucuk", type: "button", disabled: isSuruyor, onclick: () => gonderPenceresi(x, s) }, "Yükle ve gönder…"));
  const sonuc = (gonderildi) => () => gonderimSonucuSor(x.ad, gonderildi, async () => {
    try { const r = await api(`/api/sanatci/${x.kimlik}/gonderim-sonucu`, { gonderildi }); bildir(r.mesaj); } catch (err) { bildir(err.message, true); }
    sanatciGoster();
  });
  if (x.kimlik && x.hal === "taslak_hazir")
    eylem.push(el("button", { class: "dugme kucuk", type: "button", onclick: sonuc(true), title: "RouteNote panelinde Distribute'a bastım, yayın incelemede" }, "Panelde gönderdim"));
  if (x.kimlik && x.hal === "kontrol") {
    eylem.push(el("button", { class: "dugme kucuk", type: "button", onclick: sonuc(true), title: "Panelde incelemede görünüyor" }, "Gönderilmiş"),
      el("button", { class: "dugme ikincil kucuk", type: "button", onclick: sonuc(false), title: "Panelde hâlâ taslak" }, "Taslakta duruyor"));
  }
  if (x.upc && x.hal !== "kuyruk")
    eylem.push(el("a", { class: "dugme kucuk", href: x.hal.startsWith("taslak") || x.hal === "kontrol" ? `${RN}/editalbum/${x.upc}` : `${RN}/releases`, target: "_blank", rel: "noopener" }, "RouteNote"));
  if (x.spotify_id)
    eylem.push(el("a", { class: "dugme kucuk", href: `https://open.spotify.com/track/${x.spotify_id}`, target: "_blank", rel: "noopener" }, "Spotify"));
  return el("li", { class: "kayit kapakli" + (x.uyari ? " uyarili" : "") },
    kapakImg(x.kapak, "kapak-kucuk kapak-orta"),
    el("div", { class: "kayit-ad" }, ad, el("span", { class: "sanatci" }, `orijinali ${x.orijinal || "—"}`)),
    el("div", { class: "olculer" },
      el("span", { class: `rozet ${h.rozet[1]}` }, h.rozet[0]),
      x.adim && x.hal === "taslak_yarim" ? el("span", {}, "son adım ", el("b", {}, ADIM[x.adim] || x.adim)) : null,
      x.yayin_tarihi ? el("span", {}, "çıkış ", el("b", {}, tarih(x.yayin_tarihi))) : null,
      x.upc ? el("span", { title: "UPC" }, "UPC ", el("b", {}, x.upc)) : null,
      x.isrc ? el("span", { title: "ISRC (RouteNote'un atadığı)" }, "ISRC ", el("b", {}, x.isrc)) : null,
      x.eski_tarif ? el("span", { class: "rozet", title: "Bu paket bugünkü üretim tarifinden (CFG 10) önce üretildi" }, "eski tarif") : null,
      x.arsiv ? el("span", { class: "rozet", title: "Hat 10 Ekim'de baştan kurulurken arşive alındı; yayın RouteNote'ta sürüyor" }, "arşivden") : null),
    el("div", { class: "kayit-eylem" }, ...eylem),
    x.uyari ? el("p", { class: "kayit-uyari", role: "note" }, x.uyari) : null);
}

function gonderPenceresi(x, s) {
  const kutu = el("input", { id: "gonder-onay", type: "text", autocomplete: "off", spellcheck: "false", placeholder: x.ad });
  const dugme = el("button", { class: "dugme tehlike dolu", type: "button", disabled: true, onclick: async () => {
    dugme.setAttribute("aria-busy", "true"); dugme.disabled = true;
    try {
      await api(`/api/sanatci/${x.kimlik}/gonder`, { onay: kutu.value });
      dlg.close(); bildir(`"${x.ad}" RouteNote'a gönderiliyor. "Son iş" panelinden izleyebilirsin.`);
    } catch (e) { dugme.removeAttribute("aria-busy"); dugme.disabled = false; bildir(e.message, true); return; }
    sanatciGoster();
  } }, "RouteNote'a gönder");
  // sunucuyla aynı kural (sanatci.onay_metni): I/İ/ı farkı ve büyük-küçük harf aranmaz
  const sade = (s) => s.trim().replace(/[Iİı]/g, "i").toLowerCase();
  kutu.addEventListener("input", () => { dugme.disabled = sade(kutu.value) !== sade(x.ad); });
  // yeni_yayin_tarihi boş: ayar "onaylanınca" (satış tarihi boş, RouteNote onaylar onaylamaz yayında)
  const onaydaYayin = s.yeni_yayin_tarihi ? null : "RouteNote onaylayınca (5–10 iş günü)";
  const yakin = onaydaYayin || !x.yayin_tarihi || new Date(x.yayin_tarihi) < new Date(Date.now() + 10 * 864e5);
  const dlg = pencere(`"${x.ad}" RouteNote'a gönderilsin mi?`, [
    el("p", {}, "Taslak açılır, dört adım doldurulur ve yayın aynı oturumda incelemeye gönderilir.",
      " RouteNote'un şartları senin adına kabul edilir. Gönderdikten sonra ses ve playlist değiştirilemez; kaldırmak için panelden takedown gerekir."),
    el("dl", { class: "ayar-listesi gonder-ozet" },
      el("dt", {}, "Sanatçı"), el("dd", {}, s.ad),
      el("dt", {}, "Orijinali"), el("dd", {}, x.orijinal || "—"),
      el("dt", {}, "Yayın tarihi"), el("dd", {}, onaydaYayin || (yakin ? `${tarih(s.yeni_yayin_tarihi)} (yenilenecek)` : tarih(x.yayin_tarihi))),
      el("dt", {}, "Bölge"), el("dd", {}, "ABD, Kanada, Meksika, Hindistan, Pakistan hariç"),
      el("dt", {}, "Kapalı mağaza"), el("dd", {}, "Amazon, Kore mağazaları, YouTube Content ID")),
    x.eski_tarif ? el("p", { class: "uyari" }, "Bu paket bugünkü üretim tarifinden önce üretildi. Yeni modeli beklemek istiyorsan şimdilik gönderme.") : null,
    el("label", { for: "gonder-onay", class: "onay-etiket" }, "Onaylamak için şarkının adını yaz: ", el("b", {}, x.ad)), kutu,
  ], [el("button", { class: "dugme", type: "button", onclick: () => dlg.close() }, "Vazgeç"), dugme], "gonder-pencere");
  kutu.focus();
}

function isPaneli(is) {
  const panel = el("section", { class: "cam yan-panel is-paneli", id: "is-paneli", "aria-label": "Son iş", "aria-live": "polite" }, el("h2", {}, "Son iş"));
  if (!is || !is.ad) { panel.append(el("p", { class: "ipucu" }, "Odadan başlatılan bir iş yok. Taslak ya da gönderim buradan izlenir.")); return panel; }
  const hata = is.kod != null && is.kod !== 0;
  const oturumYok = (is.gunluk_son || []).some((x) => /oturumu yok|OturumYok/.test(x));
  const hal = is.suruyor ? ["sürüyor", "suruyor"] : is.sahipsiz ? ["bitti (sonuç günlükte)", ""] : hata ? ["hata", "sorun"] : ["bitti", ""];
  doldur(panel, el("h2", {}, "Son iş"),  // yerel append boş parçayı "null" metni yazıyordu ("nullnull")
    el("p", { class: "gece-satir" }, is.suruyor ? el("span", { class: "nabiz", "aria-hidden": "true" }) : el("span", { class: `nokta ${hal[1]}` }),
      el("b", {}, `${IS_ADI[is.ad] || is.ad}${is.kimlik ? ` · ${is.kimlik}` : ""}`), el("span", { class: "ipucu" }, `${hal[0]} · ${saatDakika(is.baslangic)}`)),
    oturumYok ? el("p", { class: "uyari" }, "RouteNote oturumu düşmüş. Aşağıdan giriş yap, sonra işi yeniden başlat; taslak kaldığı adımdan sürer.") : null,
    is.sahipsiz ? el("p", { class: "ipucu" }, is.suruyor ? "Oda yeniden açıldı; iş arka planda sürüyor, bitince yeni iş başlatılabilir."
      : `Oda yeniden açılmadan önce bitti; sonucu günlükte: ${is.gunluk}`) : null,
    el("pre", { class: "is-gunluk", tabindex: "0", "aria-label": "İş günlüğü" }, (is.gunluk_son || []).slice(-14).join("\n") || "…"));
  return panel;
}

function isTakip(is) {
  clearTimeout(isIzle);
  if (!is?.suruyor) return;
  isIzle = setTimeout(async () => {
    if (location.hash !== "#_sanatci") return;
    try {
      const yeni = await api("/api/sanatci/is");
      if (yeni.suruyor) { $("#is-paneli")?.replaceWith(isPaneli(yeni)); isTakip(yeni); return; }
      bildir(yeni.kod === 0 ? `${IS_ADI[yeni.ad] || "İş"} bitti.` : `${IS_ADI[yeni.ad] || "İş"} hata verdi; "Son iş" günlüğüne bak.`, yeni.kod !== 0);
      sanatciGoster();
    } catch { isTakip(is); }
  }, 3000);
}

function oturumPaneli(o, isSuruyor) {
  return el("section", { class: "cam yan-panel", "aria-label": "RouteNote oturumu" }, el("h2", {}, "RouteNote oturumu"),
    el("dl", { class: "ayar-listesi" },
      el("dt", {}, "Profil"), el("dd", {}, o.profil ? "kayıtlı" : "yok"),
      el("dt", {}, "Son kullanım"), el("dd", {}, o.son ? saatDakika(o.son) : "—")),
    el("p", { class: "ipucu" }, "Oturum birkaç saat kullanılmazsa düşüyor. Bir iş \"oturum yok\" derse buradan gir; şifre hatta tutulmaz."),
    el("button", { class: "dugme ikincil", type: "button", disabled: isSuruyor, onclick: async (e) => {
      e.currentTarget.disabled = true;
      try { await api("/api/sanatci/giris", {}); bildir("RouteNote penceresi açılıyor; giriş yapınca kendiliğinden kapanır."); } catch (err) { bildir(err.message, true); }
      sanatciGoster();
    } }, "RouteNote'a giriş yap"));
}

// gece yüklemesi açıkken takvim her gece sıradaki paketleri kendisi gönderir (geri alınamaz): şarkı gönderimi gibi ad
// yazdırılır, sunucu da aynısını ister
function geceAcPenceresi(s, kaydet) {
  const kutu = el("input", { id: "gece-onay", type: "text", autocomplete: "off", spellcheck: "false", placeholder: s.ad });
  const sade = (m) => m.trim().replace(/[Iİı]/g, "i").toLowerCase();
  const dugme = el("button", { class: "dugme tehlike dolu", type: "button", disabled: true, onclick: async () => {
    dugme.disabled = true; dlg.close();
    await kaydet({ gece: true, onay: kutu.value }, "Gece yüklemesi açıldı: takvim sırası geleni kendisi gönderir.");
  } }, "Gece yüklemesini aç");
  kutu.addEventListener("input", () => { dugme.disabled = sade(kutu.value) !== sade(s.ad); });
  const sira = s.katalog.filter((x) => x.hal === "kuyruk" || x.hal === "taslak_hazir").length;
  const eski = s.katalog.filter((x) => (x.hal === "kuyruk" || x.hal === "taslak_hazir") && x.eski_tarif).length;
  const dlg = pencere("Gece yüklemesi açılsın mı?", [
    el("p", {}, `Her gece takvimde sırası gelen paket RouteNote'a senin tıklaman olmadan gönderilir; şartlar senin adına kabul edilir. Şu an ${sira} paket sırada`,
      eski ? `, ${eski} tanesi bugünkü tariften önce üretildi.` : "."),
    el("label", { for: "gece-onay" }, "Onaylamak için sanatçı adını yaz: ", el("b", {}, s.ad)), kutu],
    [el("button", { class: "dugme ikincil", type: "button", onclick: () => dlg.close() }, "Vazgeç"), dugme], "gonder-pencere");
  kutu.focus();
}

function dagitimAyarPaneli(s) {
  const kaydet = async (degisiklik, mesaj) => {
    try { await api("/api/sanatci/ayar", degisiklik); bildir(mesaj); } catch (e) { bildir(e.message, true); }
    sanatciGoster();
  };
  const gece = el("button", { class: "anahtar", type: "button", role: "switch", "aria-checked": s.ayar.gece ? "true" : "false", "aria-labelledby": "gece-ad",
    onclick: () => s.ayar.gece ? kaydet({ gece: false }, "Gece yüklemesi kapandı: sırası gelen paket yalnız bildirilir.") : geceAcPenceresi(s, kaydet) },
    el("span", { "aria-hidden": "true" }));
  // boş kutu `+""` = 0 olup "onaylanınca yayında"ya geçiriyordu: değer zorunlu, tam sayı
  const gun = el("input", { id: "yayin-gun", type: "number", min: 0, max: 120, step: 1, required: true, value: s.ayar.yayin_on_gun ?? 21, inputmode: "numeric", "aria-describedby": "yayin-gun-ipucu" });
  const kimlik = el("input", { id: "spotify-kimlik", type: "text", value: s.ayar.spotify_sanatci_id || "", maxlength: 40, spellcheck: "false", autocomplete: "off", placeholder: "profil adresindeki kimlik" });
  return el("section", { class: "cam yan-panel", "aria-label": "Dağıtım ayarları" }, el("h2", {}, "Dağıtım"),
    el("div", { class: "ayar-satir" }, el("div", {}, el("b", { id: "gece-ad" }, "Gece yüklemesi"),
      el("p", { class: "ipucu" }, s.ayar.gece ? "Takvim sırası gelen paketi kendisi gönderir." : "Kapalı: sırası gelen paket yalnız bildirilir, gönderim senin tıklamanla.")), gece),
    s.takvim?.beklemede ? el("p", { class: "ipucu" }, `Takvim: ${s.takvim.beklemede}`) : null,
    el("form", { class: "ayar-form", onsubmit: (e) => { e.preventDefault(); kaydet({ yayin_on_gun: +gun.value }, +gun.value === 0 ? "Yayınlar artık RouteNote onaylar onaylamaz çıkar." : `Yayın tarihi artık yüklemeden ${gun.value} gün sonra.`); } },
      el("label", { for: "yayin-gun" }, "Yayın tarihi, yüklemeden"), el("div", { class: "satir-ici" }, gun, el("span", { class: "ipucu" }, "gün sonra"),
        el("button", { class: "dugme kucuk", type: "submit" }, "Kaydet")),
      el("p", { class: "ipucu", id: "yayin-gun-ipucu" }, s.ayar.yayin_on_gun === 0 ? "0: tarih yok, RouteNote onaylar onaylamaz yayında (en erken)." : "0 yazarsan onaylar onaylamaz yayında (en erken); tarih seçersen en az 10 gün.")),
    el("form", { class: "ayar-form", onsubmit: (e) => { e.preventDefault(); kaydet({ spotify_sanatci_id: kimlik.value.trim() }, kimlik.value.trim() ? "Spotify profili kaydedildi; yeni yüklemeler bu profile bağlanır." : "Spotify profili temizlendi."); } },
      el("label", { for: "spotify-kimlik" }, "Spotify sanatçı kimliği"), el("div", { class: "satir-ici" }, kimlik, el("button", { class: "dugme kucuk", type: "submit" }, "Kaydet")),
      el("p", { class: "ipucu" }, "İlk parça yayına girince profil adresindeki kimliği yaz; sonraki yüklemeler ayrı profil açmaz.")));
}

// ---- bulucu: STILLMORE FINDER'ın motoruyla Spotify araması (yanki/bulucu.py; Spotify uygulamasının içinden okur) ----
const SPOTIFY = "https://open.spotify.com";
const BTUR = { parca: "Parça", playlist: "Playlist", sanatci: "Sanatçı", katalog: "Katalog", album: "Albüm", isrc: "ISRC", upc: "UPC", listeler: "Liste keşfi", baglan: "Spotify bağlantısı" };
const SP_YOL = { parca: "track", playlist: "playlist", sanatci: "artist", katalog: "artist", album: "album" };
const tamSayi = (n) => n == null ? "—" : Number(n).toLocaleString("tr-TR");
const spLink = (tur, id, metin = "Spotify'da aç", sinif = "dugme kucuk") =>
  el("a", { class: sinif, href: `${SPOTIFY}/${SP_YOL[tur]}/${id}`, target: "_blank", rel: "noopener" }, metin);
let bulucuAcik, bulucuIzle = null, bulucuGirdi = "", bulucuSuzgec = "bosluk";

// yapıştırılanın türü: yalnız önizleme, karar sunucuda (bulucu.coz)
function girdiTuru(m) {
  m = (m || "").trim();
  const b = /(?:open\.spotify\.com\/(?:intl-[a-z-]+\/)?(?:embed\/)?|spotify:)(track|playlist|artist|album)[/:]([A-Za-z0-9]{22})/.exec(m);
  if (b) return { track: "parca", artist: "sanatci" }[b[1]] || b[1];
  const s = m.replace(/[\s-]/g, "").toUpperCase();
  if (/^[A-Z]{2}[A-Z0-9]{3}\d{7}$/.test(s)) return "isrc";
  if (/^\d{12,14}$/.test(s)) return "upc";
  return null;
}

// Spotify kalkmış parçanın sayacını 90 gün tutar; STILLMORE kalkış tarihini aralığa sıkıştırır (windowText'in karşılığı)
function pencereYazi(w) {
  if (!w) return null;
  const r = (a, b) => a != null && b != null && a !== b ? `${Math.max(0, a)}–${Math.max(0, b)}` : String(Math.max(0, b ?? a));
  switch (w.durum) {
    case "expired": return ["90 gün doldu", "no"];
    case "maybe-expired": return ["dolmuş olabilir", "amber"];
    case "soon": return [w.en_az == null ? `en çok ${Math.max(0, w.en_cok)} gün` : `${r(w.en_az, w.en_cok)} gün kaldı`, "amber"];
    case "within": return [w.en_az == null ? `en çok ${Math.max(0, w.en_cok)} gün` : `${r(w.en_az, w.en_cok)} gün kaldı`, "ok"];
    case "retained": return ["sayaç duruyor", "ok"];
    case "likely-expired": return ["muhtemelen doldu", "no"];
    default: return null;
  }
}

function disKapak(url, sinif = "kapak-orta") {
  if (!url) return el("span", { class: `kapak-kucuk ${sinif} bos`, "aria-hidden": "true" }, dalgaIsareti());
  return el("img", { class: `kapak-kucuk ${sinif}`, src: url, alt: "", loading: "lazy", decoding: "async", referrerpolicy: "no-referrer", width: 44, height: 44 });
}

async function kopyala(metin, ne) {
  try { await navigator.clipboard.writeText(metin); bildir(`${ne} kopyalandı.`); } catch { bildir(`${ne} kopyalanamadı.`, true); }
}
const kopyaDugmesi = (metin, ne) => metin ? el("button", { class: "dugme kucuk", type: "button", onclick: () => kopyala(metin, ne) }, `${ne} kopyala`) : null;
// credits'te boş rol "Not Documented" geliyor
const belgeli = (adlar) => (adlar || []).filter((x) => !/^not documented$/i.test(x));

async function bulucuIs(yol, govde = {}) {
  try { await api(yol, govde); } catch (e) { bildir(e.message, true); return; }
  bulucuGoster();
}
const bulucuAc = (tur, id) => bulucuIs(`/api/bulucu/ac/${tur}/${encodeURIComponent(id)}`);

// kaydı varsa açar (anında), yoksa okur
async function kayitAc(tur, id) {
  try { await api(`/api/bulucu/sonuc/${tur}-${encodeURIComponent(id)}`); bulucuAcik = `${tur}-${id}`; depo.yaz("bulucu.acik", bulucuAcik); bulucuGoster(); scrollTo(0, 0); }
  catch { bulucuAc(tur, id); }
}

async function bulucuGoster() {
  const ana = $("#ana");
  let d;
  try { d = await api("/api/bulucu"); } catch (e) { doldur(ana, bosEkran("Bulucu açılamadı", e.message)); return; }
  // ilk açılışta son açılan kayıt, yoksa en son arama: kaldığın yerden
  if (bulucuAcik === undefined) bulucuAcik = depo.oku("bulucu.acik", null) ?? d.gecmis[0]?.anahtar ?? null;
  let v = null;
  if (bulucuAcik) {
    try { v = await api(`/api/bulucu/sonuc/${encodeURIComponent(bulucuAcik)}`); } catch { bulucuAcik = null; depo.yaz("bulucu.acik", null); }
  }
  const suruyor = d.is?.durum === "suruyor";
  doldur(ana,
    el("header", { class: "sayfa-ust" }, el("h1", {}, "Bulucu"),
      el("p", { class: "ipucu" }, "STILLMORE FINDER'ın motoru: Spotify'dan kalkmış şarkıları, distribütörü, ISRC/UPC'yi ve dinlenmeyi bulur. Spotify uygulamasının içinden okur, Web API kotası harcamaz.")),
    aramaFormu(d.baglanti, suruyor),
    el("div", { class: "pano-izgara" },
      el("div", { class: "pano-sol" }, isSeridi(d.is), v ? sonucCiz(v, suruyor) : bulucuBos(d)),
      el("div", { class: "pano-sag" }, baglantiPaneli(d.baglanti, suruyor), konuPaneli(d.konular, !!d.baglanti.stillmore, suruyor), gecmisPaneli(d.gecmis), izlenenPaneli(d.izlenen, suruyor))));
  $("#g-bulucu").textContent = suruyor ? "•" : "";
  if (suruyor) bulucuTakip();
}

function bulucuTakip() {
  clearTimeout(bulucuIzle);
  bulucuIzle = setTimeout(async () => {
    if (location.hash !== "#_bulucu") { $("#g-bulucu").textContent = ""; return; }
    let is;
    try { is = await api("/api/bulucu/is"); } catch { bulucuTakip(); return; }
    if (is.durum === "suruyor") { $("#bulucu-is")?.replaceWith(isSeridi(is)); bulucuTakip(); return; }
    if (is.durum === "bitti" && is.anahtar) { bulucuAcik = is.anahtar; depo.yaz("bulucu.acik", is.anahtar); bildir(`${BTUR[is.tur] || "Arama"} hazır.`); scrollTo(0, 0); }
    else if (is.durum === "bitti") bildir("Spotify köprüsü bağlandı; arama yapabilirsin.");
    else if (is.durum === "hata") bildir(is.hata || "Bulucu işi hata verdi", true);
    bulucuGoster();
  }, 1200);
}

function aramaFormu(b, suruyor) {
  const tur = el("span", { class: "tur-cip", "aria-live": "polite" });
  const kutu = el("input", { id: "bulucu-girdi", type: "search", value: bulucuGirdi, autocomplete: "off", spellcheck: "false",
    placeholder: "Spotify linki, ISRC ya da UPC yapıştır", "aria-describedby": "bulucu-ipucu" });
  const turYaz = () => { const t = girdiTuru(kutu.value); tur.textContent = t ? BTUR[t] : ""; tur.hidden = !t; };
  kutu.addEventListener("input", () => { bulucuGirdi = kutu.value; turYaz(); });
  turYaz();
  const bagli = !!b.stillmore;
  return el("form", { class: "cam bulucu-ara", role: "search", onsubmit: (e) => {
    e.preventDefault();
    if (!kutu.value.trim()) { kutu.focus(); return; }
    bulucuIs("/api/bulucu/ara", { girdi: kutu.value });
  } },
    el("label", { for: "bulucu-girdi", class: "gizli" }, "Spotify linki, ISRC ya da UPC"),
    el("div", { class: "bulucu-satir" }, kutu, tur,
      bagli || suruyor ? el("button", { class: "dugme birincil", type: "submit", disabled: suruyor }, suruyor ? "Sürüyor…" : "Bul")
        : el("button", { class: "dugme birincil", type: "button", onclick: () => spotifyBaglan() }, b.spotify ? "Spotify'a bağlan" : "Spotify'ı aç ve bağlan")),
    el("p", { id: "bulucu-ipucu", class: "ipucu kucuk-ipucu" }, bagli
      ? "Playlist: kalkmış şarkılar ve dinlenmeleri · Parça: distribütör, ISRC, UPC, dinlenme · Sanatçı: dinleyici ve yer aldığı listeler · Albüm · ISRC · UPC"
      : "Arama Spotify uygulamasının içinden yapılır: önce bağlan. Spotify çalıyorsa yeniden başlatmadan önce sorulur."));
}

function isSeridi(is) {
  if (!is || is.durum === "bitti" || !is.durum) return el("div", { id: "bulucu-is", hidden: true });
  if (is.durum === "hata") return el("p", { id: "bulucu-is", class: "uyari", role: "alert" }, el("b", {}, `${BTUR[is.tur] || "İş"} yarıda kaldı: `), is.hata || "bilinmeyen hata");
  const i = is.ilerleme || {};
  const oran = i.toplam ? Math.min(1, i.bitti / i.toplam) : 0;
  return el("section", { id: "bulucu-is", class: "simdi-serit canli bulucu-is", "aria-live": "polite", "aria-busy": "true" },
    el("div", { class: "simdi-baslik" }, el("span", { class: "nabiz", "aria-hidden": "true" }),
      el("div", {}, el("b", {}, `${BTUR[is.tur] || "İş"} sürüyor`),
        el("span", { class: "ipucu" }, [i.etiket, i.toplam ? `${i.bitti}/${i.toplam}` : null].filter(Boolean).join(" · ") || "başlıyor…"))),
    el("div", { class: "ilerleme bulucu-ilerleme", role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": String(Math.round(oran * 100)) },
      el("span", { class: "ilerleme-dolu", style: { transform: `scaleX(${i.toplam ? oran : 0.04})` } })));
}

function bulucuBos(d) {
  const ornek = d.izlenen.find((x) => x.calinamayan);
  return el("section", { class: "bos-kutu bulucu-bos" },
    el("h2", { class: "bolum-baslik" }, "Nereden başlamalı"),
    el("ul", { class: "bulucu-ornekler" },
      el("li", {}, el("b", {}, "Playlist linki: "), "içindeki kalkmış şarkılar, kalkmadan önceki dinlenmeleriyle sıralanır. Boşluğu olanları (aynı ISRC'nin çalınan kopyası yok) tek tıkla keşfe gönderirsin."),
      el("li", {}, el("b", {}, "Parça linki: "), "distribütör (licensor UUID), ISRC, UPC, label, dinlenme, yazarlar, pazarlar ve aynı ISRC'li yüklemeler."),
      el("li", {}, el("b", {}, "Sanatçı linki: "), "aylık dinleyici, şehirler ve sanatçının yer aldığı playlist'ler; oradan listeleri tek tek tarayabilirsin.")),
    ornek ? el("p", { class: "ipucu" }, "Gece taranan bir listeyle dene: ",
      el("button", { class: "dugme kucuk ikincil", type: "button", disabled: !d.baglanti.stillmore, onclick: () => kayitAc("playlist", ornek.id) }, ornek.ad)) : null);
}

// Spotify köprüyle (CDP) açılır; bayraksız açıksa yeniden başlar; çalıyorsa önce sorulur (sunucu da 409 verir)
async function spotifyBaglan(zorla = false) {
  try { await api("/api/bulucu/baglan", { zorla }); bildir("Spotify köprüyle açılıyor…"); bulucuGoster(); }
  catch (e) {
    if (!zorla && /çalıyor/.test(e.message)) {
      const dlg = pencere("Spotify şu an çalıyor", [el("p", {}, "Köprü için Spotify yeniden başlatılır; çalan şarkı durur, sonra kaldığın yerden sürdürebilirsin.")],
        [el("button", { class: "dugme ikincil", type: "button", onclick: () => dlg.close() }, "Vazgeç"),
          el("button", { class: "dugme birincil", type: "button", onclick: () => { dlg.close(); spotifyBaglan(true); } }, "Yeniden başlat ve bağlan")]);
    } else bildir(e.message, true);
  }
}

function baglantiPaneli(b, suruyor) {
  const [ad, nokta, metin] = b.stillmore ? [`STILLMORE ${b.stillmore}`, "", `Bağlı${b.ulke ? ` · hesap ülkesi ${b.ulke}` : ""}`]
    : b.cdp ? ["Köprü açık", "sorun", b.hata || "STILLMORE yanıt vermiyor"]
    : b.spotify ? ["Spotify açık", "bekliyor", "Köprü kapalı: bağlanınca Spotify köprüyle yeniden açılır."]
    : ["Spotify kapalı", "bekliyor", "Bağlanınca Spotify köprüyle açılır."];
  return el("section", { class: "cam yan-panel", "aria-label": "Spotify köprüsü" }, el("h2", {}, "Spotify köprüsü"),
    el("p", { class: "gece-satir" }, el("span", { class: `nokta ${nokta}` }), el("b", {}, ad)),
    el("p", { class: "ipucu kucuk-ipucu" }, metin),
    b.stillmore ? null : el("button", { class: "dugme ikincil bulucu-baglan", type: "button", disabled: suruyor, onclick: () => spotifyBaglan() },
      b.spotify ? "Spotify'a bağlan" : "Spotify'ı aç ve bağlan"),
    el("p", { class: "ipucu kucuk-ipucu bulucu-not" }, "Köprü yalnız bu bilgisayardan erişilir; gece keşfi de aynı köprüyle tarar."));
}

function gecmisPaneli(liste) {
  return el("section", { class: "cam yan-panel", "aria-label": "Son aramalar" }, el("h2", {}, "Son aramalar"),
    liste.length ? el("ul", { class: "gecmis-liste" }, ...liste.slice(0, 14).map((x) => el("li", {},
      el("button", { type: "button", "aria-current": x.anahtar === bulucuAcik ? "true" : false,
        onclick: () => { bulucuAcik = x.anahtar; depo.yaz("bulucu.acik", x.anahtar); bulucuGoster(); scrollTo(0, 0); } },
        disKapak(x.resim, "kapak-kucuk"),
        el("span", { class: "ad" }, x.ad || "—"),
        el("span", { class: "alt" }, el("span", { class: "tur-etiket" }, BTUR[x.tur] || x.tur), x.sayi ? el("span", {}, x.sayi) : null, el("span", {}, saatDakika(x.zaman)))))))
      : el("p", { class: "ipucu kucuk-ipucu" }, "Henüz arama yok."));
}

function izlenenPaneli(liste, suruyor) {
  const kaynak = (k) => k === "bulucu" ? "senin eklediğin" : k === "config" ? "ayarlardan" : k?.startsWith("arama:") ? `arama: ${k.slice(6)}` : k || "";
  const satir = (x) => el("li", {},
    el("div", { class: "izlenen-ad" }, el("span", { class: "ad" }, x.ad), el("span", { class: "alt" },
      x.son_tarama ? `${tarih(x.son_tarama)} · ${x.calinamayan ?? 0} kalkmış · ${x.aday ?? 0} aday` : "henüz taranmadı",
      x.kaynak ? ` · ${kaynak(x.kaynak)}` : "")),
    el("button", { class: "dugme kucuk", type: "button", disabled: suruyor, onclick: () => kayitAc("playlist", x.id), "aria-label": `${x.ad} listesini aç` }, "Aç"));
  const ilk = liste.slice(0, 8), kalan = liste.slice(8);
  return el("section", { class: "cam yan-panel", "aria-label": "Gece taranan playlist'ler" }, el("h2", {}, "Gece taranan listeler"),
    el("p", { class: "ipucu kucuk-ipucu bulucu-not" }, `Gece keşfi bu havuzdan her gece birkaç listeyi STILLMORE'la tarar (${liste.length} liste). Bir playlist sonucunda "Gece taransın"ı açınca buraya girer.`),
    liste.length ? el("ul", { class: "izlenen-liste" }, ...ilk.map(satir)) : null,
    kalan.length ? el("details", { class: "izlenen-tumu" }, el("summary", {}, `${kalan.length} liste daha`), el("ul", { class: "izlenen-liste" }, ...kalan.map(satir))) : null);
}

function sonucCiz(v, suruyor) {
  const ciz = { playlist: playlistSonuc, parca: parcaSonuc, sanatci: sanatciSonuc, katalog: katalogSonuc, album: albumSonuc, isrc: aramaSonuc, upc: aramaSonuc, listeler: listelerSonuc }[v.tur];
  return ciz ? ciz(v, suruyor) : el("p", { class: "bos-kutu" }, "Bu kayıt okunamadı.");
}

// liste keşfi: konu sorgularıyla bulunan playlist'ler, en çok takipçili önce; her biri tek tıkla taranır
function listelerSonuc(v, suruyor) {
  const sahipSpotify = (p) => (p.sahip || "").toLowerCase() === "spotify";
  return el("section", { class: "bulucu-sonuc", "aria-label": v.ad },
    sonucBasi(v, `${v.sonuclar.length} liste · ${v.sorgular.length} aramadan · en çok takipçili önce`,
      [yenidenOku(v, suruyor, "Yeniden ara")]),
    el("p", { class: "ipucu" }, "Taramak istediğin listede \"Tara\"ya bas: kalkmış şarkıları dinlenmeleriyle çıkar. Spotify'ın kendi listeleri (editoryal) işaretli."),
    v.sonuclar.length ? el("ul", { class: "kayitlar" }, ...v.sonuclar.map((p) => el("li", { class: "kayit kapakli" },
      disKapak(p.resim),
      el("div", { class: "kayit-ad" },
        el("button", { class: "ad bag-dugme", type: "button", disabled: suruyor, onclick: () => p.tarandi ? kayitAc("playlist", p.id) : bulucuAc("playlist", p.id) }, p.ad),
        el("span", { class: "sanatci" }, p.sahip || "—")),
      el("div", { class: "olculer" },
        el("span", { title: "Takipçi" }, "takipçi ", el("b", {}, kisaSayi(p.takipci))),
        p.toplam != null ? el("span", {}, el("b", {}, String(p.toplam)), " parça") : null,
        sahipSpotify(p) ? el("span", { class: "rozet gumus", title: "Spotify'ın editoryal listesi" }, "Spotify") : null,
        p.tarandi ? el("span", { class: "rozet " + (p.tarandi.kalkmis ? "amber" : "") }, `tarandı · ${p.tarandi.kalkmis} kalkmış`) : null),
      el("div", { class: "kayit-eylem" },
        spLink("playlist", p.id),
        p.tarandi ? el("button", { class: "dugme kucuk", type: "button", disabled: suruyor, onclick: () => kayitAc("playlist", p.id) }, "Aç")
          : el("button", { class: "dugme kucuk", type: "button", disabled: suruyor, onclick: () => bulucuAc("playlist", p.id) }, "Tara")))))
      : el("p", { class: "bos-kutu" }, "Liste bulunamadı; Spotify köprüsünü yeniden bağlayıp tekrar dene."));
}

function konuPaneli(konular, bagli, suruyor) {
  if (!konular?.length) return null;
  return el("section", { class: "cam yan-panel", "aria-label": "Liste keşfi" }, el("h2", {}, "Liste keşfi"),
    el("p", { class: "ipucu kucuk-ipucu" }, "Konuya göre popüler playlist'leri bulur (Spotify'ın kendi araması, kota harcamaz); en çok takipçili önce, her biri tek tıkla taranır."),
    ...konular.map((k) => el("button", { class: "dugme ikincil kucuk genis-dugme", type: "button", disabled: !bagli || suruyor || null,
      onclick: () => kayitAc("listeler", k.kimlik) }, `${k.ad} listelerini bul`)));
}

// sonucun başı: kapak, ad, alt satır, eylemler
function sonucBasi(v, alt, eylemler, yuvarlak = false) {
  return el("header", { class: "sonuc-ust" },
    v.resim ? el("img", { class: "sonuc-kapak" + (yuvarlak ? " yuvarlak" : ""), src: v.resim, alt: "", referrerpolicy: "no-referrer", width: 112, height: 112 })
      : el("span", { class: "sonuc-kapak bos", "aria-hidden": "true" }, dalgaIsareti(28)),
    el("div", { class: "sonuc-kimlik" },
      el("p", { class: "ust-satir ipucu" }, el("span", { class: "tur-etiket" }, BTUR[v.tur]), v.zaman ? el("span", {}, `okundu ${saatDakika(v.zaman)}`) : null),
      el("h2", { class: "sonuc-ad" }, v.ad || v.id),
      alt ? el("p", { class: "ipucu sonuc-alt" }, alt) : null,
      el("div", { class: "sonuc-eylem" }, ...eylemler.filter(Boolean))));
}
const yenidenOku = (v, suruyor, metin = "Yeniden oku") => el("button", { class: "dugme kucuk", type: "button", disabled: suruyor, onclick: () => bulucuAc(v.tur, v.id) }, metin);

function yankiRozeti(y) {
  if (!y) return null;
  if (y.listede) return el("span", { class: "rozet ok", title: "Şarkı listede ya da hatta" }, "listede");
  if (y.duzenleme) return el("span", { class: "rozet", title: "Remix, sped up gibi düzenlemeler keşifte sorulmaz" }, "düzenleme");
  if (y.hal) return el("span", { class: "rozet " + (y.puan ? "gumus" : "no"), title: "Keşif kaydındaki hali" }, `keşif: ${y.hal}${y.puan ? ` · ${kisaSayi(y.puan)}` : ""}`);
  if (y.gonderildi) return el("span", { class: "rozet gumus", title: "Gece keşfi bu gece ölçecek" }, "keşfe gönderildi");
  return null;
}

async function kesfeGonder(v, idler, dugme) {
  if (dugme) { dugme.disabled = true; dugme.setAttribute("aria-busy", "true"); }
  try {
    const r = await api("/api/bulucu/kesfe", { anahtar: v.anahtar, parcalar: idler });
    bildir(r.eklenen ? `${r.eklenen} şarkı keşfe gönderildi; gece keşfi ölçüp uyanı listeye alır.${r.atlanan ? ` ${r.atlanan} tanesi zaten gönderilmişti.` : ""}` : "Seçilenler zaten keşfe gönderilmiş.");
  } catch (e) { bildir(e.message, true); }
  bulucuGoster();
}

const PL_SUZGEC = {
  bosluk: { ad: "Boşluk var", f: (x) => !x.kopyalar.length, bos: "Bütün kalkmış şarkıların çalınan bir kopyası var: boşluk yok." },
  kopya: { ad: "Yeniden yüklenmiş", f: (x) => x.kopyalar.length > 0, bos: "Yeniden yüklenmiş şarkı yok." },
  hepsi: { ad: "Tümü", f: () => true, bos: "Bu listede kalkmış şarkı yok." },
};

function playlistSonuc(v, suruyor) {
  const satirlar = [...v.satirlar].sort((a, b) => (b.dinlenme ?? -1) - (a.dinlenme ?? -1));
  const bosluk = satirlar.filter(PL_SUZGEC.bosluk.f);
  const gonderilebilir = bosluk.filter((x) => !(x.yanki?.listede || x.yanki?.hal || x.yanki?.gonderildi || x.yanki?.duzenleme));
  const gorunen = satirlar.filter(PL_SUZGEC[bulucuSuzgec].f);
  const izle = el("button", { class: "anahtar", type: "button", role: "switch", "aria-checked": v.izleniyor ? "true" : "false", "aria-labelledby": "izle-ad",
    onclick: async () => {
      try { await api("/api/bulucu/izle", { playlist: v.id, izle: !v.izleniyor }); bildir(v.izleniyor ? "Liste gece taramasından çıkarıldı." : "Liste gece taramasına alındı; keşif haftada bir tarar."); }
      catch (e) { bildir(e.message, true); }
      bulucuGoster();
    } }, el("span", { "aria-hidden": "true" }));
  const csvIndir = () => {
    const q = (s) => { s = s == null ? "" : String(s); return /[",;\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
    const sut = [["Parça", (x) => x.ad], ["Sanatçı", (x) => x.sanatci], ["Dinlenme", (x) => x.dinlenme], ["Durum", (x) => x.neden === "country" ? "Ülkende kapalı" : "Kaldırılmış"],
      ["Distribütör", (x) => x.distributor], ["ISRC", (x) => x.isrc], ["Çıkış", (x) => x.cikis], ["Yeniden yüklenmiş", (x) => x.kopyalar.map((k) => k.id).join(" ")], ["Spotify ID", (x) => x.id]];
    const metin = "﻿" + [sut.map((s) => q(s[0])).join(","), ...satirlar.map((x) => sut.map((s) => q(s[1](x))).join(","))].join("\n");
    const a = el("a", { href: URL.createObjectURL(new Blob([metin], { type: "text/csv" })), download: `${(v.ad || v.id).replace(/[\\/:*?"<>|]+/g, " ").trim()} - kalkmis.csv` });
    a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  };
  const toplamDinlenme = satirlar.reduce((n, x) => n + (x.dinlenme || 0), 0);
  return el("section", { class: "bulucu-sonuc", "aria-label": `${v.ad} taraması` },
    sonucBasi(v, [v.sahip, `${tamSayi(v.toplam)} parça`, v.takipci ? `${kisaSayi(v.takipci)} beğeni` : null].filter(Boolean).join(" · "),
      [spLink("playlist", v.id), yenidenOku(v, suruyor, "Yeniden tara"), satirlar.length ? el("button", { class: "dugme kucuk", type: "button", onclick: csvIndir }, "CSV indir") : null]),
    el("div", { class: "sonuc-olcu cam" },
      el("div", {}, el("span", { class: "olcu-sayi gumus-yazi" }, String(satirlar.length)), el("span", { class: "olcu-ad" }, "kalkmış")),
      el("div", {}, el("span", { class: "olcu-sayi" + (bosluk.length ? " gumus-yazi" : "") }, String(bosluk.length)), el("span", { class: "olcu-ad" }, "boşluk var")),
      el("div", {}, el("span", { class: "olcu-sayi" }, kisaSayi(toplamDinlenme)), el("span", { class: "olcu-ad" }, "toplam dinlenme")),
      el("div", { class: "ayar-satir izle-satir" }, el("div", {}, el("b", { id: "izle-ad" }, "Gece taransın"),
        el("p", { class: "ipucu" }, v.izleniyor ? "Gece keşfi bu listeyi haftada bir tarar." : "Açınca gece keşfi haftada bir tarar.")), izle)),
    satirlar.length ? el("div", { class: "kesitler", role: "group", "aria-label": "Süzgeç" }, ...Object.entries(PL_SUZGEC).map(([k, s]) =>
      el("button", { class: "kesit", type: "button", "aria-pressed": k === bulucuSuzgec ? "true" : "false", onclick: () => { bulucuSuzgec = k; bulucuGoster(); } },
        s.ad, el("span", { class: "kesit-zaman" }, String(satirlar.filter(s.f).length)))),
      gonderilebilir.length && bulucuSuzgec !== "kopya" ? el("button", { class: "dugme ikincil kucuk toplu", type: "button", onclick: (e) => kesfeGonder(v, gonderilebilir.map((x) => x.id), e.currentTarget) },
        `Boşluğu olanları keşfe gönder (${gonderilebilir.length})`) : null) : null,
    gorunen.length ? el("ul", { class: "kayitlar" }, ...gorunen.map((x) => kalkmisSatiri(v, x, suruyor)))
      : el("p", { class: "bos-kutu" }, PL_SUZGEC[bulucuSuzgec].bos));
}

function kalkmisSatiri(v, x, suruyor) {
  const p = pencereYazi(x.pencere);
  const y = x.yanki;
  const gonderilir = !x.kopyalar.length && !(y?.listede || y?.hal || y?.gonderildi || y?.duzenleme);
  return el("li", { class: "kayit kapakli" + (x.kopyalar.length ? " soluk" : "") },
    disKapak(x.resim),
    el("div", { class: "kayit-ad" },
      el("button", { class: "ad bag-dugme", type: "button", disabled: suruyor, onclick: () => kayitAc("parca", x.id), title: "Parçanın ayrıntısı" }, x.ad),
      el("span", { class: "sanatci" }, x.sanatci, x.sanatci_dinleyici != null ? ` · ${kisaSayi(x.sanatci_dinleyici)} aylık dinleyici` : "")),
    el("div", { class: "olculer" },
      el("span", { title: "Kalkmadan önceki Spotify dinlenmesi" }, "dinlenme ", el("b", {}, kisaSayi(x.dinlenme))),
      el("span", { class: "rozet " + (x.neden === "country" ? "amber" : "no") }, x.neden === "country" ? "ülkende kapalı" : "kalktı"),
      p ? el("span", { class: `rozet ${p[1]}`, title: "Spotify kalkmış şarkının sayacını 90 gün tutar" }, p[0]) : null,
      x.distributor ? el("span", { title: "Kalkmadan önceki distribütör" }, el("b", {}, x.distributor)) : null,
      x.cikis ? el("span", { title: "Çıkış tarihi" }, x.cikis.slice(0, 4)) : null,
      x.isrc ? el("code", { title: "ISRC" }, x.isrc) : null,
      x.kopyalar.length ? el("span", { class: "rozet gumus", title: x.kopyalar.map((k) => [k.album, k.distributor].filter(Boolean).join(" · ")).join("\n") },
        `${x.kopyalar.length} çalınan kopya`) : null,
      yankiRozeti(y)),
    el("div", { class: "kayit-eylem" },
      x.kopyalar.length ? spLink("parca", x.kopyalar[0].id, "Kopyayı aç") : null,
      gonderilir ? el("button", { class: "dugme ikincil kucuk", type: "button", title: "Orvane'in AI cover hattına", onclick: (e) => kesfeGonder(v, [x.id], e.currentTarget) }, "Keşfe gönder") : null,
      el("a", { class: "dugme kucuk", href: `https://www.youtube.com/results?search_query=${encodeURIComponent(`${x.sanatci} ${x.ad}`)}`, target: "_blank", rel: "noopener" }, "Dinle")));
}

function bilgi(ad, deger, ek) {
  if (deger == null || deger === "" || (Array.isArray(deger) && !deger.length)) return [];
  return [el("dt", {}, ad), el("dd", {}, Array.isArray(deger) ? deger.join(", ") : deger, ek ? el("span", { class: "ipucu" }, ek) : null)];
}

function parcaSonuc(v, suruyor) {
  const p = pencereYazi(v.pencere);
  const y = v.yanki;
  const kalkmis = v.calinir === false;
  const ib = v.isrc_bilgi;
  return el("section", { class: "bulucu-sonuc", "aria-label": `${v.ad} ayrıntısı` },
    sonucBasi(v, null, [spLink("parca", v.id), yenidenOku(v, suruyor),
      kalkmis && !(y?.listede || y?.hal || y?.gonderildi || y?.duzenleme) && !v.kopyalar.some((k) => k.calinir !== false)
        ? el("button", { class: "dugme ikincil kucuk", type: "button", onclick: (e) => kesfeGonder(v, [v.id], e.currentTarget) }, "Keşfe gönder") : null]),
    el("div", { class: "parca-sanatcilar" },
      ...(v.sanatcilar.length ? v.sanatcilar : [{ id: null, name: v.sanatci }]).map((s) => s.id
        ? el("button", { class: "dugme kucuk", type: "button", disabled: suruyor, onclick: () => kayitAc("sanatci", s.id) }, s.name) : el("span", { class: "ipucu" }, s.name)),
      v.album_id ? el("button", { class: "dugme kucuk", type: "button", disabled: suruyor, onclick: () => kayitAc("album", v.album_id) }, `Albüm: ${v.album}`) : null),
    el("div", { class: "cipler" },
      el("span", { class: "rozet " + (kalkmis ? "no" : v.calinir ? "ok" : "") }, kalkmis ? `çalınamıyor${v.calinma_nedeni ? ` · ${v.calinma_nedeni.toLowerCase().replace(/_/g, " ")}` : ""}` : v.calinir ? "çalınabilir" : "çalınabilirlik bilinmiyor"),
      p && kalkmis ? el("span", { class: `rozet ${p[1]}`, title: "Spotify kalkmış şarkının sayacını 90 gün tutar" }, p[0]) : null,
      v.acik_icerik ? el("span", { class: "rozet amber" }, "açık içerik") : null,
      v.album_turu ? el("span", { class: "rozet" }, v.album_turu) : null,
      yankiRozeti(y)),
    el("div", { class: "sonuc-olcu cam" },
      el("div", {}, el("span", { class: "olcu-sayi gumus-yazi" }, kisaSayi(v.dinlenme)), el("span", { class: "olcu-ad" }, `dinlenme${v.dinlenme != null ? ` · ${tamSayi(v.dinlenme)}` : ""}`)),
      el("div", { class: "olcu-dist" }, el("span", { class: "olcu-sayi kucuk" }, v.distributor || "bilinmiyor"), el("span", { class: "olcu-ad" }, `distribütör · ${v.guven}`))),
    el("dl", { class: "bilgi-izgara" },
      ...bilgi("ISRC", v.isrc, ib ? ` ${[ib.ulke, ib.kayit, ib.yil].filter(Boolean).join(" · ")}` : null),
      ...bilgi("UPC", v.upc),
      ...bilgi("Label", v.label),
      ...bilgi("Çıkış", v.cikis), ...bilgi("İlk yayın", v.ilk_yayin),
      ...bilgi("Süre", v.sure_ms ? sure(v.sure_ms / 1000) : null),
      ...bilgi("Tempo", v.tempo ? `${Math.round(v.tempo)} BPM` : null), ...bilgi("Ton", v.ton),
      ...bilgi("Dil", v.diller),
      ...bilgi("Yazarlar", belgeli(v.yazarlar)), ...bilgi("Yapımcılar", belgeli(v.yapimcilar)),
      ...bilgi("Pazar", v.pazar), ...bilgi("℗", v.telif_p), ...bilgi("©", v.telif_c),
      ...bilgi("Licensor", v.licensor ? el("code", {}, v.licensor) : null),
      ...bilgi("Öneri", v.oneri, " credits kaynak satırı")),
    el("div", { class: "satir-ici bulucu-arac" },
      v.isrc ? kopyaDugmesi(v.isrc, "ISRC") : null, v.isrc ? el("button", { class: "dugme kucuk", type: "button", disabled: suruyor, onclick: () => kayitAc("isrc", v.isrc) }, "ISRC'yi ara") : null,
      v.upc ? kopyaDugmesi(v.upc, "UPC") : null, v.upc ? el("button", { class: "dugme kucuk", type: "button", disabled: suruyor, onclick: () => kayitAc("upc", v.upc) }, "UPC'yi ara") : null),
    v.kopyalar.length ? el("section", { class: "bolum" }, el("h2", { class: "bolum-baslik" }, "Aynı ISRC'li yüklemeler", el("span", { class: "g-sayi" }, String(v.kopyalar.length))),
      el("ul", { class: "kayitlar" }, ...v.kopyalar.map((k) => el("li", { class: "kayit kapakli" },
        disKapak(k.resim), el("div", { class: "kayit-ad" }, el("span", { class: "ad" }, k.ad), el("span", { class: "sanatci" }, k.sanatci)),
        el("div", { class: "olculer" }, el("span", { class: "duz" }, k.album), el("span", { class: "rozet " + (k.calinir === false ? "no" : "ok") }, k.calinir === false ? "çalınamıyor" : "çalınıyor")),
        el("div", { class: "kayit-eylem" }, el("button", { class: "dugme kucuk", type: "button", disabled: suruyor, onclick: () => kayitAc("parca", k.id) }, "Ayrıntı"), spLink("parca", k.id, "Aç")))))) : null);
}

function sanatciSonuc(v, suruyor) {
  const enCok = Math.max(1, ...v.sehirler.map((s) => s.dinleyici || 0));
  return el("section", { class: "bulucu-sonuc", "aria-label": `${v.ad} özeti` },
    sonucBasi(v, [v.dogrulanmis ? "doğrulanmış sanatçı" : null, v.yayin_sayisi != null ? `${v.yayin_sayisi} yayın (${v.album_sayisi ?? 0} albüm, ${v.single_sayisi ?? 0} single)` : null].filter(Boolean).join(" · "),
      [spLink("sanatci", v.id), yenidenOku(v, suruyor),
        el("button", { class: "dugme ikincil kucuk", type: "button", disabled: suruyor, onclick: () => kayitAc("katalog", v.id), title: "Her yayının distribütörü, dinlenmesi ve aynı ISRC'li kopyalar; büyük katalogda birkaç dakika" }, "Kataloğu tara")], true),
    el("div", { class: "sonuc-olcu cam" },
      el("div", {}, el("span", { class: "olcu-sayi gumus-yazi" }, kisaSayi(v.dinleyici)), el("span", { class: "olcu-ad" }, "aylık dinleyici")),
      el("div", {}, el("span", { class: "olcu-sayi" }, kisaSayi(v.takipci)), el("span", { class: "olcu-ad" }, "takipçi")),
      v.dunya_sirasi ? el("div", {}, el("span", { class: "olcu-sayi" }, `#${v.dunya_sirasi}`), el("span", { class: "olcu-ad" }, "dünya sırası")) : null,
      v.son_yayin ? el("div", { class: "olcu-dist" }, el("button", { class: "bag-dugme olcu-sayi kucuk", type: "button", disabled: suruyor, onclick: () => kayitAc("album", v.son_yayin.id) }, v.son_yayin.ad),
        el("span", { class: "olcu-ad" }, `son yayın · ${[v.son_yayin.tur, v.son_yayin.tarih].filter(Boolean).join(" · ").toLowerCase()}`)) : null),
    v.sehirler.length ? el("section", { class: "bolum" }, el("h2", { class: "bolum-baslik" }, "En çok dinlenen şehirler"),
      el("ul", { class: "cubuklar sehirler" }, ...v.sehirler.map((s) => el("li", {}, el("span", {}, `${s.sehir}, ${s.ulke}`), el("b", {}, kisaSayi(s.dinleyici)),
        el("span", { class: "cubuk" }, el("i", { style: { width: `${Math.round(100 * (s.dinleyici || 0) / enCok)}%` } })))))) : null,
    v.listeler.length ? el("section", { class: "bolum" }, el("h2", { class: "bolum-baslik" }, "Yer aldığı listeler", el("span", { class: "g-sayi" }, String(v.listeler.length))),
      el("p", { class: "ipucu bolum-not" }, "Sanatçının dinleyicilerinin bulduğu listeler. Tara: içindeki kalkmış şarkılar."),
      el("ul", { class: "kayitlar" }, ...v.listeler.map((l) => el("li", { class: "kayit kapakli" }, disKapak(l.resim),
        el("div", { class: "kayit-ad" }, el("span", { class: "ad" }, l.ad), el("span", { class: "sanatci" }, l.sahip)), el("div", { class: "olculer" }),
        el("div", { class: "kayit-eylem" }, el("button", { class: "dugme ikincil kucuk", type: "button", disabled: suruyor, onclick: () => kayitAc("playlist", l.id) }, "Tara"), spLink("playlist", l.id, "Aç")))))) : null);
}

function katalogSonuc(v, suruyor) {
  const dist = {};
  v.yayinlar.forEach((y) => y.parcalar.forEach((t) => { const k = t.distributor || "bilinmiyor"; dist[k] = (dist[k] || 0) + 1; }));
  const distSira = Object.entries(dist).sort((a, b) => b[1] - a[1]);
  const enCok = Math.max(1, ...distSira.map((x) => x[1]));
  const yayinDist = (y) => { const c = {}; y.parcalar.forEach((t) => { const k = t.distributor || "bilinmiyor"; c[k] = (c[k] || 0) + 1; }); return Object.entries(c).sort((a, b) => b[1] - a[1])[0]?.[0]; };
  return el("section", { class: "bulucu-sonuc", "aria-label": `${v.ad} kataloğu` },
    sonucBasi(v, `${v.yayinlar.length} yayın · ${tamSayi(v.parca_sayisi)} parça`, [spLink("katalog", v.id), yenidenOku(v, suruyor, "Yeniden tara"),
      el("button", { class: "dugme kucuk", type: "button", disabled: suruyor, onclick: () => kayitAc("sanatci", v.id) }, "Sanatçı özeti")], true),
    el("div", { class: "sonuc-olcu cam" },
      el("div", {}, el("span", { class: "olcu-sayi gumus-yazi" }, kisaSayi(v.toplam_dinlenme)), el("span", { class: "olcu-ad" }, "toplam dinlenme")),
      el("div", {}, el("span", { class: "olcu-sayi" }, v.ortalama_ara != null ? `${v.ortalama_ara} gün` : "—"), el("span", { class: "olcu-ad" }, "yayın arası (ort.)")),
      el("div", {}, el("span", { class: "olcu-sayi" }, v.son_yayindan != null ? `${v.son_yayindan} gün` : "—"), el("span", { class: "olcu-ad" }, "son yayından beri"))),
    el("section", { class: "bolum" }, el("h2", { class: "bolum-baslik" }, "Distribütörler (parça sayısı)"),
      el("ul", { class: "cubuklar" }, ...distSira.map(([ad, n]) => el("li", {}, el("span", {}, ad), el("b", {}, String(n)),
        el("span", { class: "cubuk" }, el("i", { style: { width: `${Math.round(100 * n / enCok)}%` } })))))),
    v.zaman_cizelgesi.length > 1 ? el("details", { class: "stil-duzen katlanir" }, el("summary", {}, "Yıllara göre distribütör (yayın sayısı)"),
      el("ul", { class: "olaylar" }, ...v.zaman_cizelgesi.map((y) => el("li", {}, el("span", { class: "olay-zaman" }, y.yil),
        el("span", {}, y.dagilim.map((d) => `${d.ad} ${d.sayi}`).join(" · ")))))) : null,
    v.kopyalar.length ? el("details", { class: "stil-duzen katlanir" }, el("summary", {}, `Birden çok kez yüklenenler (${v.kopyalar.length})`),
      el("p", { class: "ipucu kucuk-ipucu" }, "Aynı ISRC ya da aynı ses dosyası birden çok yayında: derleme, yeniden basım ya da kopya."),
      el("ul", { class: "olaylar" }, ...v.kopyalar.slice(0, 60).map((k) => el("li", {}, el("span", { class: "olay-zaman" }, k.tur === "isrc" ? "aynı ISRC" : "aynı ses"),
        el("span", {}, k.parcalar.map((t) => `${t.ad}${t.yayin ? ` (${t.yayin})` : ""}`).join(" · ")))))) : null,
    el("section", { class: "bolum" }, el("h2", { class: "bolum-baslik" }, "Yayınlar", el("span", { class: "g-sayi" }, String(v.yayinlar.length))),
      el("ul", { class: "kayitlar" }, ...v.yayinlar.map((y) => el("li", { class: "kayit kapakli katalog-yayin" }, disKapak(y.resim),
        el("div", { class: "kayit-ad" }, el("button", { class: "ad bag-dugme", type: "button", disabled: suruyor, onclick: () => kayitAc("album", y.id) }, y.ad),
          el("span", { class: "sanatci" }, [y.tur?.toLowerCase(), y.tarih].filter(Boolean).join(" · "))),
        el("div", { class: "olculer" }, el("span", {}, "dinlenme ", el("b", {}, kisaSayi(y.parcalar.reduce((n, t) => n + (t.dinlenme || 0), 0)))),
          yayinDist(y) ? el("span", {}, el("b", {}, yayinDist(y))) : null, y.label ? el("span", { class: "duz" }, y.label) : null, y.upc ? el("code", { title: "UPC" }, y.upc) : null),
        el("div", { class: "kayit-eylem" }, spLink("album", y.id, "Aç")))))));
}

function albumSonuc(v, suruyor) {
  return el("section", { class: "bulucu-sonuc", "aria-label": `${v.ad} albümü` },
    sonucBasi(v, [v.sanatci, v.album_turu, v.cikis, v.label].filter(Boolean).join(" · "), [spLink("album", v.id), yenidenOku(v, suruyor), v.upc ? kopyaDugmesi(v.upc, "UPC") : null]),
    el("dl", { class: "bilgi-izgara" }, ...bilgi("UPC", v.upc), ...bilgi("Label", v.label), ...bilgi("Çıkış", v.cikis), ...bilgi("℗", v.telif_p)),
    el("section", { class: "bolum" }, el("h2", { class: "bolum-baslik" }, "Parçalar", el("span", { class: "g-sayi" }, String(v.satirlar.length))),
      el("ul", { class: "kayitlar" }, ...v.satirlar.map((t) => el("li", { class: "kayit" },
        el("div", { class: "kayit-ad" }, el("button", { class: "ad bag-dugme", type: "button", disabled: suruyor, onclick: () => kayitAc("parca", t.id) }, `${t.no}. ${t.ad}`),
          el("span", { class: "sanatci" }, t.sanatci)),
        el("div", { class: "olculer" }, el("span", {}, "dinlenme ", el("b", {}, kisaSayi(t.dinlenme))), t.distributor ? el("span", {}, el("b", {}, t.distributor)) : null,
          t.isrc ? el("code", { title: "ISRC" }, t.isrc) : null),
        el("div", { class: "kayit-eylem" }, spLink("parca", t.id, "Aç")))))));
}

function aramaSonuc(v, suruyor) {
  return el("section", { class: "bulucu-sonuc", "aria-label": `${v.tur} araması` },
    sonucBasi(v, `${v.sonuclar.length} sonuç`, [yenidenOku(v, suruyor, "Yeniden ara"), kopyaDugmesi(v.id, BTUR[v.tur])]),
    v.sonuclar.length ? el("ul", { class: "kayitlar" }, ...v.sonuclar.map((x) => el("li", { class: "kayit kapakli" }, disKapak(x.resim),
      el("div", { class: "kayit-ad" }, el("span", { class: "ad" }, x.ad), el("span", { class: "sanatci" }, x.sanatci)),
      el("div", { class: "olculer" }, x.album ? el("span", { class: "duz" }, x.album) : null,
        x.calinir == null ? null : el("span", { class: "rozet " + (x.calinir ? "ok" : "no") }, x.calinir ? "çalınıyor" : "çalınamıyor")),
      el("div", { class: "kayit-eylem" }, el("button", { class: "dugme kucuk", type: "button", disabled: suruyor, onclick: () => kayitAc(x.tur, x.id) }, "Ayrıntı"), spLink(x.tur, x.id, "Aç")))))
      : el("p", { class: "bos-kutu" }, v.tur === "upc"
        ? "Spotify araması bu UPC'ye sonuç vermedi. Albüm henüz yayında olmayabilir ya da kalkmış olabilir; Spotify'ın UPC araması her albümü de bulmuyor. Albüm linkiyle dene."
        : "Spotify araması bu ISRC'ye sonuç vermedi: parça yayında değil ya da kalkmış."));
}

// ---- yükle: elle yayın taslağı (yanki/elle.py). Form kendiliğinden kaydedilir; gönderim RouteNote'a tarayıcıyla ----
const ELLE_HAL = {
  taslak: ["taslak", ""], rn_taslak: ["RouteNote'ta taslak", "amber"], kontrol: ["gönderim yarıda", "amber"], gonderildi: ["gönderildi", "ok"],
};
let elleAcik, elleSecenek = null, elleKayit = null, elleIzle = null, elleIs = null; // elleKayit: { kimlik, zaman }
const elleAdi = (m) => m.baslik || "Adsız taslak";

async function yukleGoster() {
  await elleBekleyeniGonder(); // ekran sunucudaki hâlle yeniden kurulmadan önce
  const ana = $("#ana");
  let d;
  try { d = await api("/api/elle"); } catch (e) { doldur(ana, bosEkran("Yükleme açılamadı", e.message)); return; }
  elleSecenek = d.secenek;
  // oda açılınca son taslak değil liste (oluşturma düğmeleriyle); taslak bir bağlantı ya da kenar listesiyle açılır
  if (elleAcik === undefined) elleAcik = null;
  if (elleAcik && !d.liste.some((x) => x.kimlik === elleAcik)) { elleAcik = null; depo.yaz("elle.acik", null); }
  $("#g-yukle").textContent = d.is?.suruyor && String(d.is.ad || "").startsWith("elle") ? "•" : "";
  if (elleAcik) return elleDuzenle(elleAcik, d.is);
  const yeni = el("button", { class: "dugme ikincil", type: "button", title: "Dağıtıcıyı kendin seçtiğin boş taslak (RouteNote ya da elle paket)", onclick: async (e) => {
    e.currentTarget.disabled = true;
    try { const m = await api("/api/elle", { baslik: "" }); elleAc(m.kimlik); } catch (err) { bildir(err.message, true); e.currentTarget.disabled = false; }
  } }, "Boş taslak");
  const kendi = el("button", { class: "dugme birincil", type: "button", title: "Senin adınla, yapay zekâsız, FreshTunes'ta (Orvane'den ayrı)", onclick: async (e) => {
    e.currentTarget.disabled = true;
    try { const m = await api("/api/elle", { baslik: "", sablon: "freshtunes" }); elleAc(m.kimlik); } catch (err) { bildir(err.message, true); e.currentTarget.disabled = false; }
  } }, "Yeni şarkı (FreshTunes)");
  doldur(ana,
    el("header", { class: "pano-ust" },
      el("div", {}, el("h1", {}, "Taslaklar"),
        el("p", { class: "ipucu" }, "Kendi yayınlarının taslakları. Bilgileri doldur, sesi ve kapağı seç, FreshTunes paketini indir. Kalkmış yayınlarından açılan taslaklar sesi, kapağı ve ISRC'yi kendiliğinden bulur.")),
      el("div", { class: "satir-ici" }, yeni, kendi)),
    d.freshtunes?.hatirlat ? ftHesapSeridi(d.freshtunes, yukleGoster) : null,
    d.bos ? el("p", { class: "ipucu ft-serit" }, `${d.bos} taslak boş (adı, sesi, kapağı yok).`,
      el("button", { class: "dugme ikincil kucuk", type: "button", onclick: () => {
        const dlg = pencere(`${d.bos} boş taslak silinsin mi?`, [el("p", { class: "ipucu" }, "Yalnız hiçbir şey girilmemiş taslaklar silinir: adı, sesi, kapağı ve dağıtıcı kaydı olmayanlar. Geri alınamaz.")], [
          el("button", { class: "dugme", type: "button", onclick: () => dlg.close() }, "Vazgeç"),
          el("button", { class: "dugme tehlike dolu", type: "button", onclick: async () => {
            dlg.close();
            try { bildir(`${(await api("/api/elle-bos-temizle", {})).silinen} boş taslak silindi.`); } catch (e) { bildir(e.message, true); }
            yukleGoster(); taslakListesiCiz();
          } }, "Boş taslakları sil")]);
      } }, "Boş taslakları sil")) : null,
    d.liste.length ? el("ul", { class: "kayitlar" }, ...d.liste.map((x) => el("li", { class: "kayit kapakli" },
      x.kapak ? el("img", { class: "kapak-kucuk kapak-orta", src: `/elle/${x.kimlik}/kapak?boyut=96`, alt: "", width: 44, height: 44 }) : el("span", { class: "kapak-kucuk kapak-orta bos", "aria-hidden": "true" }, dalgaIsareti()),
      el("div", { class: "kayit-ad" }, el("button", { class: "ad bag-dugme", type: "button", onclick: () => elleAc(x.kimlik) }, x.baslik), el("span", { class: "sanatci" }, x.sanatci || "—")),
      el("div", { class: "olculer" },
        el("span", { class: `rozet ${ELLE_HAL[x.hal][1]}` }, ELLE_HAL[x.hal][0]),
        el("span", {}, x.dagiticilar.map((k) => elleSecenek.dagiticilar[k]?.ad || k).join(" · ") || "dağıtıcı yok"),
        x.upc ? el("code", { title: "UPC" }, x.upc) : null, x.isrc ? el("code", { title: "ISRC" }, x.isrc) : null,
        !x.ses || !x.kapak ? el("span", { class: "rozet amber" }, !x.ses && !x.kapak ? "ses ve kapak yok" : !x.ses ? "ses yok" : "kapak yok") : null,
        el("span", {}, "güncel ", el("b", {}, tarih(x.guncel)))),
      el("div", { class: "kayit-eylem" }, el("button", { class: "dugme kucuk", type: "button", onclick: () => elleAc(x.kimlik) }, "Aç")))))
      : el("section", { class: "bos-kutu bulucu-bos" }, el("h2", { class: "bolum-baslik" }, "Henüz taslak yok"),
        el("ul", { class: "bulucu-ornekler" },
          el("li", {}, "\"Yeni yayın\"la bir taslak aç; yazdıkça kendiliğinden kaydedilir, istediğin zaman dönersin."),
          el("li", {}, "Sesi WAV, FLAC, AIFF ya da MP3 olarak, kapağı JPG ya da PNG olarak seç: hat RouteNote'un istediği biçime (FLAC 44,1 kHz; 3000×3000 JPG) çevirir."),
          el("li", {}, "ISRC'n varsa yaz, yoksa dağıtıcı atar. Eksikler sağda listelenir; hepsi tamamlanınca gönder düğmesi açılır."))));
}

// FreshTunes hesabı: 3 ayda bir giriş şart (ToS §4); "Bugün girdim" sayacı sıfırlar
function ftHesapSeridi(ft, sonra) {
  return el("p", { class: ft.hatirlat ? "uyari" : "ipucu ft-serit" },
    ft.kalan < 0 ? `FreshTunes: son giriş/gönderim ${ft.gun} gün önce, 90 günlük süre doldu; hesap askıya alınmış olabilir (açmak 50 $). ` :
      `FreshTunes: son giriş/gönderim ${ft.gun} gün önce; ${ft.kalan} gün içinde giriş şart (yoksa askı, açmak 50 $). `,
    el("button", { class: "dugme ikincil kucuk", type: "button", onclick: async () => { try { bildir((await api("/api/elle-freshtunes/girdim", {})).mesaj); } catch (e) { bildir(e.message, true); } sonra(); } }, "Bugün girdim"));
}

// Kendi müziğim yüzünde kenar çubuğu: şarkılar yerine taslaklar
async function taslakListesiCiz() {
  let d;
  try { d = await api("/api/elle"); } catch { return; }
  const acik = location.hash === "#_yukle" ? elleAcik : null;
  const grup = (ad, liste, ac) => liste.length ? el("details", { class: "grup", open: ac },
    el("summary", {}, el("span", {}, ad), el("span", { class: "g-sayi" }, String(liste.length))),
    el("ul", { class: "liste" }, ...liste.map((x) => el("li", {},
      el("a", { href: "#_yukle", "aria-current": x.kimlik === acik ? "page" : false, onclick: (e) => {
        elleAcik = x.kimlik; depo.yaz("elle.acik", x.kimlik);
        if (location.hash === "#_yukle") { e.preventDefault(); yukleGoster(); taslakListesiCiz(); scrollTo(0, 0); }
      } },
        x.kapak ? el("img", { class: "kapak-kucuk", src: `/elle/${x.kimlik}/kapak?boyut=96`, alt: "", width: 32, height: 32 }) : el("span", { class: "kapak-kucuk bos", "aria-hidden": "true" }, dalgaIsareti()),
        el("span", { class: "ad" }, x.baslik), el("span", { class: "alt" }, el("span", {}, x.sanatci || "—"))))))) : null;
  const gonderilen = d.liste.filter((x) => x.hal === "gonderildi");
  const suren = d.liste.filter((x) => x.hal !== "gonderildi");
  doldur($("#taslak-listesi"), ...[grup("Taslaklar", suren, true), grup("Gönderildi", gonderilen, false),
    d.liste.length ? null : el("p", { class: "ipucu kucuk-ipucu" }, "Henüz taslak yok.")].filter(Boolean));
}

function elleAc(kimlik) { elleAcik = kimlik; depo.yaz("elle.acik", kimlik); yukleGoster(); scrollTo(0, 0); }
function elleKapat() { elleAcik = null; depo.yaz("elle.acik", null); clearTimeout(elleIzle); yukleGoster(); scrollTo(0, 0); }

// alan bileşenleri: her biri `data-alan` taşır, `elleTopla` değeri okur
// alan açıklamaları seçili dağıtıcıya göre (RouteNote: AI cover hattı; FreshTunes: kendi şarkıların); dağıtıcı
// değişince `elleKaydet` yeniler
function elleNotlari(m) {
  const d = m.dagiticilar || [], ft = d.includes("freshtunes") && !d.includes("routenote");
  return ft ? {
    spotify_sanatci_id: "Daha önce yayının varsa profil linkini yapıştır (sanatçı adı profildekiyle birebir aynı olmalı). İlk yayında boş bırak: profil yayından sonra açılır.",
    upc: "Yayının barkodu. Boşsa FreshTunes ücretsiz atar.",
    yayin_tarihi: "FreshTunes'ta zorunlu: en erken 7 gün sonrası, 14–28 gün önerilir (\"onaylanınca\" seçeneği yok).",
    yapay_zeka: "FreshTunes yapay zekâyla üretilmiş kaydı almıyor: açıksa FreshTunes paketi inmez (AI kaydı RouteNote'tan).",
  } : {
    spotify_sanatci_id: "Yayın bu profile bağlanır. Boşsa RouteNote hesaptaki aynı adlı profili kullanır, yoksa yeni profil açar.",
    upc: "Yayının barkodu. RouteNote kendi atar; başka dağıtıcı için.",
    yayin_tarihi: "Boş: dağıtıcı onaylar onaylamaz yayında (en erken). Tarih seçersen RouteNote için en az 10 gün sonrası.",
    yapay_zeka: "Açıkken Amazon ve Kore mağazaları (Melon, Bugs!, FLO, Genie) kapatılır: yapay zekâ içeriği almıyorlar.",
  };
}

function alanMetin(m, ad, etiket, ek = {}) {
  const kimlik = `elle-${ad}`;
  return el("div", { class: "alan" + (ek.genis ? " genis" : "") },
    el("label", { for: kimlik }, etiket, ek.zorunlu ? el("span", { class: "zorunlu", "aria-hidden": "true" }, " *") : null),
    el(ek.cok ? "textarea" : "input", { id: kimlik, "data-alan": ad, type: ek.tur || "text", value: ek.cok ? null : (m[ad] ?? ""), placeholder: ek.ipucu || "",
      maxlength: ek.uzunluk || 200, autocomplete: "off", spellcheck: ek.yazim ? "true" : "false", inputmode: ek.inputmode || null, required: ek.zorunlu || null,
      "aria-describedby": ek.not ? `${kimlik}-not` : null, rows: ek.cok ? 3 : null }, ek.cok ? (m[ad] ?? "") : null),
    ek.not ? el("p", { class: "ipucu alan-not", id: `${kimlik}-not` }, ek.not) : null);
}
function alanSecim(m, ad, etiket, secenekler, ek = {}) {
  const kimlik = `elle-${ad}`;
  return el("div", { class: "alan" },
    el("label", { for: kimlik }, etiket, ek.zorunlu ? el("span", { class: "zorunlu", "aria-hidden": "true" }, " *") : null),
    el("select", { id: kimlik, "data-alan": ad }, ...secenekler.map(([v, ad_]) => el("option", { value: v, selected: m[ad] === v ? true : null }, ad_))));
}
function alanEvetHayir(m, ad, etiket, ek = {}) {
  const grup = el("div", { class: "kesitler ikili", role: "radiogroup", "aria-label": etiket, "data-alan": ad, "data-bool": "1", "data-deger": m[ad] === true ? "1" : m[ad] === false ? "0" : "" },
    ...[["1", ek.evet || "Evet"], ["0", ek.hayir || "Hayır"]].map(([v, yazi]) => el("button", { class: "kesit kucuk", type: "button", role: "radio",
      "aria-checked": grup_secili(m[ad], v) ? "true" : "false", "aria-pressed": grup_secili(m[ad], v) ? "true" : "false",
      onclick: (e) => { const g = e.currentTarget.parentElement; g.dataset.deger = v;
        for (const b of g.children) { const s = b === e.currentTarget; b.setAttribute("aria-checked", s ? "true" : "false"); b.setAttribute("aria-pressed", s ? "true" : "false"); }
        elleDegisti(); } }, yazi)));
  return el("div", { class: "alan" }, el("span", { class: "alan-etiket" }, etiket, ek.zorunlu ? el("span", { class: "zorunlu", "aria-hidden": "true" }, " *") : null), grup,
    ek.not ? el("p", { class: "ipucu alan-not" }, ek.not) : null);
}
const grup_secili = (deger, v) => (deger === true && v === "1") || (deger === false && v === "0");
function alanAnahtar(m, ad, etiket, not) {
  const kimlik = `elle-${ad}`;
  return el("div", { class: "ayar-satir alan-anahtar" },
    el("div", {}, el("b", { id: `${kimlik}-ad` }, etiket), not ? el("p", { class: "ipucu", id: `${kimlik}-not` }, not) : null),
    el("button", { class: "anahtar", type: "button", role: "switch", "data-alan": ad, "data-anahtar": "1", "aria-checked": m[ad] ? "true" : "false", "aria-labelledby": `${kimlik}-ad`,
      onclick: (e) => { const b = e.currentTarget; b.setAttribute("aria-checked", b.getAttribute("aria-checked") === "true" ? "false" : "true"); elleDegisti(true); } },
      el("span", { "aria-hidden": "true" })));
}
function alanKisiler(m, ad, etiket, ek = {}) {
  const liste = el("ul", { class: "kisi-liste", "data-alan": ad, "data-kisi": "1" });
  const satir = (a = "", s = "") => {
    const li = el("li", { class: "kisi-satir" },
      el("input", { type: "text", value: a, placeholder: "Ad", "aria-label": `${etiket}: ad`, maxlength: 80, autocomplete: "off" }),
      el("input", { type: "text", value: s, placeholder: "Soyad", "aria-label": `${etiket}: soyad`, maxlength: 80, autocomplete: "off" }),
      el("button", { class: "dugme tehlike kucuk", type: "button", "aria-label": "Kişiyi çıkar", onclick: () => { li.remove(); if (!liste.children.length) liste.append(satir()); elleDegisti(true); } }, "Çıkar"));
    return li;
  };
  const kisiler = (m[ad] || []).length ? m[ad] : [["", ""]];
  kisiler.forEach(([a, s]) => liste.append(satir(a, s)));
  return el("div", { class: "alan genis" }, el("span", { class: "alan-etiket" }, etiket, ek.zorunlu ? el("span", { class: "zorunlu", "aria-hidden": "true" }, " *") : null),
    liste, el("button", { class: "dugme kucuk ikincil", type: "button", onclick: () => { liste.append(satir()); liste.lastChild.querySelector("input").focus(); } }, ek.ekle || "Kişi ekle"),
    ek.not ? el("p", { class: "ipucu alan-not" }, ek.not) : null);
}

function elleTopla() {
  const deger = {};
  // dağıtıcı kutuları yan panelde (`form="elle-form"`)
  for (const e of document.querySelectorAll("#elle-form [data-alan], [form='elle-form'][data-alan]")) {
    const ad = e.dataset.alan;
    if (e.dataset.kisi) deger[ad] = [...e.children].map((li) => [...li.querySelectorAll("input")].map((i) => i.value));
    else if (e.dataset.bool) { if (e.dataset.deger !== "") deger[ad] = e.dataset.deger === "1"; }
    else if (e.dataset.anahtar) deger[ad] = e.getAttribute("aria-checked") === "true";
    else if (e.dataset.dagitici) { (deger.dagiticilar ||= []); if (e.checked) deger.dagiticilar.push(e.value); }
    else if (e.type === "checkbox") deger[ad] = e.checked;
    else if (["c_yil", "p_yil"].includes(ad)) deger[ad] = e.value.trim() ? Number(e.value) : null;
    else if (ad === "onizleme") { const r = /^(\d{1,2}):([0-5]\d)$/.exec(e.value.trim()); deger.onizleme_sn = r ? +r[1] * 60 + +r[2] : null; }
    else deger[ad] = e.value;
  }
  if (deger.dagiticilar === undefined && document.querySelector("#elle-form [data-dagitici]")) deger.dagiticilar = [];
  return deger;
}

// yazdıkça kaydet (700 ms sonra); sağdaki denetim ve önizleme sunucunun cevabıyla tazelenir
function elleDegisti(hemen = false) {
  const durum = $("#elle-kayit");
  if (durum) { durum.textContent = "Kaydedilecek…"; durum.dataset.d = "bekliyor"; }
  clearTimeout(elleKayit?.zaman);
  const kimlik = elleAcik;
  elleKayit = { kimlik, zaman: setTimeout(() => { elleKayit = null; elleKaydet(kimlik); }, hemen ? 50 : 700) };
}
// bekleyen kaydı hemen gönderir: taslaktan çıkarken, başka görünüme geçerken, ekran yeniden kurulmadan önce (son 700 ms'de
// yazılan kayboluyordu); sayfa kapanırken `keepalive` ile. Form değerleri ekran değişmeden okunur.
function elleBekleyeniGonder(kapaniyor = false) {
  const k = elleKayit;
  if (!k) return null;
  clearTimeout(k.zaman); elleKayit = null;
  if (!kapaniyor) return elleKaydet(k.kimlik);
  try { fetch(`/api/elle/${k.kimlik}`, { method: "POST", keepalive: true, headers: { "Content-Type": "application/json" }, body: JSON.stringify(elleTopla()) }); }
  catch { /* sayfa kapanıyor */ }
  return null;
}
addEventListener("pagehide", () => elleBekleyeniGonder(true));
async function elleKaydet(kimlik = elleAcik) {
  const durum = $("#elle-kayit");
  try {
    if (durum) { durum.textContent = "Kaydediliyor…"; durum.dataset.d = "bekliyor"; }
    const m = await api(`/api/elle/${kimlik}`, elleTopla());
    if (kimlik !== elleAcik || !document.contains(durum)) return; // kayıt yapıldı; ekran artık başka bir taslağın
    if (durum) { durum.textContent = `Kaydedildi ${new Date().toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}`; durum.dataset.d = "ok"; }
    $("#elle-yan")?.replaceWith(elleYan(m, elleIs));
    $("#elle-ust-ad").textContent = elleAdi(m);
    const cover = document.querySelector("#elle-cover-alanlar");
    if (cover) cover.hidden = !m.cover;
    const soz = document.querySelector("#elle-soz-alanlar");
    if (soz) soz.hidden = !m.soz_var || m.soz_ayni !== false;
    for (const [ad, metin] of Object.entries(elleNotlari(m))) { const n = document.getElementById(`elle-${ad}-not`); if (n) n.textContent = metin; }
  } catch (e) { if (durum) { durum.textContent = `Kaydedilemedi: ${e.message}`; durum.dataset.d = "hata"; } }
}

function dosyaGonder(yol, dosya, cubuk) {
  return new Promise((coz, red) => {
    const x = new XMLHttpRequest();
    x.open("POST", `${yol}?ad=${encodeURIComponent(dosya.name)}`);
    x.setRequestHeader("Content-Type", "application/octet-stream");
    x.upload.onprogress = (e) => { if (e.lengthComputable && cubuk) cubuk.style.transform = `scaleX(${e.loaded / e.total})`; };
    x.onload = () => { let d = {}; try { d = JSON.parse(x.responseText); } catch { /* boş */ }
      x.status < 300 ? coz(d) : red(new Error(d.detail || `${x.status}`)); };
    x.onerror = () => red(new Error("bağlantı koptu"));
    x.send(dosya);
  });
}

function yuklemeKutusu(m, tur, kilit) {
  const kapak = tur === "kapak";
  const var_ = kapak ? m.dosya.kapak : m.dosya.ses;
  const bilgi = kapak ? m.kapak : m.ses;
  const girdi = el("input", { type: "file", id: `elle-${tur}`, class: "gizli", accept: kapak ? "image/jpeg,image/png" : "audio/*,.wav,.flac,.aif,.aiff,.mp3,.m4a",
    disabled: kilit ? true : null });
  const cubuk = el("span", { class: "ilerleme-dolu" });
  const yukle = async (dosya) => {
    if (!dosya || kilit) return;
    kutu.setAttribute("aria-busy", "true"); kutu.classList.add("yukleniyor");
    try { await dosyaGonder(`/api/elle/${m.kimlik}/${tur}`, dosya, cubuk); bildir(kapak ? "Kapak 3000×3000'e hazırlandı." : "Ses FLAC'a çevrildi."); yukleGoster(); }
    catch (e) { bildir(`${kapak ? "Kapak" : "Ses"} yüklenemedi: ${e.message}`, true); kutu.removeAttribute("aria-busy"); kutu.classList.remove("yukleniyor"); }
  };
  girdi.addEventListener("change", () => yukle(girdi.files[0]));
  const kutu = el("label", { class: "yukle-kutu" + (var_ ? " dolu" : ""), for: `elle-${tur}`,
    ondragover: (e) => { e.preventDefault(); kutu.classList.add("uzerinde"); }, ondragleave: () => kutu.classList.remove("uzerinde"),
    ondrop: (e) => { e.preventDefault(); kutu.classList.remove("uzerinde"); yukle(e.dataTransfer.files[0]); } },
    kapak && var_ ? el("img", { class: "yukle-kapak", src: `/elle/${m.kimlik}/kapak?boyut=480&v=${var_}`, alt: "Kapak önizlemesi", width: 120, height: 120 })
      : el("span", { class: "yukle-isaret", "aria-hidden": "true" }, dalgaIsareti(26)),
    el("span", { class: "yukle-metin" },
      el("b", {}, kapak ? (var_ ? "Kapak hazır" : "Kapak görseli") : (var_ ? "Ses hazır" : "Ses dosyası")),
      el("span", { class: "ipucu" }, var_ && bilgi
        ? (kapak ? `${bilgi.ad} · ${bilgi.asil.join("×")}${bilgi.kirpildi ? " · kare kırpıldı" : ""}${bilgi.buyutuldu ? " · büyütüldü" : ""}` : `${bilgi.ad} · ${sure(bilgi.sure)} · FLAC ${virgul(bilgi.flac_boyut / 2 ** 20, 1)} MB`)
        : kapak ? "JPG ya da PNG, en az 1400×1400. Sürükle ya da tıkla." : "WAV, FLAC, AIFF ya da MP3. Sürükle ya da tıkla."),
      var_ && !kilit ? el("span", { class: "ipucu kucuk-ipucu" }, "Değiştirmek için yenisini bırak.") : null),
    el("span", { class: "ilerleme yukle-ilerleme", "aria-hidden": "true" }, cubuk), girdi);
  return el("div", { class: "yukle-alan" }, kutu,
    !kapak && var_ ? el("audio", { controls: true, preload: "none", src: `/elle/${m.kimlik}/ses?v=${var_}`, "data-dosya": "elle" }) : null);
}

async function elleDuzenle(kimlik, is) {
  const ana = $("#ana");
  let m;
  try { m = await api(`/api/elle/${kimlik}`); } catch (e) { elleAcik = null; depo.yaz("elle.acik", null); doldur(ana, bosEkran("Taslak açılamadı", e.message)); return; }
  const s = elleSecenek, kilit = !!m.kilit;
  elleIs = is;
  const diller = s.diller.map((d) => [d, d.replace(/_/g, " ").replace("Simplified", "(Basitleştirilmiş)").replace("Traditional", "(Geleneksel)").replace("Latin America", "(Latin Amerika)")]);
  const form = el("form", { id: "elle-form", class: "elle-form", novalidate: true, oninput: () => elleDegisti(), onchange: () => elleDegisti(true), onsubmit: (e) => e.preventDefault() },
    el("fieldset", { class: "form-bolum", disabled: kilit || null }, el("legend", {}, "Dosyalar"),
      el("div", { class: "yukle-cift" }, yuklemeKutusu(m, "ses", kilit), yuklemeKutusu(m, "kapak", kilit))),
    el("fieldset", { class: "form-bolum", disabled: kilit || null }, el("legend", {}, "Şarkı"),
      el("div", { class: "alanlar" },
        alanMetin(m, "baslik", "Şarkının adı", { zorunlu: true, genis: true, ipucu: "Mağazada görünecek ad", yazim: true }),
        alanMetin(m, "surum", "Sürüm", { ipucu: "Acoustic, Remix, Live… (yoksa boş)", uzunluk: 100 }),
        alanMetin(m, "sanatci", "Ana sanatçı", { zorunlu: true, uzunluk: 120 }),
        alanMetin(m, "spotify_sanatci_id", "Spotify sanatçı profili", { ipucu: "Profil linki ya da kimlik (yoksa boş)", uzunluk: 200,
          not: elleNotlari(m).spotify_sanatci_id }),
        alanSecim(m, "dil", "Dil", diller, { zorunlu: true }),
        alanSecim(m, "tur", "Tür", s.turler.map((t) => [t, t]), { zorunlu: true }),
        alanEvetHayir(m, "acik_icerik", "Açık içerik (küfür, argo)", { zorunlu: true, not: "Mağazalar \"E\" (explicit) etiketi koyar." }),
        alanEvetHayir(m, "soz_var", "Sözlü mü", { evet: "Sözlü", hayir: "Enstrümantal" }))),
    el("fieldset", { class: "form-bolum", disabled: kilit || null }, el("legend", {}, "Haklar ve künye"),
      el("div", { class: "alanlar" },
        alanEvetHayir(m, "cover", "Bu bir cover mı", { evet: "Cover", hayir: "Özgün", not: "Cover'da besteci orijinal şarkının yazarlarıdır." }),
        el("div", { id: "elle-cover-alanlar", class: "alanlar ic", hidden: !m.cover },
          alanMetin(m, "orijinal_sanatci", "Orijinal sanatçı", { zorunlu: true, uzunluk: 120 }),
          el("div", { class: "alan genis" }, el("label", { class: "onay-satir" }, el("input", { type: "checkbox", "data-alan": "mekanik_lisans", checked: m.mekanik_lisans || null }),
            " Mekanik lisansım var"), el("p", { class: "ipucu alan-not" }, `Yoksa yayın ${s.mekanik_ulkeler.join(", ")} dışında yapılır (RouteNote cover için bu ülkelerde lisans istiyor).`))),
        alanKisiler(m, "yazar_adlari", "Besteciler", { zorunlu: true, ekle: "Besteci ekle", not: "Yasal ad ve soyad (sahne adı değil). Tek adlı sanatçının soyadı da yazılır." }),
        el("div", { class: "alan genis" }, el("label", { class: "onay-satir" }, el("input", { type: "checkbox", "data-alan": "soz_ayni", checked: m.soz_ayni !== false || null }),
          " Söz yazarları bestecilerle aynı")),
        el("div", { id: "elle-soz-alanlar", class: "alanlar ic", hidden: !m.soz_var || m.soz_ayni !== false },
          alanKisiler(m, "soz_yazari_adlari", "Söz yazarları", { ekle: "Söz yazarı ekle" })),
        alanMetin(m, "uretici", "Yapımcı (producer)", { ipucu: m.sanatci || "boşsa ana sanatçı", uzunluk: 120 }),
        alanMetin(m, "etiket", "Plak şirketi (label)", { ipucu: m.sanatci || "", uzunluk: 120 }),
        alanMetin(m, "c_yil", "© yılı (beste)", { tur: "number", inputmode: "numeric", uzunluk: 4 }),
        alanMetin(m, "c_sahibi", "© sahibi", { ipucu: "boşsa besteciler", uzunluk: 200 }),
        alanMetin(m, "p_yil", "℗ yılı (kayıt)", { tur: "number", inputmode: "numeric", uzunluk: 4 }),
        alanMetin(m, "p_sahibi", "℗ sahibi", { ipucu: "boşsa ana sanatçı", uzunluk: 200 }))),
    el("fieldset", { class: "form-bolum", disabled: kilit || null }, el("legend", {}, "Kodlar ve tarih"),
      el("div", { class: "alanlar" },
        alanMetin(m, "isrc", "ISRC", { ipucu: "TR-A1B-26-00001", uzunluk: 15, not: "Kaydın kodu. Yoksa boş bırak: dağıtıcı atar." }),
        alanMetin(m, "upc", "UPC / EAN", { ipucu: "12–13 rakam", uzunluk: 13, inputmode: "numeric", not: elleNotlari(m).upc }),
        alanMetin(m, "yayin_tarihi", "Yayın tarihi", { tur: "date", uzunluk: 10, not: elleNotlari(m).yayin_tarihi }),
        alanMetin(m, "orijinal_tarih", "Daha önce yayınlandıysa ilk tarih", { tur: "date", uzunluk: 10 }),
        alanMetin(m, "onizleme", "Önizleme başlangıcı", { ipucu: "1:05", uzunluk: 5, inputmode: "numeric", not: "TikTok ve mağaza önizlemesi buradan başlar (dk:sn)." }))),
    el("fieldset", { class: "form-bolum", disabled: kilit || null }, el("legend", {}, "Mağazalar"),
      alanAnahtar(m, "yapay_zeka", "Ses yapay zekâyla üretildi", elleNotlari(m).yapay_zeka),
      alanAnahtar(m, "content_id", "YouTube Content ID", "Kaydını YouTube'da başkasının videosunda tanır ve gelir toplar. Cover ya da yapay zekâ içeriğinde kapalı tut."),
      el("div", { class: "alanlar" }, alanMetin(m, "notlar", "Notlar (kendin için)", { cok: true, uzunluk: 2000, genis: true, yazim: true }))));
  const onizleme = form.querySelector("#elle-onizleme");
  if (onizleme && m.onizleme_sn != null) onizleme.value = `${Math.floor(m.onizleme_sn / 60)}:${String(m.onizleme_sn % 60).padStart(2, "0")}`;
  doldur(ana,
    el("header", { class: "elle-ust" },
      el("button", { class: "dugme kucuk", type: "button", onclick: elleKapat }, "← Taslaklar"),
      el("div", { class: "elle-kimlik" }, el("p", { class: "ust-satir ipucu" }, el("span", { class: "tur-etiket" }, "Yayın taslağı"), el("span", { class: `rozet ${ELLE_HAL[m.hal][1]}` }, ELLE_HAL[m.hal][0])),
        el("h1", { id: "elle-ust-ad" }, elleAdi(m))), // "elle-baslik" ad kutusunun: aynı kimlik etiketi başlığa bağlıyordu
      el("p", { id: "elle-kayit", class: "elle-kayit", "aria-live": "polite", "data-d": "ok" }, kilit ? "Salt okunur" : `Kaydedildi ${saatDakika(m.guncel)}`)),
    kilit ? el("p", { class: "not" }, m.kilit) : null,
    el("div", { class: "pano-izgara elle-izgara" }, el("div", { class: "pano-sol" }, form), elleYan(m, is)));
  if (is?.suruyor && String(is.ad || "").startsWith("elle")) elleTakip();
}

function elleYan(m, is) {
  const s = elleSecenek, k = m.kontrol;
  const secili = m.dagiticilar || [];
  const rn = m.routenote || {};
  const hazir = (d) => !k.eksik.length && !(k.dagitici[d] || []).length;
  const dagitici = el("fieldset", { class: "dagitici-sec", disabled: m.kilit ? true : null }, el("legend", {}, "Dağıtıcı"),
    ...Object.entries(s.dagiticilar).map(([ad, d]) => el("label", { class: "dagitici" + (secili.includes(ad) ? " secili" : "") },
      el("input", { type: "checkbox", value: ad, "data-alan": "dagiticilar", "data-dagitici": "1", checked: secili.includes(ad) || null, form: "elle-form",
        onchange: () => elleDegisti(true) }),
      el("span", {}, el("b", {}, d.ad, d.otomatik ? el("span", { class: "rozet ok" }, "otomatik") : el("span", { class: "rozet" }, "elle")), el("span", { class: "ipucu" }, d.aciklama)))));
  const eksikler = [...k.eksik, ...Object.entries(k.dagitici).flatMap(([d, l]) => l.map((x) => `${s.dagiticilar[d]?.ad}: ${x}`))];
  const eylemler = [];
  if (rn.adim === "gonderildi") eylemler.push(el("p", { class: "not canli" }, el("span", { class: "nokta" }), `RouteNote'a gönderildi${rn.gonderim ? ` (${tarih(rn.gonderim)})` : ""}. İnceleme 5–10 iş günü; onay ya da red e-postası gelince bildirilir.`));
  else if (rn.adim === "gonderiliyor") eylemler.push(el("p", { class: "uyari" }, "Son tıktan sonra iş yarıda kaldı. RouteNote panelinde yayına bak:"),
    el("div", { class: "satir-ici" }, ...[[true, "Gönderilmiş"], [false, "Taslakta duruyor"]].map(([g, yazi]) => el("button", { class: g ? "dugme kucuk" : "dugme ikincil kucuk", type: "button",
      onclick: () => gonderimSonucuSor(elleAdi(m), g, async () => { try { bildir((await api(`/api/elle/${m.kimlik}/gonderim-sonucu`, { gonderildi: g })).mesaj); } catch (e) { bildir(e.message, true); } yukleGoster(); }) }, yazi))));
  else if (secili.includes("routenote")) {
    const yarim = rn.upc && rn.adim !== "hazir";
    // önceki oturumda hazırlanmış taslağın yayın sayfası yeni oturumda boş: otomasyon gönderemez, düğme yanıltmasın
    if (rn.adim !== "hazir") eylemler.push(el("button", { class: "dugme tehlike dolu genis-dugme", type: "button", disabled: !hazir("routenote") || is?.suruyor || null,
      title: hazir("routenote") ? "" : "Önce eksikleri tamamla", onclick: () => elleGonderPenceresi(m) }, yarim ? "Taslağı tamamla ve gönder…" : "RouteNote'a gönder…"));
    if (rn.adim === "hazir") eylemler.push(el("p", { class: "ipucu kucuk-ipucu" }, `Taslak RouteNote'ta hazır ama önceki bir oturumda açıldı; otomasyon bunu gönderemez. Panelde taslağı aç${rn.upc ? ` (UPC ${rn.upc})` : ""}, Distribute'a bas, sonra:`),
      el("button", { class: "dugme kucuk", type: "button", onclick: () => gonderimSonucuSor(elleAdi(m), true, async () => { try { bildir((await api(`/api/elle/${m.kimlik}/gonderim-sonucu`, { gonderildi: true })).mesaj); } catch (e) { bildir(e.message, true); } yukleGoster(); }) }, "Panelde gönderdim"));
    if (!rn.upc) eylemler.push(el("button", { class: "dugme ikincil kucuk", type: "button", disabled: !hazir("routenote") || is?.suruyor || null,
      onclick: async () => { try { await api(`/api/elle/${m.kimlik}/gonder`, { gonder: false }); bildir("RouteNote taslağı hazırlanıyor; gönderilmeyecek."); elleTakip(); yukleGoster(); } catch (e) { bildir(e.message, true); } } },
      "Yalnız RouteNote taslağı aç"));
  }
  const ft = m.freshtunes || {};
  // kapak yoksa Pinterest'ten (cover kapaklarındaki gibi insansız, yazısız); Pinterest kapağı varsa başkası
  if (!m.kilit && !m.dosya.kapak) eylemler.push(el("button", { class: "dugme ikincil kucuk", type: "button", onclick: async (e) => {
    const b = e.currentTarget; b.disabled = true; b.setAttribute("aria-busy", "true");
    try { bildir((await api(`/api/elle/${m.kimlik}/pinterest`, {})).mesaj); } catch (err) { bildir(err.message, true); }
    yukleGoster(); } }, "Pinterest'ten kapak bul"));
  if (!m.kilit && m.kapak?.kaynak === "pinterest") eylemler.push(el("div", { class: "satir-ici" },
    el("span", { class: "ipucu kucuk-ipucu" }, "Kapak Pinterest'ten."),
    m.kapak.pin ? el("a", { class: "dugme ikincil kucuk", href: m.kapak.pin, target: "_blank", rel: "noopener" }, "Pin'i aç") : null,
    el("button", { class: "dugme ikincil kucuk", type: "button", onclick: async (e) => {
      const b = e.currentTarget; b.disabled = true; b.setAttribute("aria-busy", "true");
      try { bildir((await api(`/api/elle/${m.kimlik}/pinterest`, {})).mesaj); } catch (err) { bildir(err.message, true); }
      yukleGoster(); } }, "Başka kapak")));
  if (ft.adim === "gonderildi") eylemler.push(el("p", { class: "not canli" }, el("span", { class: "nokta" }), `FreshTunes'a gönderildi (${tarih(ft.gonderim)}); yayın ${ft.yayin_tarihi ? tarih(ft.yayin_tarihi) : "—"}. Reddedilirse aşağıdan kaydı sıfırla, düzeltip yeniden gönder.`));
  else if (secili.includes("freshtunes")) {
    // FreshTunes şartları botu yasaklıyor (ToS §9g): paket hatta hazırlanır, form Scryne'da
    const ftHazir = hazir("freshtunes");
    eylemler.push(el("ol", { class: "ft-adimlar ipucu" },
      el("li", {}, "Paketi indir: ses, kapak ve formun alanları (FRESHTUNES.txt) içinde."),
      el("li", {}, "FreshTunes'ta yeni yayın aç, alanları listeden kopyala, dosyaları yükle."),
      el("li", {}, "Gönderince buradan kaydet: taslak kilitlenir.")),
    el("a", { class: "dugme birincil genis-dugme" + (ftHazir ? "" : " pasif"), href: ftHazir ? `/elle/${m.kimlik}/paket.zip?dagitici=freshtunes` : null,
      "aria-disabled": ftHazir ? null : "true", title: ftHazir ? "" : "Önce eksikleri tamamla", download: "" }, "FreshTunes paketini indir (ZIP)"),
    el("div", { class: "satir-ici" },
      el("a", { class: "dugme ikincil kucuk", href: s.freshtunes_url, target: "_blank", rel: "noopener" }, "FreshTunes'u aç"),
      el("button", { class: "dugme kucuk", type: "button", disabled: !ftHazir || null, onclick: () => ftGonderildiSor(m) }, "FreshTunes'a gönderdim")));
  }
  if (secili.includes("elle")) eylemler.push(el("a", { class: "dugme ikincil genis-dugme" + (m.dosya.ses && m.dosya.kapak ? "" : " pasif"), href: m.dosya.ses && m.dosya.kapak ? `/elle/${m.kimlik}/paket.zip` : null,
    "aria-disabled": m.dosya.ses && m.dosya.kapak ? null : "true", download: "" }, "Paketi indir (ZIP)"));
  return el("aside", { id: "elle-yan", class: "pano-sag elle-yan" },
    el("section", { class: "cam yan-panel elle-onizleme", "aria-label": "Önizleme" },
      m.dosya.kapak ? el("img", { src: `/elle/${m.kimlik}/kapak?boyut=480&v=${m.dosya.kapak}`, alt: "", width: 480, height: 480 }) : el("div", { class: "elle-kapak-bos", "aria-hidden": "true" }, dalgaIsareti(40)),
      el("div", { class: "elle-onizleme-yazi" }, el("b", {}, elleAdi(m), m.surum ? el("span", { class: "ipucu" }, ` (${m.surum})`) : null),
        el("span", { class: "ipucu" }, [m.sanatci, m.tur, m.acik_icerik ? "E" : null].filter(Boolean).join(" · ")),
        rn.upc || rn.isrc || m.isrc ? el("span", { class: "ipucu elle-kod" }, [rn.upc ? `UPC ${rn.upc}` : null, (rn.isrc || m.isrc) ? `ISRC ${rn.isrc || m.isrc}` : null].filter(Boolean).join(" · ")) : null)),
    el("section", { class: "cam yan-panel", "aria-label": "Hazırlık" }, el("h2", {}, "Hazırlık"),
      eksikler.length ? el("ul", { class: "kontrol-liste" }, ...eksikler.map((x) => el("li", { class: "eksik" }, x)))
        : el("p", { class: "gece-satir" }, el("span", { class: "nokta" }), el("b", {}, "Gönderime hazır")),
      k.uyari.length ? el("ul", { class: "kontrol-liste" }, ...k.uyari.map((x) => el("li", { class: "uyari-madde" }, x))) : null),
    el("section", { class: "cam yan-panel", "aria-label": "Dağıtım" }, el("h2", {}, "Dağıtım"), dagitici, ...eylemler,
      rn.upc && rn.adim !== "gonderildi" && rn.adim !== "gonderiliyor" ? el("details", { class: "elle-ileri" }, el("summary", {}, "RouteNote taslağını panelden sildim"),
        el("p", { class: "ipucu kucuk-ipucu" }, "Kayıt sıfırlanır, form yeniden düzenlenebilir; sonraki gönderim yeni taslak açar."),
        el("button", { class: "dugme tehlike kucuk", type: "button", onclick: async () => { try { bildir((await api(`/api/elle/${m.kimlik}/sifirla`, {})).mesaj); } catch (e) { bildir(e.message, true); } yukleGoster(); } }, "Kaydı sıfırla")) : null,
      ft.adim === "gonderildi" ? el("details", { class: "elle-ileri" }, el("summary", {}, "FreshTunes reddetti / yanlışlıkla kaydettim"),
        el("p", { class: "ipucu kucuk-ipucu" }, "Kayıt geçmişe taşınır, form yeniden düzenlenebilir. FreshTunes'taki yayına dokunulmaz."),
        el("button", { class: "dugme tehlike kucuk", type: "button", onclick: async () => { try { bildir((await api(`/api/elle/${m.kimlik}/sifirla?dagitici=freshtunes`, {})).mesaj); } catch (e) { bildir(e.message, true); } yukleGoster(); } }, "FreshTunes kaydını sıfırla")) : null,
      !rn.upc && ft.adim !== "gonderildi" ? el("details", { class: "elle-ileri" }, el("summary", {}, "Taslağı sil"),
        el("button", { class: "dugme tehlike kucuk", type: "button", onclick: async () => { try { await api(`/api/elle/${m.kimlik}/sil`, {}); bildir("Taslak silindi."); elleKapat(); } catch (e) { bildir(e.message, true); } } }, "Kalıcı olarak sil")) : null),
    is && String(is.ad || "").startsWith("elle") ? isPaneli(is) : null);
}
function ftGonderildiSor(m) {
  const dlg = pencere(`"${elleAdi(m)}" FreshTunes'a gönderildi diye kaydedilsin mi?`, [
    el("p", { class: "ipucu" }, "Yalnız FreshTunes'ta yayını gönderdiysen (moderasyonda görünüyorsa). Taslak kilitlenir; bilgiler artık FreshTunes panelinden değişir. Hesap etkinliği de sayılır (3 ayda bir giriş şartı)."),
  ], [
    el("button", { class: "dugme", type: "button", onclick: () => dlg.close() }, "Vazgeç"),
    el("button", { class: "dugme punch", type: "button", onclick: async () => { dlg.close(); try { bildir((await api(`/api/elle/${m.kimlik}/freshtunes-gonderildi`, {})).mesaj); } catch (e) { bildir(e.message, true); } yukleGoster(); } }, "Gönderildi, kaydet"),
  ]);
}

function elleGonderPenceresi(m) {
  const kutu = el("input", { id: "elle-onay", type: "text", autocomplete: "off", spellcheck: "false", placeholder: m.baslik });
  const sade = (x) => x.trim().replace(/[Iİı]/g, "i").toLowerCase();
  const dugme = el("button", { class: "dugme tehlike dolu", type: "button", disabled: true, onclick: async () => {
    dugme.setAttribute("aria-busy", "true"); dugme.disabled = true;
    try { await api(`/api/elle/${m.kimlik}/gonder`, { gonder: true, onay: kutu.value }); dlg.close(); bildir(`"${m.baslik}" RouteNote'a gönderiliyor; ilerlemeyi "Son iş"ten izle.`); elleTakip(); }
    catch (e) { dugme.removeAttribute("aria-busy"); dugme.disabled = false; bildir(e.message, true); return; }
    yukleGoster();
  } }, "RouteNote'a gönder");
  kutu.addEventListener("input", () => { dugme.disabled = sade(kutu.value) !== sade(m.baslik); });
  const dlg = pencere(`"${m.baslik}" RouteNote'a gönderilsin mi?`, [
    el("p", {}, "Form tarayıcıyla doldurulur ve aynı oturumda incelemeye gönderilir. RouteNote'un şartları senin adına kabul edilir. Gönderdikten sonra ses ve bilgiler değiştirilemez; kaldırmak için panelden takedown gerekir."),
    el("dl", { class: "ayar-listesi gonder-ozet" },
      el("dt", {}, "Sanatçı"), el("dd", {}, m.sanatci),
      el("dt", {}, "Profil"), el("dd", {}, m.spotify_sanatci_id || "yeni profil"),
      el("dt", {}, "Tür / dil"), el("dd", {}, `${m.tur} · ${(m.dil || "").replace(/_/g, " ")}`),
      el("dt", {}, "ISRC"), el("dd", {}, m.isrc || "RouteNote atar"),
      el("dt", {}, "Yayın"), el("dd", {}, m.yayin_tarihi ? tarih(m.yayin_tarihi) : "onaylanınca"),
      el("dt", {}, "Bölge"), el("dd", {}, m.cover && !m.mekanik_lisans ? `${elleSecenek.mekanik_ulkeler.join(", ")} hariç` : "bütün dünya")),
    el("label", { for: "elle-onay" }, "Onaylamak için şarkının adını yaz: ", el("b", {}, m.baslik)), kutu],
    [el("button", { class: "dugme ikincil", type: "button", onclick: () => dlg.close() }, "Vazgeç"), dugme], "gonder-pencere");
  kutu.focus();
}

function elleTakip() {
  clearTimeout(elleIzle);
  elleIzle = setTimeout(async () => {
    if (location.hash !== "#_yukle") return;
    let is;
    try { is = await api("/api/sanatci/is"); } catch { elleTakip(); return; }
    elleIs = is;
    if (is.suruyor) { $("#is-paneli")?.replaceWith(isPaneli(is)); elleTakip(); return; }
    const ad = IS_ADI[is.ad] || "İş";
    bildir(is.kod === 0 ? `${ad} bitti.` : `${ad} hata verdi; "Son iş" günlüğüne bak.`, is.kod !== 0);
    yukleGoster();
  }, 2500);
}

// ---- kenar çubuğu: şarkılar aşama gruplarında, aranabilir ----
const GRUPLAR = [
  { k: "dinleme", ad: "Dinlemende", asamalar: ["uretildi", "onarim"], acik: true },
  { k: "uretim", ad: "Üretimde", asamalar: ["yeni", "hazir", "analiz"], acik: true },
  { k: "hata", ad: "Hata", asamalar: ["hata"], acik: true },
  { k: "hazirlik", ad: "Yayına hazırlanıyor", asamalar: ["onaylandi", "paketlendi"], acik: true },
  { k: "dagitim", ad: "Dağıtımda", asamalar: ["yuklendi", "yayinda"], acik: false },
  // reddedilenler listede yok (Scryne, 2026-10-18: "görmeyeyim"); sesleri gece temizliğinde silinir
];
let sonListe = [], aramaMetni = "";
const katla = (s) => s.toLocaleLowerCase("tr").normalize("NFD").replace(/\p{M}/gu, "");

async function listeGoster(secili) {
  for (const a of document.querySelectorAll(".gorunumler a")) {
    if (a.dataset.g !== secili) { a.removeAttribute("aria-current"); continue; }
    a.setAttribute("aria-current", "page");
    // dar ekranda görünümler yatay kayan tek satır: açık olan görünsün (sayfa dikeyde oynamaz)
    const ul = a.closest(".gorunumler");
    if (ul.scrollWidth > ul.clientWidth)
      ul.scrollLeft += a.getBoundingClientRect().left - ul.getBoundingClientRect().left - (ul.clientWidth - a.offsetWidth) / 2;
  }
  sonListe = await api("/api/sarkilar");
  listeCiz(secili);
  return sonListe;
}

function listeCiz(secili = decodeURIComponent(location.hash.slice(1)) || "_pano") {
  const liste = sonListe;
  $("#liste-bos").hidden = liste.length > 0;
  const dinlemede = liste.filter((s) => s.asama === "uretildi").length;
  $("#sayac").textContent = dinlemede ? `${dinlemede} şarkı dinlemeni bekliyor` : "";
  const q = katla(aramaMetni.trim());
  const uyan = q ? liste.filter((s) => katla(`${s.ad} ${s.sanatci}`).includes(q)) : liste;
  const acikDurum = depo.oku("gruplar", {});
  const gruplar = GRUPLAR.map((g) => {
    const sarkilar = uyan.filter((s) => g.asamalar.includes(s.asama))
      .sort((a, b) => (b.guncel || "").localeCompare(a.guncel || ""));
    if (!sarkilar.length) return null;
    const acik = q || sarkilar.some((s) => s.kimlik === secili) || (acikDurum[g.k] ?? g.acik);
    const det = el("details", { class: "grup", "data-g": g.k, open: acik },
      el("summary", {}, el("span", {}, g.ad), el("span", { class: "g-sayi" + (g.k === "dinleme" ? " dikkat" : "") }, String(sarkilar.length))),
      el("ul", { class: "liste" }, ...sarkilar.map((s) => el("li", {},
        el("a", { href: `#${s.kimlik}`, "aria-current": s.kimlik === secili ? "page" : false },
          kapakImg(s.kapak),
          el("span", { class: "ad" }, s.ad),
          el("span", { class: "alt" }, el("span", {}, s.sanatci),
            g.asamalar.length > 1 || g.k === "hata" ? el("span", { class: "asama", "data-a": s.asama }, ASAMA[s.asama] || s.asama) : null,
            s.asama === "analiz" ? el("span", { class: "nabiz kucuk", title: "üretimde", "aria-hidden": "true" }) : null))))));
    det.addEventListener("toggle", () => { if (q) return; const d = depo.oku("gruplar", {}); d[g.k] = det.open; depo.yaz("gruplar", d); });
    return det;
  }).filter(Boolean);
  doldur($("#liste"), ...(gruplar.length ? gruplar : [el("p", { class: "ipucu kucuk-ipucu" }, `"${aramaMetni}" ile eşleşen şarkı yok.`)]));
}

const GORUNUM = { _pano: panoGoster, _kesif: kesifGoster, _bulucu: bulucuGoster, _yayin: yayinGoster, _kulak: kulakGoster, _sanatci: sanatciGoster, _yukle: yukleGoster };
// iki yüz: Orvane (AI cover hattı) ve Kendi müziğim (FreshTunes); yüzü görünüm adresi belirler, her yüz son görünümünü hatırlar
const KENDI_YUZU = new Set(["_yukle", "_bulucu"]);
const YUZ = { orvane: { alt: "Orvane", acilis: "_pano", baslik: "Orvane" }, kendi: { alt: "Kendi", acilis: "_yukle", baslik: "Kendi müziğim" } };
const yuzBul = (kimlik) => KENDI_YUZU.has(kimlik) ? "kendi" : "orvane";
function yuzAyarla(kimlik) {
  const yuz = yuzBul(kimlik);
  document.body.dataset.yuz = yuz;
  $("#marka-alt").textContent = YUZ[yuz].alt;
  $(".marka").setAttribute("href", yuz === "kendi" ? "#_yukle" : "#");
  for (const b of document.querySelectorAll("[data-yuz-sec]")) b.setAttribute("aria-pressed", b.dataset.yuzSec === yuz ? "true" : "false");
  document.title = `Yanki · ${YUZ[yuz].baslik}`;
  depo.yaz(`yuz.son.${yuz}`, kimlik);
  depo.yaz("yuz", yuz);
  return yuz;
}
// menüdeki "Taslaklar" her zaman listeyi (ve "Yeni şarkı"/"Boş taslak" düğmelerini) açar, son açılan taslağı değil
$('[data-g="_yukle"]').addEventListener("click", (e) => {
  elleBekleyeniGonder();
  elleAcik = null; depo.yaz("elle.acik", null);
  if (location.hash === "#_yukle") { e.preventDefault(); yukleGoster(); taslakListesiCiz(); scrollTo(0, 0); }
});
for (const b of document.querySelectorAll("[data-yuz-sec]")) b.addEventListener("click", () => {
  const yuz = b.dataset.yuzSec;
  if (yuzBul(acikKimlik()) === yuz) return;
  const son = depo.oku(`yuz.son.${yuz}`, YUZ[yuz].acilis);
  const hedef = yuzBul(son) === yuz ? son : YUZ[yuz].acilis;
  location.hash = hedef === "_pano" ? "" : hedef;
});
function acikKimlik() {
  try { return decodeURIComponent(location.hash.slice(1)) || "_pano"; } catch { return "_pano"; }
}
async function yenile(kimlik = acikKimlik()) {
  // önceki şarkının hızlı karşılaştırma kısayolları başka görünümde onay/çal yapmasın; şarkı sayfası kendisi kurar
  panelTus = null;
  const yuz = yuzAyarla(kimlik);
  await listeGoster(kimlik);
  if (yuz === "kendi") taslakListesiCiz();
  gorunumSayilari();
  if (GORUNUM[kimlik]) await GORUNUM[kimlik]();
  else await sarkiGoster(kimlik);
}
addEventListener("hashchange", () => {
  calan?.ses.pause();
  elleBekleyeniGonder(); // Yükle'den başka görünüme geçerken son yazılan kaybolmasın
  yenile().then(() => $("#ana").focus({ preventScroll: true }), (e) => bildir(`Sayfa açılamadı: ${e.message}`, true));
  scrollTo(0, 0);
});
$("#ara").addEventListener("input", (e) => { aramaMetni = e.target.value; listeCiz(); });
$("#ara").addEventListener("keydown", (e) => {
  if (e.key === "Escape") { e.target.value = ""; aramaMetni = ""; listeCiz(); e.target.blur(); }
  if (e.key === "Enter") { const ilk = $("#liste a"); if (ilk) { location.hash = ilk.getAttribute("href").slice(1); e.target.blur(); } }
});
// adres yoksa son kullanılan yüz açılır
if (!location.hash && depo.oku("yuz", "orvane") === "kendi") history.replaceState(null, "", `#${depo.oku("yuz.son.kendi", "_yukle")}`);
yenile().catch((e) => bildir(`Sunucuya ulaşılamadı: ${e.message}`, true));
// arka planda ilerleyen aşamalar: liste her 30 sn; açık şarkı değiştiyse (yeni adaylar) ve bir şey çalmıyorsa sayfa da
setInterval(async () => {
  const kimlik = acikKimlik();
  try {
    const liste = await listeGoster(kimlik);
    gorunumSayilari();
    if (sesCaliyor() || document.querySelector("dialog[open]") || document.activeElement?.closest?.("form, textarea, input")) return;
    if (acikSarki && acikSarki.kimlik === kimlik) {
      const s = liste.find((x) => x.kimlik === kimlik);
      if (s && (s.guncel !== acikSarki.guncel || s.asama !== acikSarki.asama)) {
        const y = scrollY; await sarkiGoster(kimlik); scrollTo(0, y);
        bildir(s.asama === "uretildi" ? `"${s.ad}" için yeni adaylar geldi.` : `"${s.ad}" güncellendi: ${ASAMA[s.asama] || s.asama}.`);
      }
    } else if (kimlik === "_pano" && !anadaOdak()) { const y = scrollY; await panoGoster(); scrollTo(0, y); }
  } catch { /* sunucu kısa süre yoksa sonraki turda */ }
}, 30000);
