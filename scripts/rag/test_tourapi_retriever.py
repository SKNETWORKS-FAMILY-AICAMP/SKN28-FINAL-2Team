from __future__ import annotations

from src.rag import TourAPIRetriever


def main() -> None:
    retriever = TourAPIRetriever()

    print("=" * 80)
    print("TourAPI Retriever 테스트")
    print(f"Collection: {retriever.collection_name}")
    print(f"전체 문서 수: {retriever.count()}")
    print("=" * 80)

    results = retriever.search_attractions(
        query=(
            "제주에서 바다 풍경을 감상하고 "
            "사진을 찍기 좋은 관광지"
        ),
        top_k=5,
    )


    results = retriever.search(
        query="비 오는 날 갈 만한 곳",
        top_k=5,
        place_types=["attraction"],
    )

    if not results:
        print("검색 결과가 없습니다.")
        return

    for index, result in enumerate(
        results,
        start=1,
    ):
        metadata = result.metadata

        print()
        print(f"[{index}] {result.title}")
        print(f"문서 ID: {result.document_id}")
        print(f"TourAPI ID: {result.contentid}")
        print(f"유사도: {result.similarity:.4f}")
        print(f"거리값: {result.distance:.4f}")
        print(
            f"지역: {result.city} {result.district}"
        )
        print(f"주소: {result.address}")
        print(
            "장소 유형:",
            metadata.get("place_subtype", ""),
        )
        print(
            "운영시간:",
            metadata.get("opening_hours_raw", ""),
        )
        print(
            "휴무일:",
            metadata.get("closed_days_raw", ""),
        )
        print(
            "주차:",
            metadata.get("parking_raw", ""),
        )
        print(
            "홈페이지:",
            metadata.get("homepage", ""),
        )
        print(
            "이미지:",
            metadata.get("image_url", ""),
        )
        print("-" * 80)


if __name__ == "__main__":
    main()