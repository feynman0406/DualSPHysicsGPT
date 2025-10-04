"""Test script to validate the fixed XML file"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lxml import etree as ET
from AutoXml_script.generate_xml import validate_case_tree

def test_xml_file(xml_path: Path):
    """Test if an XML file passes validation"""
    try:
        # Parse the XML file
        tree = ET.parse(str(xml_path))
        root = tree.getroot()
        
        # Validate using our validation function
        errors = validate_case_tree(root)
        
        if errors:
            print(f"❌ Validation FAILED for {xml_path.name}")
            print("\nErrors found:")
            for i, error in enumerate(errors, 1):
                print(f"  {i}. {error}")
            return False
        else:
            print(f"✅ Validation PASSED for {xml_path.name}")
            print("  All validation checks passed successfully!")
            return True
            
    except Exception as e:
        print(f"❌ Error parsing or validating {xml_path.name}: {e}")
        return False

if __name__ == "__main__":
    xml_file = Path("logs/mvp/generated_case.xml")
    
    if not xml_file.exists():
        print(f"Error: File not found: {xml_file}")
        sys.exit(1)
    
    print(f"Testing XML file: {xml_file}\n")
    success = test_xml_file(xml_file)
    
    sys.exit(0 if success else 1)
