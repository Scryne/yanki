"""Şarkı yapısı (yanki/yapi.py): zaman damgalı sözden ACE-Step bölüm etiketleri."""

from yanki import yapi


def _zamanla(satirlar, aralik=4.0, bas=12.0):
    """Satır listesi → [(sn, satır)]; "" boş satır (LRCLIB'de vokalin bittiği an), ("ara", sn) o kadar boşluk."""
    t, cikti = bas, []
    for s in satirlar:
        if isinstance(s, tuple):
            t += s[1]
            continue
        cikti.append((round(t, 2), s))
        t += aralik
    return cikti


def _adlar(bolumler):
    return [b.ad for b in bolumler]


def test_kita_nakarat_kopru_ve_enstrumantal_bolumler():
    nakarat = ["never mind I'll find someone like you", "I wish nothing but the best", "don't forget me I beg"]
    satirlar = _zamanla(["first verse line one", "first verse line two", "", ("ara", 4), *nakarat, "", ("ara", 12),
                         "second verse goes here", "second verse again", "", ("ara", 4), *nakarat, "",
                         ("ara", 4), "nothing compares no worries", "regrets and mistakes", "", ("ara", 4),
                         *nakarat, ""])
    b = yapi.coz(satirlar, sure_sn=satirlar[-1][0] + 20, ad="Someone Like You")
    assert _adlar(b) == ["Intro", "Verse 1", "Chorus", "Instrumental", "Verse 2", "Chorus", "Bridge", "Chorus",
                         "Outro"]
    assert b[2].satirlar[0][1] == nakarat[0] and not b[0].satirlar and not b[-1].satirlar
    metin = yapi.metin(b)
    assert metin.startswith("[Intro]\n\n[Verse 1]\nfirst verse line one") and "\n\n[Bridge]\nnothing" in metin


def test_on_nakarat_ve_sarki_adini_tasiyan_nakarat_ayrilir():
    # Somewhere Only We Know: "Oh simple thing" üç kez, ardından iki kez başlıklı nakarat; arada sınır yok
    on = ["oh simple thing where have you gone", "I'm getting old and I need something"]
    nak = ["and if you have a minute why don't we go", "talk about it somewhere only we know"]
    satirlar = _zamanla(["walked across an empty land", "knew the pathway", *on, "came across a fallen tree",
                         "felt the branches", *on, *nak, ("ara", 6), *on, *nak, ""])
    b = yapi.coz(satirlar, ad="Somewhere Only We Know")
    assert _adlar(b) == ["Intro", "Verse 1", "Pre-Chorus", "Verse 2", "Pre-Chorus", "Chorus", "Pre-Chorus", "Chorus"]


def test_sozleri_degisen_son_nakarat_cesitleme_sayilir():
    # When I Was Your Man: son nakarat aynı kalıpta başka sözlerle ("I hope he buys you flowers")
    nak = ["that I should've bought you flowers", "and held your hand", "should've gave you all my hours",
           "when I had the chance", "take you to every party"]
    son = ["I hope he buys you flowers", "I hope he holds your hand", "give you all his hours",
           "when he has the chance", "take to every party"]
    satirlar = _zamanla(["same bed but it feels bigger", "our song on the radio", ("ara", 6), *nak, ("ara", 6),
                         "my pride my ego my needs", "caused a good strong woman", ("ara", 6), *nak, ("ara", 6),
                         "although it hurts", "I'll be the first to say", ("ara", 6), *son, ("ara", 6),
                         "when I was your man", "when I was your man", ""])
    b = yapi.coz(satirlar, ad="When I Was Your Man")
    assert _adlar(b) == ["Intro", "Verse 1", "Chorus", "Verse 2", "Chorus", "Bridge", "Chorus", "Outro"]
    assert b[6].satirlar[0][1] == son[0]


def test_iki_nakarat_arasindaki_kita_kopru_sayilmaz_ve_kunye_satiri_atilir():
    nak = ["walking on air tonight", "feels like walking on air"]
    satirlar = _zamanla(["Feat. Snoop Dogg & Bella Blue", "falling lights from the sky", "lights so bright",
                         ("ara", 6), *nak, ("ara", 6), "second verse line", "and another one", ("ara", 6), *nak, ""])
    b = yapi.coz(satirlar)
    assert _adlar(b) == ["Intro", "Verse 1", "Chorus", "Verse 2", "Chorus"]
    assert b[1].satirlar[0][1] == "falling lights from the sky"


def test_zaman_damgasiz_soz_yalniz_tekrarlardan():
    b = yapi.coz([(None, x) for x in "a\nb\n\nn1\nn2\n\nc\nd\n\nn1\nn2".split("\n")])
    assert yapi.metin(b) == "[Verse 1]\na\nb\n\n[Chorus]\nn1\nn2\n\n[Verse 2]\nc\nd\n\n[Chorus]\nn1\nn2"
    assert yapi.coz([]) == [] and yapi.coz([(1.0, "♪"), (2.0, "")]) == []


def test_aralik_parcaya_dusen_satirlar_ve_enstrumantal_bolumler():
    nak = ["chorus line one", "chorus line two"]
    satirlar = _zamanla(["verse one", "verse two", *nak, "", ("ara", 20), "verse three", "verse four", *nak, ""])
    b = yapi.coz(satirlar)
    ara = next(x for x in b if x.ad == "Instrumental")
    assert yapi.aralik(b, 0, ara.bas) == ("[Intro]\n\n[Verse 1]\nverse one\nverse two\n\n[Chorus]\nchorus line one\n"
                                          "chorus line two")
    assert yapi.aralik(b, ara.bas, 999).startswith("[Instrumental]\n\n[Verse 2]\nverse three")
    assert yapi.aralik(b, 500, 999) == ""  # sözsüz parça: boş (çağıran [Instrumental] yazar)
