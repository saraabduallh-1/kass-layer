from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "demo_local"
pytestmark = pytest.mark.skipif(not (DATA / "index.json").exists(), reason="detector data not built (scripts/demo/build_*.py)")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from kass_layer.detector.api import app
    return TestClient(app)


def test_replaces_and_keeps_morphology(client):
    r = client.post("/analyse", json={"text": "درّبنا المودل على الداتا", "domain": "tech"}).json()
    assert r["suggested_text"] == "درّبنا النموذج على البيانات"
    assert [i["start"] for i in r["items"]] == [7, 18]


def test_context_picks_the_sense(client):
    def pick(text):
        items = client.post("/analyse", json={"text": text, "domain": "eng"}).json()["items"]
        return next(i for i in items if i["original"] == "الفيوز")["suggestion"]["term"]
    assert pick("الجندي ركب الفيوز في القذيفة قبل الإطلاق") == "فتيلة انفجار"
    assert pick("الفني فحص الفيوز في الدائرة الكهربائية للسيارة") in {"المصهر", "مصهر", "صهيرة"}


def test_plain_arabic_is_left_alone(client):
    r = client.post("/analyse", json={"text": "طلب مني المدير أراجع بنود الاتفاقية قبل الاجتماع", "domain": "tech"}).json()
    assert r["counts"]["replace"] == 0 and r["counts"]["review"] == 0


def test_rejects_bad_input(client):
    assert client.post("/analyse", json={"text": "x", "domain": "nope"}).status_code == 422
    assert client.post("/analyse", json={"text": "ا" * 6000}).status_code == 422


def test_everyday_arabic_word_follows_context(client):
    def found(text):
        items = client.post("/analyse", json={"text": text, "domain": "tech"}).json()["items"]
        return {i["original"]: i["suggestion"]["term"] for i in items if i["state"] != "std"}
    assert found("بنينا عميل ذكي يرد على استفسارات المستخدمين باستخدام نموذج لغوي كبير").get("عميل ذكي") == "وكيل ذكي"
    assert found("المودل والعميل يشتغلون مع بعض").get("والعميل") == "وكيل"  # a borrowed term (المودل) is context too
    assert "العميل" not in found("نحرص على رضا العميل في كل مراحل المشروع")


def test_unify_groups_forms_of_one_term(client):
    r = client.post("/unify", json={"text": "دربنا المودل على بيانات العملاء، ثم قارنّا الموديل الجديد بالنموذج القديم.", "domain": "tech"}).json()
    assert len(r["groups"]) == 1 and r["groups"][0]["keep"] == "نموذج"
    assert {f["form"] for f in r["groups"][0]["forms"]} == {"المودل", "الموديل", "بالنموذج"}


def test_unify_spellings_outside_the_dictionaries(client):
    g = client.post("/unify", json={"text": "رفعنا الملفات على الدرايف، ثم شاركنا رابط Drive مع الفريق.", "domain": "tech"}).json()["groups"]
    assert len(g) == 1 and g[0]["kind"] == "spelling" and g[0]["review"]


def test_unify_leaves_inflection_and_glosses_alone(client):
    for text in ["البنك رفع الفائدة، والفائدة الجديدة تطبق من الشهر القادم.", "اشترينا لابتوب جديد للموظفين، واللابتوب القديم نقلناه للمخزن.",
                 "تطور الذكاء الاصطناعي (AI) بسرعة، وصار الذكاء الاصطناعي جزءًا من العمل."]:
        assert client.post("/unify", json={"text": text, "domain": "tech"}).json()["groups"] == []
