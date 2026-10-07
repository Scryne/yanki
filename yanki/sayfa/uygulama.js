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
  onaylandi: "onaylandı", paketlendi: "paketlendi", yuklendi: "yüklendi", hata: "hata", reddedildi: "reddedildi",
};
const KAPI = { parmak_izi: "parmak izi", dalga: "dalga", soz_wer: "söz", sure_fark: "süre", motor: "motor" };

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
  const parcalar = [
    el("header", { class: "baslik" }, el("h1", {}, d.ad), el("span", { class: "sanatci" }, d.sanatci),
      el("span", { class: "asama", "data-a": d.asama }, ASAMA[d.asama] || d.asama)),
    el("p", { class: "kunye" },
      el("span", {}, "Yazarlar: ", el("b", {}, (k.yazarlar || []).join(", ") || "bulunamadı")),
      el("span", {}, "Stil: ", el("b", {}, d.analiz?.stil || "—")),
      el("span", {}, "Tempo/ton: ", el("b", {}, [d.analiz?.bpm && `${d.analiz.bpm} BPM`, d.analiz?.ton].filter(Boolean).join(" · ") || "—")),
      el("span", {}, "Kaynak: ", el("b", {}, d.kaynak?.baslik || "—"))),
  ];
  if (d.hata) parcalar.push(el("p", { class: "uyari", role: "alert" }, d.hata));
  if (["uretildi", "hata"].includes(d.asama) && d.analiz?.stil) parcalar.push(stilKutu(d));
  if (d.asama === "analiz" && d.adaylar.length) parcalar.push(el("p", { class: "ipucu bekleyen" },
    "Yeni stille iki aday sırada; sonraki koşuda üretilir. O zamana kadar mevcut adaylar yalnız dinlenebilir."));
  if (d.kaynak?.dosya) parcalar.push(seritKutu({ kimlik, dosya: d.kaynak.dosya, baslik: "Orijinal", alt: "karşılaştırma için" }));
  const duzenlenebilir = ["uretildi", "onarim"].includes(d.asama);
  const stilFarkli = new Set(d.adaylar.map((a) => a.stil || "")).size > 1;
  for (const a of d.adaylar) parcalar.push(adayKutu(d, a, duzenlenebilir, stilFarkli));
  if (!d.adaylar.length && !d.hata) parcalar.push(el("p", { class: "ipucu" }, "Adaylar henüz üretilmedi. Üretim GPU boşken arka planda çalışır."));
  if (!["reddedildi", "yuklendi"].includes(d.asama)) {
    parcalar.push(el("div", { class: "alt-cubuk" },
      el("span", { class: "ipucu" }, d.asama === "onaylandi" ? `Onaylanan: aday ${d.secilen}. Paket sonraki koşuda hazırlanır.` : "Dalga üzerinde sürükle: aralık seç · Boşluk: çal/durdur"),
      el("span", { class: "bosluk" }),
      el("button", { class: "dugme tehlike", type: "button", onclick: () => reddet(d) }, "Şarkıyı reddet")));
  }
  ana.replaceChildren(...parcalar);
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
      "Yeni stil kaydedildi. İki aday sonraki koşuda üretilecek; mevcut adaylar yerinde kalır.");
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
      el("p", { class: "ipucu" }, "Mevcut adaylar silinmez; yeni iki aday onların ardından eklenir. Boş bırakılan BPM ve ton modele bırakılır.")));
}

function rozetler(kapilar) {
  return Object.entries(kapilar || {}).map(([ad, v]) => el("span", { class: `rozet ${v.gecti ? "ok" : "no"}` },
    `${KAPI[ad] || ad} ${v.deger != null ? String(v.deger).replace(".", ",") : ""} ${v.gecti ? "✓" : "✗"}`));
}

function adayKutu(d, a, duzenlenebilir, stilFarkli) {
  const baslik = `Aday ${a.no}`;
  if (!a.dosya) return el("section", { class: "serit dusen" }, el("div", { class: "serit-ust" }, el("h2", {}, baslik), ...rozetler(a.kapilar)));
  const s = new Serit({ kimlik: d.kimlik, dosya: a.dosya, secilebilir: duzenlenebilir && a.gecti, etiket: baslik });
  const onar = el("button", { class: "dugme ikincil", type: "button", disabled: true, onclick: () => onarimIste(d, a, s.secim) }, "Bu aralığı onar");
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
  const kabul = o.durum === "hazir" ? el("button", { class: "dugme ikincil", type: "button", onclick: () => onarimKabul(d, a, o) }, "Bunu kabul et") : null;
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
const onayVer = (d, a) => eylem(d, "onayla", { aday: a.no }, `Aday ${a.no} onaylandı. Yükleme paketi sonraki koşuda hazırlanır.`);
function reddet(d) {
  const neden = prompt(`"${d.ad}" reddedilsin mi? İstersen nedenini yaz (boş bırakabilirsin).`);
  if (neden === null) return;
  eylem(d, "reddet", { neden }, `"${d.ad}" reddedildi.`);
}

// ---- kuyruk ----
async function listeGoster(secili) {
  const liste = await api("/api/sarkilar");
  $("#liste-bos").hidden = liste.length > 0;
  $("#liste").replaceChildren(...liste.map((s) => el("li", {},
    el("a", { href: `#${s.kimlik}`, "aria-current": s.kimlik === secili ? "page" : false },
      el("span", { class: "ad" }, s.ad),
      el("span", { class: "alt" }, s.sanatci, el("span", { class: "asama", "data-a": s.asama }, ASAMA[s.asama] || s.asama))))));
}

async function yenile(kimlik = decodeURIComponent(location.hash.slice(1))) {
  await listeGoster(kimlik);
  if (kimlik) await sarkiGoster(kimlik);
}
addEventListener("hashchange", () => { calan?.ses.pause(); yenile().then(() => $("#ana").focus()); });
yenile().catch((e) => bildir(`Sunucuya ulaşılamadı: ${e.message}`, true));
// arka planda ilerleyen aşamaları kuyrukta göster (oynatmayı bölmeden yalnız listeyi yeniler)
setInterval(() => listeGoster(decodeURIComponent(location.hash.slice(1))).catch(() => {}), 30000);
