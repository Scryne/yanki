// Bulucu'nun Spotify sayfasında koşan yardımcısı: yanki/bulucu.py yükler, __SURUM__ = bulucu.YARDIMCI_SURUM.
// STILLMORE'un window.Stillmore API'si (v12.x); sonuçlar burada kırpılır. Tek ifade (CDP Runtime.evaluate).
(() => {
  if (window.__yanki && window.__yanki.surum === __SURUM__) return true;
  const S = () => { if (!window.Stillmore || !window.Stillmore.track) throw new Error("STILLMORE yüklenmedi"); return window.Stillmore; };
  const resim = (u) => {
    u = String(u || "");
    if (u.startsWith("spotify:image:")) return "https://i.scdn.co/image/" + u.slice(14);
    if (u.startsWith("spotify:mosaic:")) return "https://mosaic.scdn.co/640/" + u.slice(15).split(":").join("");
    return /^https:\/\//.test(u) ? u : "";
  };
  const pencere = (w) => w ? { durum: w.status, en_az: w.daysMin, en_cok: w.daysMax, son_acik: w.lastOnline,
    ilk_kapali: w.goneSeen, sayi_duruyor: w.countRetained ?? null } : null;
  const is = { no: 0, durum: "bos" };
  const ilerle = (bitti, toplam, etiket) => { is.ilerleme = { bitti, toplam, etiket: etiket || (is.ilerleme && is.ilerleme.etiket) || "" }; };
  const satir = (x) => {
    const r = x.removed || {};
    return { id: x.trackId, ad: x.name, sanatci: x.artist, sanatci_id: x.artistId || null, album: x.album, album_id: x.albumId || null,
      resim: resim(x.art), eklendi: x.addedAt || null, neden: r.reasonCode || null, neden_ham: r.reasonRaw || null,
      dinlenme: r.plays ?? null, isrc: r.isrc || x.isrc || null, distributor: r.distributor || x.distributor || null,
      guven: r.confidence || null, label: r.label || null, cikis: r.releaseDate || null, ilk_yayin: r.earliestLive || null,
      sanatci_dinleyici: r.artistListeners ?? null, pencere: pencere(r.window),
      kopyalar: (r.reuploads || []).map((u) => ({ id: u.id, album: u.album || "", distributor: u.distributor || null })) };
  };
  const islemler = {
    async parca(id) {
      ilerle(0, 2, "Parça bilgisi okunuyor");
      const d = await S().track.analyze(id, { deep: true });
      ilerle(1, 2, "Aynı ISRC'li yüklemeler aranıyor");
      let kopyalar = [];
      if (d.isrc) {
        const h = await S().search.isrc(d.isrc).catch(() => []);
        kopyalar = h.filter((x) => x.id && x.id !== id).slice(0, 10).map((x) => ({ id: x.id, ad: x.name, sanatci: x.artist,
          album: x.album || "", resim: resim(x.art), calinir: x.playable ?? null }));
      }
      const rol = (re) => [...new Set(((d.credits && d.credits.roles) || []).filter((r) => re.test(r.role)).flatMap((r) => r.names))];
      const m = d.markets, ib = d.isrcInfo;
      return { tur: "parca", id, ad: d.name, sanatci: d.artist, sanatcilar: (d.artists || []).filter((a) => a.id),
        album: d.album, album_id: d.albumId, album_turu: d.albumType || null, resim: resim(d.artworkUrl),
        isrc: d.isrc || null, isrc_bilgi: ib ? { ulke: ib.countryName || ib.country || null, kayit: ib.registrant || null, yil: ib.year || null } : null,
        upc: d.upc || null, label: d.label || null, cikis: d.releaseDate || null, ilk_yayin: d.earliestLive || null,
        dinlenme: d.playCount ?? null, calinir: d.playable ?? null, calinma_nedeni: d.playReason || null, acik_icerik: !!d.explicit,
        sure_ms: (d.audio && d.audio.duration_ms) || null, tempo: (d.audio && d.audio.tempo) || null, ton: (d.audio && d.audio.keyName) || null,
        populerlik: d.popularity ?? null, diller: d.languages || [],
        distributor: d.distributor || null, guven: S().confidenceText(d), guven_kod: d.confidence || null, licensor: d.licensorUuid || null,
        oneri: d.suggestion ? d.suggestion.name : null,
        pazar: m && (m.allowed.length || m.forbidden.length) ? S().util.countryList(m) : null,
        yazarlar: rol(/writ|compos|lyric|söz|beste/i), yapimcilar: rol(/produc|yapımcı/i),
        telif_p: d.copyrightP || null, telif_c: d.copyrightC || null, pencere: pencere(d.window), kopyalar };
    },
    async playlist(id) {
      ilerle(0, 0, "Playlist okunuyor");
      const bilgi = await S().playlist.info(id);
      const r = await S().playlist.scan(id, { onProgress: (b, t, e) => ilerle(b, t, e) });
      const kalkan = r.rows.filter((x) => x.playable === false);
      return { tur: "playlist", id, ad: bilgi.name, sahip: bilgi.owner, resim: resim(bilgi.image), toplam: r.rows.length,
        takipci: bilgi.followers ?? null, satirlar: kalkan.map(satir) };
    },
    async sanatci(id) {
      ilerle(0, 1, "Sanatçı özeti okunuyor");
      const o = await S().artist.overview(id, true);
      return { tur: "sanatci", id, ad: o.name, dogrulanmis: !!o.verified, resim: resim(o.avatar), dinleyici: o.monthlyListeners ?? null,
        takipci: o.followers ?? null, dunya_sirasi: o.worldRank || null, yayin_sayisi: o.releaseCount ?? null,
        album_sayisi: o.albumCount ?? null, single_sayisi: o.singleCount ?? null,
        son_yayin: o.latestRelease ? { id: o.latestRelease.id, ad: o.latestRelease.name, tarih: o.latestRelease.date, tur: o.latestRelease.type } : null,
        sehirler: (o.topCities || []).map((c) => ({ sehir: c.city, ulke: c.country, dinleyici: c.listeners })),
        listeler: (o.discoveredOn || []).map((p) => ({ id: p.id, ad: p.name, sahip: p.owner, resim: resim(p.image) })) };
    },
    async katalog(id) {
      ilerle(0, 0, "Yayınlar listeleniyor");
      const r = await S().artist.scan(id, (b, t) => ilerle(b, t, "Yayınlar okunuyor"));
      const o = r.overview || {};
      return { tur: "katalog", id, ad: o.name || "", resim: resim(o.avatar), dinleyici: o.monthlyListeners ?? null,
        toplam_dinlenme: r.totals.plays, parca_sayisi: r.totals.tracks, ortalama_ara: r.cadence.avgDays, son_yayindan: r.cadence.sinceLast,
        zaman_cizelgesi: r.timeline.map((y) => ({ yil: y.year, dagilim: y.items.map((i) => ({ ad: i.label, sayi: i.value })) })),
        kopyalar: r.duplicates.map((d) => ({ tur: d.kind, parcalar: d.tracks.map((t) => ({ id: t.trackId, ad: t.name, yayin: t.release && t.release.name })) })),
        yayinlar: r.releases.map((y) => ({ id: y.id, ad: y.name, tur: y.type, tarih: y.date, label: y.label || null, upc: y.upc || null,
          resim: resim(y.artworkUrl), parcalar: y.tracks.map((t) => ({ id: t.trackId, ad: t.name, isrc: t.isrc || null, dinlenme: t.plays ?? null,
            distributor: t.distributor || null })) })) };
    },
    async album(id) {
      ilerle(0, 1, "Albüm okunuyor");
      const r = await S().album.scan(id);
      const i = r.info || {};
      return { tur: "album", id, ad: i.name, sanatci: (i.albumArtists || []).join(", "), resim: resim(i.artworkUrl), label: i.label || null,
        upc: i.upc || null, cikis: i.releaseDate || null, album_turu: i.albumType || null, telif_p: i.copyrightP || null,
        satirlar: r.rows.map((t) => ({ no: t.n, id: t.trackId, ad: t.name, sanatci: t.artist, isrc: t.isrc || null, dinlenme: t.plays ?? null,
          distributor: t.distributor || null, guven: t.confidence || null })) };
    },
    async isrc(kod) {
      ilerle(0, 1, "ISRC aranıyor");
      const h = await S().search.isrc(kod);
      return { tur: "isrc", id: kod, ad: kod, sonuclar: h.filter((x) => x.id).map((x) => ({ tur: "parca", id: x.id, ad: x.name, sanatci: x.artist,
        album: x.album || "", resim: resim(x.art), calinir: x.playable ?? null })) };
    },
    // liste keşfi: konu sorgularıyla Spotify istemcisinin kendi araması (searchDesktop, kotasız); her listenin takipçi
    // ve parça sayısı STILLMORE'dan (`playlist.info`), en popüler önce
    async listeler(a) {
      const tanim = Spicetify.GraphQL.Definitions.searchDesktop || { name: "searchDesktop", operation: "query",
        sha256Hash: "db61238974d27839a136c9dc02bfdbe3fab7635f21cf85976ebff9a1ee281345", value: null };
      const bulunan = new Map();
      for (const [i, q] of a.sorgular.entries()) {
        ilerle(i, a.sorgular.length, `"${q}" aranıyor`);
        const r = await Spicetify.GraphQL.Request(tanim, { searchTerm: q, offset: 0, limit: 20, numberOfTopResults: 5,
          includeAudiobooks: false, includePreReleases: false }).catch(() => null);
        for (const x of (r && r.data && r.data.searchV2 && r.data.searchV2.playlists && r.data.searchV2.playlists.items) || []) {
          const d = (x && x.data) || x;
          const id = String((d && d.uri) || "").split(":").pop();
          if (!/^[A-Za-z0-9]{22}$/.test(id) || bulunan.has(id)) continue;
          const kaynak = (((d.images || {}).items || [])[0] || {}).sources || [];
          bulunan.set(id, { id, ad: d.name || "", sahip: (((d.ownerV2 || {}).data) || {}).name || null,
            resim: resim((kaynak.find((s) => s.width >= 300) || kaynak[0] || {}).url),
            aciklama: String(d.description || "").replace(/<[^>]+>/g, "").slice(0, 200), sorgu: q });
        }
      }
      const konu = a.suzgec ? new RegExp(a.suzgec, "i") : null;
      const liste = [...bulunan.values()].filter((p) => !konu || konu.test(`${p.ad} ${p.aciklama}`)).slice(0, a.zengin || 80);
      for (const [i, p] of liste.entries()) {
        ilerle(i, liste.length, "Takipçi sayıları okunuyor");
        try { const b = await S().playlist.info(p.id); p.takipci = b.followers ?? null; p.toplam = b.total ?? null; p.sahip = p.sahip || b.owner || null; }
        catch (e) { p.takipci = null; }
      }
      liste.sort((x, y) => (y.takipci ?? -1) - (x.takipci ?? -1));
      return { tur: "listeler", id: a.konu, ad: a.ad, sorgular: a.sorgular, sonuclar: liste };
    },
    async upc(kod) {
      ilerle(0, 1, "UPC aranıyor");
      const h = await S().search.upc(kod);
      return { tur: "upc", id: kod, ad: kod, sonuclar: h.filter((x) => x.id).map((x) => ({ tur: "album", id: x.id, ad: x.name, sanatci: x.artist,
        album: [x.type, x.date].filter(Boolean).join(" · "), resim: resim(x.image), calinir: null })) };
    },
  };
  window.__yanki = {
    surum: __SURUM__,
    baslat(tur, kimlik, sinirMs) {
      // hiç bitmeyen bir söz (Promise) sayfa yenilenene kadar bütün aramaları kilitlemesin: süresi geçen iş bırakılır
      if (is.durum === "suruyor" && Date.now() - is.baslangic < (sinirMs || 45 * 60 * 1000))
        throw new Error("Spotify'da başka bir Bulucu işi sürüyor");
      if (!islemler[tur]) throw new Error("bilinmeyen tür: " + tur);
      const no = ++is.no;
      Object.assign(is, { durum: "suruyor", tur, kimlik, ilerleme: null, sonuc: null, hata: null, baslangic: Date.now() });
      islemler[tur](kimlik).then((r) => { if (is.no === no) Object.assign(is, { durum: "bitti", sonuc: r }); },
        (e) => { if (is.no === no) Object.assign(is, { durum: "hata", hata: String((e && e.message) || e) }); });
      return no;
    },
    durum() { return { no: is.no, durum: is.durum, ilerleme: is.ilerleme || null, hata: is.hata || null }; },
    sonuc(no) { if (is.no !== no) return null; const r = is.sonuc; is.sonuc = null; is.durum = "bos"; return r; },
    birak(no) { if (is.no === no && is.durum === "suruyor") Object.assign(is, { durum: "bos", sonuc: null }); return true; },
  };
  return true;
})()
