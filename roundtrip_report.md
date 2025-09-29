# XML Roundtrip Fidelity Report

This document summarizes the results, progress, and outstanding issues related to ensuring a lossless roundtrip conversion from XML to JSON and back to XML.

## 1. Initial Goal

The primary goal was to fix the XML -> JSON -> XML conversion pipeline to be fully idempotent, meaning that an XML file, once converted to JSON and back to XML, should be semantically and structurally identical to the original. This is crucial for preventing data loss and ensuring the reliability of the generation scripts.

## 2. Progress and Actions Taken

A systematic approach was taken to diagnose and fix the conversion discrepancies:

- **Created a Test Suite:** A new test script, `tests/test_xml_roundtrip.py`, was created to automate the process of converting every `Case*.xml` file to JSON and back, and then structurally comparing the result to the original.

- **Upgraded XML Library:** The project was migrated from Python's standard `xml.etree.ElementTree` to the more powerful `lxml` library. This was a necessary step to handle XML comments and provide better control over serialization.

- **Fixed Floating-Point Precision:** An issue where numeric values (e.g., `1.20`) were being converted to floats and losing their trailing zeros (becoming `1.2`) was resolved by modifying `AutoXml_script/xml_to_json.py` to treat all attribute and text values as strings, thus preserving their original format.

- **Iterative Debugging:** The test suite was run repeatedly to uncover and diagnose issues. Several bugs were fixed, including:
    - An `AttributeError` in the test script itself.
    - Multiple syntax errors and incomplete logic introduced during my attempts to fix the conversion scripts.
    - A `cython_function_or_method` error caused by incorrect handling of `lxml` tag objects.

## 3. Current Status & Outstanding Issues

After several iterations of fixes, the test suite now produces a consistent set of failures. These errors provide a clear picture of the remaining work.

**Latest Test Results (Summary):**

The test run on `9/28/2025` resulted in **21 failed** test cases. The primary errors are:

1.  **`'list' object has no attribute 'get'`**: This is the most prevalent error, indicating a fundamental mismatch between how the refactored `xml_to_json.py` creates JSON and how `generate_xml.py` expects to consume it. The builder script is attempting dictionary operations on list objects, a direct result of changes made to preserve comment and element order.

2.  **`Child count mismatch`**: These errors are symptoms of the same core issue as above. Comments are being misplaced or dropped during the list/dictionary confusion, altering the structure of the document.

3.  **`Tag mismatch at /case/execution/special/gauges/swl: pointdp != point0`**: A specific parsing error in `_parse_gauges` in the `xml_to_json.py` script. The tag `pointdp` is not being correctly handled.

## 4. Next Steps

The path forward is clear, but requires careful and precise implementation.

1.  **Fix the `'list' has no attribute 'get'` error:** This requires a comprehensive fix in `generate_xml.py`. The builder functions (like `_build_geometry_commands` and `_build_execution`) must be re-written to correctly process the list-based, order-preserving structure that the parser now generates. This is the highest priority as it will resolve the majority of failures.

2.  **Fix the `pointdp` Tag Mismatch:** Correct the logic in the `_parse_gauges` function in `xml_to_json.py` to correctly identify and process the `pointdp` tag.

3.  **Final Verification:** After these fixes are implemented, the `tests/test_xml_roundtrip.py` suite must be run again. The goal is to have all 21 tests pass, confirming that the roundtrip conversion is finally lossless.

This task has proven to be more complex than initially anticipated due to the intricacies of XML parsing and my own repeated errors in editing the files. The current state, however, provides a solid foundation for a final, successful resolution.
