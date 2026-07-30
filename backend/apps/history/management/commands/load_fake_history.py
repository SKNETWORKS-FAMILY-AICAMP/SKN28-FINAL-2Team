import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.history.models import History


class Command(BaseCommand):
    help = "backend/fake_data.json 의 histories 데이터를 History 테이블에 적재합니다 (user 없이 code 기준으로 upsert)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=None,
            help="fake_data.json 경로 (기본값: BASE_DIR/fake_data.json)",
        )

    def handle(self, *args, **options):
        from django.conf import settings

        path = Path(options["path"]) if options["path"] else settings.BASE_DIR / "fake_data.json"

        if not path.exists():
            self.stderr.write(self.style.ERROR(f"파일을 찾을 수 없습니다: {path}"))
            return

        data = json.loads(path.read_text(encoding="utf-8"))
        histories = data.get("histories", [])

        created, updated = 0, 0
        for h in histories:
            obj, was_created = History.objects.update_or_create(
                code=h["id"],
                defaults={
                    "date": h["date"],
                    "time": h["time"],
                    "action": History.Action.VISIT,
                },
            )
            created += int(was_created)
            updated += int(not was_created)

        self.stdout.write(
            self.style.SUCCESS(f"histories 적재 완료: 생성 {created}건, 갱신 {updated}건 (총 {len(histories)}건)")
        )
