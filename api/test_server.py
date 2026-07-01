import unittest

from api import db
from api.server import (
    WATCH_CONFIG,
    _clean_product_name,
    _extract_price,
    _offer_score,
    group_passes_quality_filter,
    should_alert,
)


class TestServerLogic(unittest.TestCase):

    def test_extract_price(self):
        self.assertEqual(_extract_price("iPhone por apenas R$ 4.999,99 parcelado"), 4999.99)
        self.assertEqual(_extract_price("Saindo a R$ 250 no PIX"), 250.0)
        self.assertEqual(_extract_price("Custa 999 reais"), 999.0)
        self.assertEqual(_extract_price("Sem preço na mensagem"), None)
        self.assertEqual(_extract_price("De R$ 1.200 por R$ 999"), 999.0)

    def test_clean_product_name(self):
        self.assertEqual(
            _clean_product_name("AMAZON SOLTOU CUPOM\nPanela de Pressão Eletrica"),
            "Panela de Pressao Eletrica",
        )
        self.assertEqual(
            _clean_product_name("CERVEJA DE QUEM TRABALHA NO SABADO\nCerveja Heineken 350ml"),
            "Cerveja Heineken 350ml",
        )

    def test_group_passes_quality_filter(self):
        self.assertTrue(group_passes_quality_filter("Ofertas do Dia"))
        self.assertFalse(group_passes_quality_filter("Grupo de Apostas Bet365"))
        self.assertFalse(group_passes_quality_filter("Crypto Trade Brasil"))
        self.assertFalse(group_passes_quality_filter("Grupo 123"))

    def test_offer_score(self):
        text = "Celular em oferta por R$ 1.500 link https://amazon.com"
        score, cats = _offer_score(text)
        self.assertIn("celulares", cats)
        self.assertGreaterEqual(score, 3)

    def test_should_alert(self):
        # Backup configuration
        old_config = WATCH_CONFIG.copy()

        try:
            # Test Broad Level
            WATCH_CONFIG.clear()
            WATCH_CONFIG.update(
                {
                    "active_levels": ["broad"],
                    "broad_categories": ["celulares"],
                    "price_max": 2000.0,
                    "min_score": 2,
                    "require_offer_match": True,
                    "relaxed_mode": False,
                }
            )
            ok, meta = should_alert("Smartphone Samsung Galaxy por R$ 1.200 no link https://amazon.com")
            self.assertTrue(ok)
            self.assertEqual(meta["extracted_price"], 1200.0)

            # Price exceeds price_max
            ok, meta = should_alert("Smartphone Samsung Galaxy por R$ 2.500 no link https://amazon.com")
            self.assertFalse(ok)

            # Test Mid Level (brand categories + mid brands)
            WATCH_CONFIG.clear()
            WATCH_CONFIG.update(
                {
                    "active_levels": ["mid"],
                    "mid_categories": ["celulares"],
                    "mid_brands": ["Apple"],
                    "min_score": 2,
                    "require_offer_match": True,
                    "relaxed_mode": False,
                }
            )
            # Apple is in mid_brands and Celular is celulares category
            ok, meta = should_alert("Celular Apple por R$ 4.000 link https://amazon.com")
            self.assertTrue(ok)
            # Samsung is not in mid_brands
            ok, meta = should_alert("Celular Samsung por R$ 2.000 link https://amazon.com")
            self.assertFalse(ok)

            # Test Specific Level with custom price limit override
            WATCH_CONFIG.clear()
            WATCH_CONFIG.update(
                {
                    "active_levels": ["specific"],
                    "specific_models": ["iPhone 15 Pro Max : 5500", "Galaxy S24 : 3200"],
                    "price_max": 2000.0,
                    "min_score": 2,
                    "require_offer_match": True,
                    "relaxed_mode": False,
                }
            )
            # iPhone 15 Pro Max is R$ 4.800 (under specific limit 5500, even though over global limit 2000!)
            ok, meta = should_alert("Celular iPhone 15 Pro Max por R$ 4.800 no link https://amazon.com")
            self.assertTrue(ok)

            # Galaxy S24 is R$ 3.500 (over specific limit 3200)
            ok, meta = should_alert("Celular Galaxy S24 por R$ 3.500 no link https://amazon.com")
            self.assertFalse(ok)

            # Words out of order matching
            ok, meta = should_alert("Celular Max Pro 15 iPhone por R$ 5.000 no link https://amazon.com")
            self.assertTrue(ok)

        finally:
            # Restore configuration
            WATCH_CONFIG.clear()
            WATCH_CONFIG.update(old_config)

    def test_price_drop_calculation(self):
        db.init_db()
        db.clear_alerts()

        alert1 = {
            "group_id": 1234,
            "group_title": "Ofertas",
            "message": "iPhone 15 Pro Max por R$ 5.000",
            "message_id": 1,
            "extracted_price": 5000.0,
            "clean_title": "iPhone 15 Pro Max",
            "offer_score": 5,
        }
        db.save_alert(alert1)

        alert2 = {
            "group_id": 1234,
            "group_title": "Ofertas",
            "message": "iPhone 15 Pro Max por R$ 4.000",
            "message_id": 2,
            "extracted_price": 4000.0,
            "clean_title": "iPhone 15 Pro Max",
            "offer_score": 5,
        }
        db.save_alert(alert2)

        alerts = db.get_alerts(limit=5)
        item2 = next(a for a in alerts if a["message_id"] == 2)
        self.assertEqual(item2["price_drop_percentage"], 20)

        alert3 = {
            "group_id": 1234,
            "group_title": "Ofertas",
            "message": "iPhone 15 Pro Max por R$ 4.500",
            "message_id": 3,
            "extracted_price": 4500.0,
            "clean_title": "iPhone 15 Pro Max",
            "offer_score": 5,
        }
        db.save_alert(alert3)

        alerts = db.get_alerts(limit=5)
        item3 = next(a for a in alerts if a["message_id"] == 3)
        self.assertEqual(item3["price_drop_percentage"], 0)


if __name__ == "__main__":
    unittest.main()
