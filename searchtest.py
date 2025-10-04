import os
from dotenv import load_dotenv
from rag.openai_file_search import get_file_id_to_name_map


def main() -> None:
    load_dotenv()
    vector_store_id = os.environ.get("OPENAI_RAG_VS_DESIGN_ID")
    if not vector_store_id:
        raise SystemExit("OPENAI_RAG_VS_DESIGN_ID is not set")

    mapping = get_file_id_to_name_map(vector_store_id)
    print(f"Total files indexed: {len(mapping)}")

    matches = [(fid, name) for fid, name in mapping.items() if name and "CaseDambreak2D" in name]
    if matches:
        print("Matches containing 'CaseDambreak2D':")
        for fid, name in matches:
            print(f"  {fid} -> {name}")
    else:
        print("No entries containing 'CaseDambreak2D'.")


if __name__ == "__main__":
    main()
