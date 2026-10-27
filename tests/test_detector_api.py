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
    assert found("بنينا عميل ذكي يرد على استفسارات المستخدمين باستخدام نموذج لغوي كبير").get("عميل") == "وكيل"
    assert "العميل" not in found("نحرص على رضا العميل في كل مراحل المشروع")
