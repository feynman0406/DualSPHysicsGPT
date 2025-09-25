import unittest

from chains.generator import sanitize_newvarcte


class TestPredefinitionSanitizer(unittest.TestCase):
    def test_convert_simple_name_value_selfclosing(self):
        inp = (
            '<predefinition>'
            '<newvarcte name="mdbc" value="false"/>'
            '</predefinition>'
        )
        # sanitize_newvarcte expects raw XML, not HTML-escaped. Use raw for effective test.
        raw_inp = '<predefinition><newvarcte name="mdbc" value="false"/></predefinition>'
        out = sanitize_newvarcte(raw_inp)
        self.assertEqual(out, '<predefinition><newvarcte mdbc="false"/></predefinition>')

    def test_convert_with_extra_attrs_and_nonselfclosing(self):
        raw_inp = '<predefinition><newvarcte name=\'tank_min_x\' value="0.0" data="meta"></newvarcte></predefinition>'
        out = sanitize_newvarcte(raw_inp)
        # Attribute order: sanitizer preserves other attrs, removes name/value, appends X="Y" at end
        self.assertEqual(
            out,
            '<predefinition><newvarcte data="meta" tank_min_x="0.0"></newvarcte></predefinition>'
        )

    def test_idempotent_when_already_attribute_style(self):
        raw_inp = '<predefinition><newvarcte dom_padding="Dp"/></predefinition>'
        out = sanitize_newvarcte(raw_inp)
        self.assertEqual(out, raw_inp)

    def test_mixed_quotes_and_spacing(self):
        raw_inp = '<predefinition>\n  <newvarcte   name = "dom_padding"   value = \'0.01\'   />\n</predefinition>'
        out = sanitize_newvarcte(raw_inp)
        self.assertEqual(out, '<predefinition>\n  <newvarcte dom_padding="0.01"/>\n</predefinition>')


if __name__ == "__main__":
    unittest.main()
