from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.common.paths import REPOSITORY_ROOT
from src.embeddings.embedder import OpenAIEmbeddingClient
from src.storage.chroma import (
    create_chroma_client,
    get_collection_if_exists,
)
from src.storage.tourapi import (
    TOURAPI_CHROMA_COLLECTION,
    chroma_config_from_env,
)


class TourAPIRetrieverError(RuntimeError):
    """TourAPI 장소 검색 과정에서 발생하는 오류."""


@dataclass(frozen=True)
class TourAPISearchResult:
    """
    ChromaDB에서 검색된 TourAPI 장소 한 건.
    """

    document_id: str
    document: str
    metadata: dict[str, Any]
    distance: float
    similarity: float

    @property
    def contentid(self) -> str:
        return str(self.metadata.get("contentid") or "")

    @property
    def title(self) -> str:
        return str(self.metadata.get("title") or "")

    @property
    def city(self) -> str:
        return str(self.metadata.get("city") or "")

    @property
    def district(self) -> str:
        return str(self.metadata.get("district") or "")

    @property
    def address(self) -> str:
        return str(self.metadata.get("address") or "")

    @property
    def latitude(self) -> float | None:
        return _to_float(self.metadata.get("latitude"))

    @property
    def longitude(self) -> float | None:
        return _to_float(self.metadata.get("longitude"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "contentid": self.contentid,
            "title": self.title,
            "document": self.document,
            "distance": self.distance,
            "similarity": self.similarity,
            "metadata": self.metadata,
        }


class TourAPIRetriever:
    """
    TourAPI 제주 장소 전용 Retriever.

    역할:
        1. 자연어 검색어 임베딩
        2. jeju_places 컬렉션 검색
        3. metadata 필터 적용
        4. 검색 결과 정리 및 중복 제거

    이 클래스는 여행 기간, 동행자, 이동수단을 직접 처리하지 않는다.
    """

    def __init__(
        self,
        *,
        env_file: str | Path | None = None,
        client: Any | None = None,
        collection: Any | None = None,
        embedder: OpenAIEmbeddingClient | None = None,
    ) -> None:
        if env_file is None:
            env_file = REPOSITORY_ROOT / ".env"

        self.config = chroma_config_from_env(
            env_file,
            project_root=REPOSITORY_ROOT,
        )

        if client is None:
            client = create_chroma_client(self.config)

        self.client = client

        collection_name = (
            self.config.collection_name
            or TOURAPI_CHROMA_COLLECTION
        )

        if collection is None:
            collection = get_collection_if_exists(
                self.client,
                collection_name,
            )

        if collection is None:
            raise TourAPIRetrieverError(
                "TourAPI Chroma 컬렉션을 찾을 수 없습니다.\n"
                f"컬렉션 이름: {collection_name}\n"
                "먼저 다음 명령어로 인덱스를 생성하세요.\n"
                "python -m scripts.indexing.build_tourapi_vector_index"
            )

        self.collection = collection
        self.collection_name = collection_name

        collection_metadata = self.collection.metadata or {}

        embedding_model = str(
            collection_metadata.get("embedding_model")
            or "text-embedding-3-small"
        )

        embedding_dimensions = _to_positive_int(
            collection_metadata.get("embedding_dimensions")
        )

        if embedder is None:
            embedder = OpenAIEmbeddingClient(
                api_key=self.config.openai_api_key,
                model=embedding_model,
                dimensions=embedding_dimensions,
            )

        self.embedder = embedder

    def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        fetch_k: int | None = None,
        city: str | None = None,
        district: str | None = None,
        target_collection: str | None = None,
        itinerary_role: str | None = None,
        place_subtype: str | None = None,
        schedule_eligible_only: bool = True,
        route_eligible_only: bool = True,
        primary_place_only: bool = True,
        exclude_contentids: set[str] | None = None,
    ) -> list[TourAPISearchResult]:
        """
        자연어 검색어를 이용하여 제주 장소를 검색한다.

        Args:
            query:
                자연어 검색 문장

            top_k:
                최종 반환할 장소 개수

            fetch_k:
                ChromaDB에서 우선 가져올 후보 개수.
                중복 제거와 제외 처리를 고려해 top_k보다 크게 설정한다.

            city:
                제주시 또는 서귀포시

            district:
                한림읍, 애월읍, 성산읍 등의 세부 지역

            target_collection:
                attractions, activities, restaurants,
                lodgings, shopping 중 하나

            itinerary_role:
                visit, activity, experience, meal,
                cafe_break, stay, shopping, market_visit 등

            place_subtype:
                attraction, culture, restaurant,
                cafe_tea, lodging 등의 세부 유형

            exclude_contentids:
                결과에서 제외할 TourAPI contentid 집합
        """

        normalized_query = query.strip()

        if not normalized_query:
            raise ValueError("검색어가 비어 있습니다.")

        if top_k <= 0:
            raise ValueError("top_k는 1 이상이어야 합니다.")

        if fetch_k is None:
            fetch_k = max(top_k * 3, 20)

        if fetch_k <= 0:
            raise ValueError("fetch_k는 1 이상이어야 합니다.")

        fetch_k = max(fetch_k, top_k)

        query_embeddings = self.embedder.embed(
            [normalized_query]
        )

        if len(query_embeddings) != 1:
            raise TourAPIRetrieverError(
                "검색어 임베딩을 정상적으로 생성하지 못했습니다."
            )

        where_filter = self._build_where_filter(
            city=city,
            district=district,
            target_collection=target_collection,
            itinerary_role=itinerary_role,
            place_subtype=place_subtype,
            schedule_eligible_only=schedule_eligible_only,
            route_eligible_only=route_eligible_only,
            primary_place_only=primary_place_only,
        )

        query_arguments: dict[str, Any] = {
            "query_embeddings": query_embeddings,
            "n_results": fetch_k,
            "include": [
                "documents",
                "metadatas",
                "distances",
            ],
        }

        if where_filter is not None:
            query_arguments["where"] = where_filter

        try:
            raw_results = self.collection.query(
                **query_arguments
            )
        except Exception as exc:
            raise TourAPIRetrieverError(
                f"ChromaDB 장소 검색에 실패했습니다: {exc}"
            ) from exc

        results = self._parse_results(raw_results)

        results = self._exclude_results(
            results,
            exclude_contentids or set(),
        )

        results = self._deduplicate_results(results)

        return results[:top_k]

    def search_attractions(
        self,
        query: str,
        *,
        top_k: int = 10,
        city: str | None = None,
        district: str | None = None,
        exclude_contentids: set[str] | None = None,
    ) -> list[TourAPISearchResult]:
        """
        관광 일정에 사용할 관광지 후보만 검색한다.
        """

        return self.search(
            query=query,
            top_k=top_k,
            city=city,
            district=district,
            target_collection="attractions",
            exclude_contentids=exclude_contentids,
        )

    def search_restaurants(
        self,
        query: str,
        *,
        top_k: int = 10,
        city: str | None = None,
        district: str | None = None,
        exclude_contentids: set[str] | None = None,
    ) -> list[TourAPISearchResult]:
        """
        음식점 후보만 검색한다.
        """

        return self.search(
            query=query,
            top_k=top_k,
            city=city,
            district=district,
            target_collection="restaurants",
            exclude_contentids=exclude_contentids,
        )

    def search_lodgings(
        self,
        query: str,
        *,
        top_k: int = 10,
        city: str | None = None,
        district: str | None = None,
        exclude_contentids: set[str] | None = None,
    ) -> list[TourAPISearchResult]:
        """
        숙박 후보만 검색한다.
        """

        return self.search(
            query=query,
            top_k=top_k,
            city=city,
            district=district,
            target_collection="lodgings",
            exclude_contentids=exclude_contentids,
        )

    def count(self) -> int:
        """
        현재 컬렉션에 저장된 전체 문서 수.
        """

        return int(self.collection.count())

    @staticmethod
    def _build_where_filter(
        *,
        city: str | None,
        district: str | None,
        target_collection: str | None,
        itinerary_role: str | None,
        place_subtype: str | None,
        schedule_eligible_only: bool,
        route_eligible_only: bool,
        primary_place_only: bool,
    ) -> dict[str, Any] | None:
        conditions: list[dict[str, Any]] = []

        if city:
            conditions.append(
                {"city": city.strip()}
            )

        if district:
            conditions.append(
                {"district": district.strip()}
            )

        if target_collection:
            conditions.append(
                {
                    "target_collection":
                        target_collection.strip()
                }
            )

        if itinerary_role:
            conditions.append(
                {
                    "itinerary_role":
                        itinerary_role.strip()
                }
            )

        if place_subtype:
            conditions.append(
                {
                    "place_subtype":
                        place_subtype.strip()
                }
            )

        if schedule_eligible_only:
            conditions.append(
                {"schedule_eligible": True}
            )

        if route_eligible_only:
            conditions.append(
                {"route_eligible": True}
            )

        if primary_place_only:
            conditions.append(
                {"is_primary_place": True}
            )

        if not conditions:
            return None

        if len(conditions) == 1:
            return conditions[0]

        return {
            "$and": conditions
        }

    @staticmethod
    def _parse_results(
        raw_results: dict[str, Any],
    ) -> list[TourAPISearchResult]:
        ids = _first_batch(raw_results.get("ids"))
        documents = _first_batch(
            raw_results.get("documents")
        )
        metadatas = _first_batch(
            raw_results.get("metadatas")
        )
        distances = _first_batch(
            raw_results.get("distances")
        )

        parsed_results: list[TourAPISearchResult] = []

        for index, document_id in enumerate(ids):
            document = _get_list_value(
                documents,
                index,
                default="",
            )

            raw_metadata = _get_list_value(
                metadatas,
                index,
                default={},
            )

            metadata = (
                dict(raw_metadata)
                if isinstance(raw_metadata, dict)
                else {}
            )

            raw_distance = _get_list_value(
                distances,
                index,
                default=math.inf,
            )

            try:
                distance = float(raw_distance)
            except (TypeError, ValueError):
                distance = math.inf

            parsed_results.append(
                TourAPISearchResult(
                    document_id=str(document_id),
                    document=str(document or ""),
                    metadata=metadata,
                    distance=distance,
                    similarity=_distance_to_similarity(
                        distance
                    ),
                )
            )

        return parsed_results

    @staticmethod
    def _exclude_results(
        results: list[TourAPISearchResult],
        exclude_contentids: set[str],
    ) -> list[TourAPISearchResult]:
        normalized_excluded_ids = {
            str(contentid).strip()
            for contentid in exclude_contentids
            if str(contentid).strip()
        }

        if not normalized_excluded_ids:
            return results

        return [
            result
            for result in results
            if result.contentid not in normalized_excluded_ids
        ]

    @staticmethod
    def _deduplicate_results(
        results: list[TourAPISearchResult],
    ) -> list[TourAPISearchResult]:
        unique_results: list[TourAPISearchResult] = []

        seen_contentids: set[str] = set()
        seen_titles: set[str] = set()

        for result in results:
            contentid = result.contentid.strip()
            normalized_title = (
                result.title.strip().casefold()
            )

            if contentid and contentid in seen_contentids:
                continue

            if (
                not contentid
                and normalized_title
                and normalized_title in seen_titles
            ):
                continue

            if contentid:
                seen_contentids.add(contentid)

            if normalized_title:
                seen_titles.add(normalized_title)

            unique_results.append(result)

        return unique_results


def _first_batch(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []

    if not value:
        return []

    first = value[0]

    if isinstance(first, list):
        return first

    return []


def _get_list_value(
    values: list[Any],
    index: int,
    *,
    default: Any,
) -> Any:
    if index >= len(values):
        return default

    value = values[index]

    if value is None:
        return default

    return value


def _distance_to_similarity(distance: float) -> float:
    """
    컬렉션이 cosine distance로 생성되었으므로
    유사도를 1 - distance로 변환한다.
    """

    if not math.isfinite(distance):
        return 0.0

    similarity = 1.0 - distance

    return max(
        0.0,
        min(1.0, similarity),
    )


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_positive_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None

    return number if number > 0 else None