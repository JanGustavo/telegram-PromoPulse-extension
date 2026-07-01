import unittest

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

        # Configure WATCH_CONFIG for predictable test
        WATCH_CONFIG["active_levels"] = ["broad"]
        WATCH_CONFIG["broad_categories"] = ["celulares"]
        WATCH_CONFIG["price_max"] = 2000.0
        WATCH_CONFIG["min_score"] = 2
        WATCH_CONFIG["require_offer_match"] = True
        WATCH_CONFIG["relaxed_mode"] = False

        try:
            # Should match
            ok, meta = should_alert("Smartphone Samsung Galaxy por R$ 1.200 no link https://amazon.com")
            self.assertTrue(ok)
            self.assertEqual(meta["extracted_price"], 1200.0)

            # Price exceeds price_max
            ok, meta = should_alert("Smartphone Samsung Galaxy por R$ 2.500 no link https://amazon.com")
            self.assertFalse(ok)

            # Not matching category
            ok, meta = should_alert("Fralda Pampers por R$ 50 no link https://amazon.com")
            self.assertFalse(ok)
        finally:
            # Restore configuration
            WATCH_CONFIG.clear()
            WATCH_CONFIG.update(old_config)


if __name__ == "__main__":
    unittest.main()
