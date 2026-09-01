from pathlib import Path

from presentation_engine.builders.deck_builder import DeckBuilder

CONTRACT_PATH = Path("data/input/fy27_strategy_agent_contract.json")


def main() -> int:
    result = DeckBuilder().build_from_contract_file(CONTRACT_PATH)

    print()
    print("Deck generated successfully")
    print(f"PPTX: {result.output_pptx_path}")
    print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())