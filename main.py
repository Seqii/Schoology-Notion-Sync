from notion import NotionClient
from schoology import SchoologyClient
from sync import sync_assignments


def main() -> None:
    schoology = SchoologyClient()
    notion = NotionClient()

    sync_assignments(
        schoology,
        notion,
    )


if __name__ == "__main__":
    main()