from yanki import routenote


def test_kisi_adi_takma_adi_atar():
    assert routenote.kisi_adi("Joseph “Joe”") == "Joseph"
    assert routenote.kisi_adi('Chester "Chaz" Bennington') == "Chester Bennington"
    assert routenote.kisi_adi("David Michael (Phoenix)") == "David Michael"
    assert routenote.kisi_adi("Adele") == "Adele"


def test_yazarlar_temiz_ad_soyad():
    meta = {"orijinal_yazar_adlari": [["Joseph “Joe”", "Hahn"], ["Mike", "Shinoda"]]}
    assert routenote.yazarlar(meta) == [("Joseph", "Hahn"), ("Mike", "Shinoda")]
