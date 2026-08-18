from typing import Optional, Type

from django.db.models import Model


class DatabaseRouter:
    """
    Django 서비스 모델은 default(accounts_db)에 저장하고,
    외부 여행 카탈로그 모델만 travel(tour_recommender)에서 조회한다.
    """

    travel_models = {
        ("travel", "place"),
        ("travel", "package"),
    }

    @classmethod
    def _is_travel_model(
        cls,
        model: Type[Model],
    ) -> bool:
        model_key = (
            model._meta.app_label,
            model._meta.model_name,
        )
        return model_key in cls.travel_models

    def db_for_read(
        self,
        model: Type[Model],
        **hints,
    ) -> Optional[str]:
        if self._is_travel_model(model):
            return "travel"

        return "default"

    def db_for_write(
        self,
        model: Type[Model],
        **hints,
    ) -> Optional[str]:
        if self._is_travel_model(model):
            return "travel"

        return "default"

    def allow_relation(
        self,
        obj1: Model,
        obj2: Model,
        **hints,
    ) -> Optional[bool]:
        db1 = self.db_for_read(obj1.__class__)
        db2 = self.db_for_read(obj2.__class__)

        if db1 == db2:
            return True

        # 서로 다른 물리 DB 간 Django ForeignKey 관계는 허용하지 않는다.
        return False

    def allow_migrate(
        self,
        db: str,
        app_label: str,
        model_name: Optional[str] = None,
        **hints,
    ) -> Optional[bool]:
        model_key = (
            app_label,
            model_name,
        )

        # 외부 관리 테이블은 Django migration 대상이 아니다.
        if model_key in self.travel_models:
            return False

        # Django가 관리하는 모든 테이블은 default에만 생성한다.
        return db == "default"