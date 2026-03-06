import unittest

from image_gen import build_pollinations_url, extract_image_prompt, is_image_request
from stoic_ai import StoicJudge


class ImageGenTests(unittest.TestCase):
    def test_detect_image_request(self):
        self.assertTrue(is_image_request("Нарисуй стоика на закате"))
        self.assertTrue(is_image_request("сгенерируй космический Рим"))
        self.assertFalse(is_image_request("просто текст"))

    def test_extract_prompt(self):
        self.assertEqual(extract_image_prompt("нарисуй: храм и бурю"), "храм и бурю")

    def test_pollinations_url(self):
        url = build_pollinations_url("римский форум")
        self.assertIn("image.pollinations.ai", url)
        self.assertIn("%20", url)


class FallbackTests(unittest.TestCase):
    def test_fallback_contains_verdict(self):
        judge = StoicJudge()
        text = judge._fallback_reply("я выбираю лень и прокрастинацию")
        self.assertIn("Марк Аврелий", text)
        self.assertTrue("доволен" in text or "недоволен" in text)


if __name__ == "__main__":
    unittest.main()
