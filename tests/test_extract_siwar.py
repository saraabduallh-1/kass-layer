from kass_layer.dictionary.siwar import limit_entries, parse_siwar_entries


def test_parse_siwar_preserves_dictionary_entry_and_separate_senses():
    html = """
    <div class="lexical-entry-card">
      <div id="LE_abc" class="lexical-entry-card__header">
        <span class="lemma">نَمُوذَج</span>
      </div>
      <div id="LE_abc_DICT_Riyadh" class="lexical-entry-card__details">
        <a href="/public-dict-information/Riyadh">معجم الرياض للغة العربية المعاصرة</a>
        <div class="pos-style"><div class="item">اسم ذات</div></div>
        <div class="lexical-entry-card__details__sense">
          <div class="text-justify">١. <span ptooltip="التعريف">مثال للعمل.</span>
            <span class="synset-badge">العلاقات المجردة</span></div>
          <div class="lexical-entry-example">هذا نموذج.</div>
        </div>
        <div class="lexical-entry-card__details__sense">
          <div class="text-justify">٢. <span ptooltip="التعريف">مثال يُقتدى به.</span></div>
        </div>
      </div>
        <div id="LE_abc_DICT_Other" class="lexical-entry-card__details">
          <a href="/public-dict-information/Other">معجم آخر</a>
          <div class="lexical-entry-card__details__sense">
            <div class="text-justify">١. <span ptooltip="التعريف">تعريف من معجم آخر.</span></div>
          </div>
        </div>
    </div>
    <div class="lexical-entry-card">
      <div id="LE_other_DICT_Other" class="lexical-entry-card__details">
        <a href="/public-dict-information/Other">Other dictionary</a>
      </div>
    </div>
    """

    records = parse_siwar_entries(html, "نموذج", dictionary_id="Riyadh")

    assert len(records) == 2
    assert [record["entry_id"] for record in records] == ["LE_abc", "LE_abc"]
    assert [record["sense_number"] for record in records] == ["١", "٢"]
    assert [record["definition"] for record in records] == ["مثال للعمل.", "مثال يُقتدى به."]
    assert records[0]["term"] == "نَمُوذَج"
    assert records[0]["dictionary_id"] == "Riyadh"
    assert records[0]["semantic_field"] == "العلاقات المجردة"
    assert records[0]["morphology"] == ["اسم ذات"]
    assert records[0]["example"] == "هذا نموذج."
    assert records[0]["domain"] is None

    all_records = parse_siwar_entries(html, "نموذج")
    assert len(all_records) == 3
    assert all_records[2]["dictionary_id"] == "Other"
    assert all_records[2]["dictionary_name"] == "معجم آخر"


def test_limit_entries_keeps_all_senses_for_selected_entries():
    records = [
      {"dictionary_id": "Riyadh", "entry_id": "LE_one", "sense_number": "١"},
      {"dictionary_id": "Riyadh", "entry_id": "LE_one", "sense_number": "٢"},
      {"dictionary_id": "Riyadh", "entry_id": "LE_two", "sense_number": "١"},
      {"dictionary_id": "Other", "entry_id": "LE_one", "sense_number": "١"},
    ]

    assert limit_entries(records, 1) == [*records[:2], records[3]]