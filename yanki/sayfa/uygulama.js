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
const sure = (s) => { s = Math.max(0, s || 0); return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`; };
const aralik = (a, b) => `${sure(a)}–${sure(b)}`;
const virgul = (n, basamak) => n == null ? "—" : String(basamak == null ? n : Number(n).toFixed(basamak)).replace(".", ",");
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
const DAGITIM = { draft: "taslak", pending: "incelemede", approved: "onaylandı", live: "mağazalarda", rejected: "reddedildi",
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
const sesCaliyor = () => !!calan && !calan.ses.paused && document.contains(calan.ses);

// ---- dalga şeridi ----
const seritler = new Map(); // dosya → Serit (şarkı ekranında; söz satırına tıklayınca o kayıtta oraya gidilir)
class Serit {
  constructor({ kimlik, dosya, secilebilir = false, vurgu = null, kucuk = false, etiket }) {
    this.kimlik = kimlik; this.dosya = dosya; this.secilebilir = secilebilir; this.vurgu = vurgu;
    this.secim = null; this.tepe = []; this.toplam = 0;
    this.ses = el("audio", { preload: "none", src: `/ses/${kimlik}/${dosya}`, "data-dosya": dosya });
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
    try { const d = await api(`/api/dalga/${this.kimlik}/${this.dosya}`); this.tepe = d.tepe; this.toplam = d.sure; this.ciz(); }
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
  try { d = await api(`/api/sarki/${kimlik}`); } catch (e) { ana.replaceChildren(bosEkran("Şarkı açılamadı", e.message)); return; }
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
      el("span", { class: "ipucu" }, "Bu şarkıyı reddettin. Geri alırsan reddetmeden önceki aşamasına döner; adaylar yerinde."),
      el("span", { class: "bosluk" }),
      el("button", { class: "dugme ikincil", type: "button",
        onclick: () => eylem(d, "geri-al", {}, `"${d.ad}" yeniden listede, reddetmeden önceki aşamasında.`) }, "Reddi geri al")));
  }
  ana.replaceChildren(...parcalar.filter(Boolean));
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
  if (e.key === " " && e.target.closest?.("button, a")) return; // odaktaki düğmenin kendi tıklaması
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
    iz.ses = el("audio", { preload: "none", src: `/ses/${d.kimlik}/${iz.dosya}`, "data-dosya": iz.dosya });
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
  try { d = await api("/api/kesif"); } catch (e) { ana.replaceChildren(bosEkran("Keşif açılamadı", e.message)); return; }
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
    ana.replaceChildren(
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
  let d;
  try { d = await api("/api/yayin"); } catch (e) { ana.replaceChildren(bosEkran("Yayın durumu açılamadı", e.message)); return; }
  const canli = d.sarkilar.filter((s) => s.son?.canli).length;
  const parcalar = [
    el("header", { class: "sayfa-ust" }, el("h1", {}, "Yayın"),
      el("p", { class: "ipucu" }, `${d.sarkilar.length} yüklenen şarkı, ${canli} tanesi Spotify'da. Adı arandığında kaçıncı çıktığımız pazar pazar.`)),
    kotaSatiri(d.kota),
  ];
  if (d.profiller.length > 1) parcalar.push(el("p", { class: "uyari", role: "alert" },
    `Sanatçı profili bölünmüş: parçalar ${d.profiller.length} ayrı Spotify profilinde. Dağıtımcıdan birleştirme iste.`));
  parcalar.push(d.sarkilar.length ? el("ul", { class: "kayitlar" }, ...d.sarkilar.map(yayinSatiri))
    : el("p", { class: "bos-kutu" }, "Henüz yüklenmiş şarkı yok. Paketi yükleyince: yanki yuklendi <kimlik>"));
  parcalar.push(takvimBolumu(d.takvim));
  if (d.olaylar?.length) parcalar.push(olayBolumu(d.olaylar));
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
      el("span", {}, "çıkış ", el("b", {}, tarih(s.yayin_tarihi))),
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
    const [k, y, p] = await Promise.all([api("/api/kesif"), api("/api/yayin"), api("/api/pano")]);
    const bekleyen = p.kulak.length + p.hatada.length + (p.takvim?.yazarsiz?.length || 0);
    $("#g-pano").textContent = bekleyen ? String(bekleyen) : "";
    $("#g-pano").classList.toggle("dikkat", bekleyen > 0);
    $("#g-pano").title = bekleyen ? "Senden beklenen" : "";
    $("#g-kesif").textContent = String(k.adaylar.filter(SUZGEC.oneri.f).length || "");
    $("#g-yayin").textContent = y.sarkilar.length ? `${y.sarkilar.filter((s) => s.son?.canli).length}/${y.sarkilar.length}` : "";
    simdiDurum(p.simdi);
  } catch { /* sayılar ikincil: sunucu yoksa ana hata zaten bildirilir */ }
}

// kenar çubuğundaki canlı durum: koşu sürüyor mu, kiralık GPU açık mı
function simdiDurum(s) {
  const yer = $("#simdi");
  if (!yer || !s) return;
  if (!s.suruyor && !s.pod) { yer.replaceChildren(el("span", { class: "nokta" }), "Hat boşta"); yer.dataset.d = "bos"; return; }
  yer.dataset.d = "suruyor";
  yer.replaceChildren(el("span", { class: "nabiz", "aria-hidden": "true" }),
    s.pod ? `Kiralık GPU'da üretim · ${s.pod.dakika} dk` : "Koşu sürüyor");
}

// ---- pano: hattın sinyal zinciri, şu an, senden beklenenler, dağıtım, kazanç, tarif ----
const saatDakika = (iso) => iso ? new Date(iso).toLocaleString("tr-TR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";
const ZINCIR_HEDEF = { "Keşif": "#_kesif", "Dinleme": null, "İnceleme": "#_yayin", "Yayında": "#_yayin" };

async function panoGoster() {
  const ana = $("#ana");
  let p;
  try { p = await api("/api/pano"); } catch (e) { ana.replaceChildren(bosEkran("Pano açılamadı", e.message)); return; }
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
  const ozet = [ayar.takvim_acik === false ? "yayın takvimi kapalı" : ayar.haftada === 0 ? "sırası gelen her paket hemen yüklenir" : ayar.haftada ? `haftada ${ayar.haftada} yayın` : null,
    ayar.oto_onay ? `${ayar.oto_onay_saat} saatte karar yoksa kendiliğinden onay` : "onay sende"].filter(Boolean).join(" · ");
  const saat = new Date().getHours();
  const selam = saat < 6 ? "İyi geceler" : saat < 12 ? "Günaydın" : saat < 18 ? "İyi günler" : "İyi akşamlar";

  ana.replaceChildren(
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
  const durumYazi = s.pod ? `Kiralık GPU açık · ${s.pod.dakika} dk` : s.suruyor ? "Koşu sürüyor" : "Sırada, sonraki koşuyu bekliyor";
  return el("section", { class: "simdi-serit" + (s.suruyor || s.pod ? " canli" : ""), "aria-label": "Şu an" },
    el("div", { class: "simdi-baslik" }, s.suruyor || s.pod ? el("span", { class: "nabiz", "aria-hidden": "true" }) : el("span", { class: "nokta" }),
      el("div", {}, el("b", {}, "Şu an"), el("span", { class: "ipucu" }, durumYazi))),
    s.uretimde?.length ? el("ul", { class: "simdi-liste" }, ...s.uretimde.map((x) => el("li", {},
      el("a", { href: `#${x.kimlik}` }, kapakImg(x.kapak), el("span", { class: "ad" }, x.ad),
        el("span", { class: "ipucu" }, x.asama === "onarim" ? "onarım" : x.gecen_aday ? "yeni adaylar üretiliyor" : "adaylar üretiliyor"))))) : null);
}

function beklenenBolumu(p) {
  const satirlar = [
    ...p.kulak.map((s) => ({ s, rozet: ["dinlemen gerekiyor", "amber"], metin: s.neden })),
    ...p.hatada.map((s) => ({ s, rozet: ["hata", "no"], metin: s.hata })),
    ...p.yakinda.map((s) => ({ s, rozet: ["kendiliğinden onaylanacak", "gumus"], metin: saatDakika(s.zaman) })),
    ...(p.takvim?.yazarsiz || []).map((s) => ({ s, rozet: ["yazar gerekli", "amber"],
      metin: "Orijinal söz yazarı bulunamadı; dağıtımcılar yazarsız cover almıyor. girdi/liste.toml'da şarkıya yazarlar = [\"Ad Soyad\"] ekle, paket sonraki koşuda yenilenip sıraya girer." })),
  ];
  const uyarilar = (p.uyarilar || []).map((u) => el("li", { class: "kayit uyari-kayit" },
    el("div", { class: "kayit-ad" }, el("span", { class: "ad" }, u.baslik)),
    el("div", { class: "olculer" }, el("span", { class: "rozet amber" }, "dağıtım"), el("span", { class: "duz" }, u.metin))));
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
    if (!k.bagli) { kutu.replaceChildren(el("h2", {}, "Kazanç"), el("p", { class: "kazanc-alt" }, "Tunearo anahtarı yok (.env).")); return; }
    if (k.ulasilamadi) {
      kutu.replaceChildren(el("h2", {}, "Kazanç"), el("p", { class: "kazanc-toplam soluk-sayi" }, "—"),
        el("p", { class: "kazanc-alt", title: k.hata }, k.erisim_kapali ? "Tunearo API erişimi kapalı. Hesap sahibi açınca raporlar burada görünür."
          : "Tunearo'ya şu an ulaşılamıyor; sonra yeniden denenir."));
      return;
    }
    const enCok = Math.max(...k.kaynaklar.map((x) => x.tutar), 0.01);
    kutu.replaceChildren(el("h2", {}, "Kazanç"),
      el("p", { class: "kazanc-toplam gumus-yazi" }, para(k.toplam, k.para)),
      el("p", { class: "kazanc-alt" }, `bu ay ${para(k.bu_ay, k.para)} · ${k.yayinlar.length} yayın · aylık raporla güncellenir`),
      k.kaynaklar.length ? el("ul", { class: "cubuklar" }, ...k.kaynaklar.slice(0, 6).map((x) => el("li", {},
        el("span", {}, x.kaynak), el("b", {}, para(x.tutar, k.para)),
        el("span", { class: "cubuk", "aria-hidden": "true" }, el("i", { style: { width: `${Math.round((x.tutar / enCok) * 100)}%` } })))))
        : el("p", { class: "kazanc-alt" }, "İlk rapor, parçalar mağazalarda dinlendikten sonraki ay gelir."));
  }).catch((e) => kutu.replaceChildren(el("h2", {}, "Kazanç"), el("p", { class: "kazanc-alt" }, e.message)));
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
  const kutu = el("section", { class: "cam yan-panel", "aria-label": "Son koşu" }, el("h2", {}, "Son gece koşusu"));
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
      ...satir("Üretim", a.uretim || "—"),
      ...satir("Dağıtımcı", DAGITIMCI[a.dagitimci] || a.dagitimci || "—"),
      ...satir("Takvim", !a.takvim_acik ? "kapalı" : a.haftada === 0 ? "açık · sınırsız" : a.haftada >= 7 ? "açık · her gün" : `açık · haftada ${a.haftada}`),
      ...satir("Otomatik onay", a.oto_onay ? `${a.oto_onay_saat} sa` : "kapalı"),
      ...satir("Kapak", a.kapak === "pinterest" ? "Pinterest" : "üretilen"),
      ...satir("Spotify", !kota?.bagli ? "bağlı değil" : kota.kilit_sn ? `kilitli · ${saatYazi(kota.kilit_sn)}` : `${kota.bugun}/${kota.tavan} istek`)));
}

// ---- kenar çubuğu: şarkılar aşama gruplarında, aranabilir ----
const GRUPLAR = [
  { k: "dinleme", ad: "Dinlemende", asamalar: ["uretildi", "onarim"], acik: true },
  { k: "uretim", ad: "Üretimde", asamalar: ["yeni", "hazir", "analiz"], acik: true },
  { k: "hata", ad: "Hata", asamalar: ["hata"], acik: true },
  { k: "hazirlik", ad: "Yayına hazırlanıyor", asamalar: ["onaylandi", "paketlendi"], acik: true },
  { k: "dagitim", ad: "Dağıtımda", asamalar: ["yuklendi", "yayinda"], acik: false },
  { k: "red", ad: "Reddedilen", asamalar: ["reddedildi"], acik: false },
];
let sonListe = [], aramaMetni = "";
const katla = (s) => s.toLocaleLowerCase("tr").normalize("NFD").replace(/\p{M}/gu, "");

async function listeGoster(secili) {
  for (const a of document.querySelectorAll(".gorunumler a")) {
    if (a.dataset.g === secili) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
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
  $("#liste").replaceChildren(...(gruplar.length ? gruplar : [el("p", { class: "ipucu kucuk-ipucu" }, `"${aramaMetni}" ile eşleşen şarkı yok.`)]));
}

const GORUNUM = { _pano: panoGoster, _kesif: kesifGoster, _yayin: yayinGoster };
async function yenile(kimlik = decodeURIComponent(location.hash.slice(1)) || "_pano") {
  await listeGoster(kimlik);
  gorunumSayilari();
  if (GORUNUM[kimlik]) await GORUNUM[kimlik]();
  else await sarkiGoster(kimlik);
}
addEventListener("hashchange", () => { calan?.ses.pause(); yenile().then(() => $("#ana").focus({ preventScroll: true })); scrollTo(0, 0); });
$("#ara").addEventListener("input", (e) => { aramaMetni = e.target.value; listeCiz(); });
$("#ara").addEventListener("keydown", (e) => {
  if (e.key === "Escape") { e.target.value = ""; aramaMetni = ""; listeCiz(); e.target.blur(); }
  if (e.key === "Enter") { const ilk = $("#liste a"); if (ilk) { location.hash = ilk.getAttribute("href").slice(1); e.target.blur(); } }
});
yenile().catch((e) => bildir(`Sunucuya ulaşılamadı: ${e.message}`, true));
// arka planda ilerleyen aşamalar: liste her 30 sn; açık şarkı değiştiyse (yeni adaylar) ve bir şey çalmıyorsa sayfa da
setInterval(async () => {
  const kimlik = decodeURIComponent(location.hash.slice(1)) || "_pano";
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
    } else if (kimlik === "_pano") { const y = scrollY; await panoGoster(); scrollTo(0, y); }
  } catch { /* sunucu kısa süre yoksa sonraki turda */ }
}, 30000);
