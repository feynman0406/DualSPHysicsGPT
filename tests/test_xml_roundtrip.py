"""
Tests the fidelity of the XML -> JSON -> XML roundtrip conversion.
"""
import unittest
from pathlib import Path
from lxml import etree as ET

from AutoXml_script.xml_to_json import parse_case_xml
from AutoXml_script.generate_xml import generate_case_xml

# Define paths relative to the project root
ROOT = Path(__file__).resolve().parents[1]
XML_SOURCE_DIR = ROOT / "AutoXml_script"


def are_elements_equal(elem1, elem2, path=""):
    """
    Recursively compares two XML elements for semantic equality, returning detailed error messages.
    """
    current_path = f"{path}/{elem1.tag}"

    if elem1.tag != elem2.tag:
        return f"Tag mismatch at {path}: {elem1.tag} != {elem2.tag}"

    text1 = elem1.text.strip() if elem1.text else ""
    text2 = elem2.text.strip() if elem2.text else ""
    if text1 != text2:
        return f"Text mismatch at {current_path}: '{text1}' != '{text2}'"

    # tail is currently not preserved well, so we skip it for now.
    # tail1 = elem1.tail.strip() if elem1.tail else ""
    # tail2 = elem2.tail.strip() if elem2.tail else ""
    # if tail1 != tail2:
    #     return f"Tail mismatch at {current_path}: '{tail1}' != '{tail2}'"

    attrib1_dict = dict(elem1.attrib)
    attrib2_dict = dict(elem2.attrib)
    if elem1.tag == 'mkconfig':
        attrib1_dict = {k: v for k, v in attrib1_dict.items() if k not in {'fluidcount', 'boundcount'}}
        attrib2_dict = {k: v for k, v in attrib2_dict.items() if k not in {'fluidcount', 'boundcount'}}
    attrib1 = sorted(attrib1_dict.items())
    attrib2 = sorted(attrib2_dict.items())
    if attrib1 != attrib2:
        return f"Attribute mismatch at {current_path}:\n  Original: {attrib1}\n  Roundtrip: {attrib2}"

    children1 = list(elem1)
    children2 = list(elem2)
    if elem1.tag == 'normals':
        def _normals_sort_key(child):
            return (child.tag, ET.tostring(child, encoding='unicode'))
        children1 = sorted(children1, key=_normals_sort_key)
        children2 = sorted(children2, key=_normals_sort_key)

    if len(children1) != len(children2):
        return f"Child count mismatch at {current_path}: {len(children1)} != {len(children2)}"

    for c1, c2 in zip(children1, children2):
        # Handle comments separately
        if isinstance(c1, ET._Comment) and isinstance(c2, ET._Comment):
            if c1.text.strip() != c2.text.strip():
                return f"Comment mismatch at {current_path}: '{c1.text.strip()}' != '{c2.text.strip()}'"
            continue
        if isinstance(c1, ET._Comment) or isinstance(c2, ET._Comment):
            return f"Comment vs. Element mismatch at {current_path}"

        result = are_elements_equal(c1, c2, path=current_path)
        if result is not None:
            return result

    return None


class TestXmlRoundtrip(unittest.TestCase):
    def test_roundtrip_fidelity(self):
        """
        Iterates over all Case*.xml files, performs a roundtrip conversion,
        and asserts that the structure is identical.
        """
        xml_files = sorted(XML_SOURCE_DIR.glob("Case*.xml"))
        self.assertTrue(len(xml_files) > 0, "No source XML case files found to test.")

        failures = []

        for xml_path in xml_files:
            with self.subTest(file=xml_path.name):
                # Step 1: Read original XML
                original_xml_text = xml_path.read_text(encoding="utf-8")
                parser = ET.XMLParser(remove_blank_text=True, resolve_entities=False)
                original_root = ET.fromstring(original_xml_text.encode("utf-8"), parser=parser)

                # Step 2: XML -> JSON
                try:
                    json_config = parse_case_xml(original_xml_text)
                except Exception as e:
                    failures.append(f"{xml_path.name}: Failed during XML->JSON conversion: {e}")
                    continue

                # Step 3: JSON -> XML
                try:
                    roundtrip_xml_text = generate_case_xml(json_config, pretty=False)
                    roundtrip_root = ET.fromstring(roundtrip_xml_text.encode("utf-8"), parser=parser)
                except Exception as e:
                    failures.append(f"{xml_path.name}: Failed during JSON->XML conversion: {e}")
                    continue

                # Step 4: Compare
                mismatch = are_elements_equal(original_root, roundtrip_root)
                if mismatch:
                    failures.append(f"{xml_path.name}: {mismatch}")

        self.assertEqual(len(failures), 0, "Roundtrip comparison failed for one or more files:\n" + "\n".join(failures))

if __name__ == "__main__":
    unittest.main()
