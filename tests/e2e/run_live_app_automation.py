"""Run repeatable end-to-end checks against the locally running Tamna Plan API.

The script creates one dedicated test user, exercises the real HTTP endpoints,
stores a JSON report, and removes all test data by deleting that user unless
``--keep-data`` is supplied.  It intentionally does not call social OAuth.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
import os
from pathlib import Path
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from apps.accounts.models import User  # noqa: E402


TEST_EMAIL = "codex.e2e@tamna-plan.local"
TEST_PASSWORD = "CodexE2E-2026!"
TEST_PROVIDER_ID = "codex-e2e-user"


class LiveAppRunner:
    def __init__(self, base_url: str, output: Path, keep_data: bool) -> None:
        self.base_url = base_url.rstrip("/")
        self.output = output
        self.keep_data = keep_data
        self.token: str | None = None
        self.results: list[dict[str, Any]] = []
        self.created_user_id: int | None = None
        self.package: dict[str, Any] | None = None
        self.itinerary: dict[str, Any] | None = None

    def record(
        self,
        tc_id: str,
        feature: str,
        expected: str,
        passed: bool,
        actual: str,
        elapsed_ms: float,
    ) -> None:
        self.results.append(
            {
                "tc_id": tc_id,
                "feature": feature,
                "expected": expected,
                "actual": actual,
                "status": "PASS" if passed else "FAIL",
                "elapsed_ms": round(elapsed_ms, 1),
            }
        )

    def call(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        authenticated: bool = True,
        timeout: int = 30,
    ) -> tuple[int, Any, float]:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if authenticated and self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        started = time.perf_counter()
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read()
                status = response.status
        except HTTPError as exc:
            raw = exc.read()
            status = exc.code
        except (URLError, TimeoutError) as exc:
            elapsed = (time.perf_counter() - started) * 1000
            return 0, {"detail": str(exc)}, elapsed

        elapsed = (time.perf_counter() - started) * 1000
        if not raw:
            return status, None, elapsed
        try:
            return status, json.loads(raw.decode("utf-8")), elapsed
        except (UnicodeDecodeError, json.JSONDecodeError):
            return status, raw.decode("utf-8", errors="replace"), elapsed

    def prepare_user(self) -> None:
        User.objects.filter(email=TEST_EMAIL).delete()
        user = User(
            email=TEST_EMAIL,
            nickname="E2E 여행자",
            provider="google",
            provider_id=TEST_PROVIDER_ID,
            preferred_style="healing",
        )
        user.set_password(TEST_PASSWORD)
        user.save()
        self.created_user_id = user.id

    def authenticate(self) -> None:
        status, data, elapsed = self.call(
            "POST",
            "/api/token/",
            {"email": TEST_EMAIL, "password": TEST_PASSWORD},
            authenticated=False,
        )
        passed = status == 200 and isinstance(data, dict) and bool(data.get("access"))
        if passed:
            self.token = data["access"]
        self.record(
            "TC-AUTH-02",
            "전용 테스트 사용자 JWT 발급",
            "HTTP 200 및 access token 반환",
            passed,
            f"HTTP {status}",
            elapsed,
        )

    def test_auth_guard(self) -> None:
        status, _, elapsed = self.call(
            "GET", "/api/travel/itineraries/", authenticated=False
        )
        self.record(
            "TC-AUTH-01",
            "인증 필요 기능 차단",
            "비로그인 일정 목록 요청 HTTP 401",
            status == 401,
            f"HTTP {status}",
            elapsed,
        )

    def test_profile(self) -> None:
        status, data, elapsed = self.call("GET", "/api/accounts/me/")
        self.record(
            "TC-ACC-01",
            "내 정보 조회",
            "현재 사용자의 이메일·닉네임·선호 스타일 반환",
            status == 200
            and data.get("email") == TEST_EMAIL
            and data.get("preferred_style") == "healing",
            f"HTTP {status}, email={data.get('email') if isinstance(data, dict) else None}",
            elapsed,
        )

        status, data, elapsed = self.call(
            "PATCH",
            "/api/accounts/me/",
            {"nickname": "자동화 여행자", "preferred_style": "activity"},
        )
        passed = (
            status == 200
            and data.get("nickname") == "자동화 여행자"
            and data.get("preferred_style") == "activity"
        )
        self.record(
            "TC-ACC-02",
            "내 정보 수정",
            "닉네임과 선호 여행 스타일 저장",
            passed,
            f"HTTP {status}, nickname={data.get('nickname') if isinstance(data, dict) else None}",
            elapsed,
        )

    def test_packages(self) -> None:
        status, data, elapsed = self.call(
            "GET", "/api/travel/packages/", authenticated=False
        )
        packages = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []
        passed = status == 200 and len(packages) > 0
        self.package = packages[0] if passed else None
        self.record(
            "TC-PKG-01",
            "패키지 목록 조회",
            "비로그인 상태에서 활성 패키지 목록 반환",
            passed,
            f"HTTP {status}, count={len(packages)}",
            elapsed,
        )
        if not self.package:
            return

        package_id = self.package["id"]
        status, detail, elapsed = self.call(
            "GET", f"/api/travel/packages/{package_id}/", authenticated=False
        )
        required = {"id", "package_id", "name", "price", "duration_days", "course"}
        passed = status == 200 and required.issubset(detail)
        self.record(
            "TC-PKG-02",
            "패키지 상세 조회",
            "상품 식별자·가격·기간·일정별 코스 반환",
            passed,
            f"HTTP {status}, fields={sorted(required.intersection(detail)) if isinstance(detail, dict) else []}",
            elapsed,
        )

        duration = self.package.get("duration_days")
        max_price = self.package.get("price")
        status, filtered, elapsed = self.call(
            "GET",
            f"/api/travel/packages/?duration_days={duration}&max_price={max_price}",
            authenticated=False,
        )
        filtered_list = filtered if isinstance(filtered, list) else []
        passed = status == 200 and all(
            item.get("duration_days") == duration and item.get("price", 0) <= max_price
            for item in filtered_list
        )
        self.record(
            "TC-PKG-03",
            "패키지 기간·가격 필터",
            "필터 조건을 만족하는 패키지만 반환",
            passed,
            f"HTTP {status}, count={len(filtered_list)}",
            elapsed,
        )

    def test_bookmarks(self) -> None:
        if not self.package:
            return
        package_id = self.package["id"]
        status, created, elapsed = self.call(
            "POST", "/api/bookmarks/", {"package_id": package_id}
        )
        bookmark_id = created.get("id") if isinstance(created, dict) else None
        passed = status == 201 and bookmark_id is not None
        self.record(
            "TC-BMK-01",
            "패키지 찜 추가",
            "유효한 패키지를 찜하고 상세 정보를 반환",
            passed,
            f"HTTP {status}, bookmark_id={bookmark_id}",
            elapsed,
        )

        status, _, elapsed = self.call(
            "POST", "/api/bookmarks/", {"package_id": package_id}
        )
        list_status, bookmarks, _ = self.call("GET", "/api/bookmarks/")
        same_package = [b for b in bookmarks if b.get("package_db_id") == package_id] if isinstance(bookmarks, list) else []
        self.record(
            "TC-BMK-02",
            "패키지 중복 찜 방지",
            "재요청은 HTTP 200이며 동일 패키지 찜은 1건 유지",
            status == 200 and list_status == 200 and len(same_package) == 1,
            f"HTTP {status}, saved_count={len(same_package)}",
            elapsed,
        )

        if bookmark_id:
            status, _, elapsed = self.call("DELETE", f"/api/bookmarks/{bookmark_id}/")
            self.record(
                "TC-BMK-03",
                "패키지 찜 해제",
                "본인 찜 항목 삭제 HTTP 204",
                status == 204,
                f"HTTP {status}",
                elapsed,
            )

    def test_cart_and_reservation(self) -> None:
        if not self.package:
            return
        package_id = self.package["id"]
        package_price = int(self.package.get("price") or 0)
        status, cart_item, elapsed = self.call(
            "POST", "/api/cart/", {"package_id": package_id}
        )
        cart_id = cart_item.get("id") if isinstance(cart_item, dict) else None
        self.record(
            "TC-CART-01",
            "장바구니 담기",
            "패키지 장바구니 추가 HTTP 201",
            status == 201 and cart_id is not None,
            f"HTTP {status}, cart_id={cart_id}",
            elapsed,
        )
        if not cart_id:
            return

        status, updated, elapsed = self.call(
            "PATCH",
            f"/api/cart/{cart_id}/",
            {"quantity": 2, "option_people": 4, "option_date": str(date.today() + timedelta(days=30))},
        )
        cart_status, cart, _ = self.call("GET", "/api/cart/")
        passed = (
            status == 200
            and updated.get("quantity") == 2
            and updated.get("option_people") == 4
            and cart_status == 200
            and cart.get("total_price") == package_price * 2
        )
        self.record(
            "TC-CART-02",
            "장바구니 옵션·수량 수정",
            "수량 2·인원 4 저장 및 총액 재계산",
            passed,
            f"HTTP {status}, total={cart.get('total_price') if isinstance(cart, dict) else None}",
            elapsed,
        )

        status, data, elapsed = self.call(
            "PATCH", f"/api/cart/{cart_id}/", {"quantity": 10}
        )
        self.record(
            "TC-CART-03",
            "장바구니 수량 검증",
            "허용 범위(1~9)를 벗어난 수량 HTTP 400",
            status == 400,
            f"HTTP {status}, detail={data}",
            elapsed,
        )

        status, reservation, elapsed = self.call(
            "POST",
            "/api/reservations/",
            {
                "cart_item_ids": [cart_id],
                "payment_method": "E2E 테스트 카드",
            },
        )
        reservation_id = reservation.get("id") if isinstance(reservation, dict) else None
        passed = (
            status == 201
            and reservation_id is not None
            and reservation.get("status") == "confirmed"
            and reservation.get("total_price") == package_price * 2
            and len(reservation.get("items", [])) == 1
        )
        self.record(
            "TC-RES-01",
            "장바구니 기반 예약 생성",
            "예약 확정·금액 스냅샷·예약 항목 생성",
            passed,
            f"HTTP {status}, reservation_id={reservation_id}, total={reservation.get('total_price') if isinstance(reservation, dict) else None}",
            elapsed,
        )
        if not reservation_id:
            return

        cart_status, cart, elapsed = self.call("GET", "/api/cart/")
        self.record(
            "TC-RES-02",
            "예약 후 장바구니 정리",
            "예약된 장바구니 항목 자동 삭제",
            cart_status == 200 and not cart.get("items"),
            f"HTTP {cart_status}, cart_items={len(cart.get('items', [])) if isinstance(cart, dict) else None}",
            elapsed,
        )

        status, cancelled, elapsed = self.call(
            "PATCH", f"/api/reservations/{reservation_id}/cancel/"
        )
        self.record(
            "TC-RES-03",
            "예약 취소",
            "확정 예약을 취소 상태로 변경",
            status == 200 and cancelled.get("status") == "cancelled",
            f"HTTP {status}, status={cancelled.get('status') if isinstance(cancelled, dict) else None}",
            elapsed,
        )

        status, _, elapsed = self.call(
            "PATCH", f"/api/reservations/{reservation_id}/cancel/"
        )
        self.record(
            "TC-RES-04",
            "예약 중복 취소 방지",
            "이미 취소된 예약 재취소 HTTP 400",
            status == 400,
            f"HTTP {status}",
            elapsed,
        )

    @staticmethod
    def api_days(days: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "day_number": day["day_number"],
                "date": day.get("date"),
                "items": [
                    {
                        "order": index,
                        "time": item.get("time", ""),
                        "item_type": item.get("item_type", "custom"),
                        "title": item.get("title", ""),
                        "description": item.get("description", ""),
                        "thumbnail": item.get("thumbnail", ""),
                        "spot": item.get("spot"),
                        "restaurant": item.get("restaurant"),
                        "accommodation": item.get("accommodation"),
                        "latitude": item.get("latitude"),
                        "longitude": item.get("longitude"),
                        "memo": item.get("memo", ""),
                    }
                    for index, item in enumerate(day.get("items", []))
                ],
            }
            for day in days
        ]

    def test_itinerary(self) -> None:
        status, _, elapsed = self.call(
            "POST",
            "/api/travel/itineraries/",
            {
                "start_date": str(date.today() + timedelta(days=30)),
                "companion_type": "friend",
                "style": "healing",
            },
            timeout=30,
        )
        self.record(
            "TC-ITI-01",
            "일정 생성 필수값 검증",
            "종료일 누락 요청 HTTP 400",
            status == 400,
            f"HTTP {status}",
            elapsed,
        )

        start = date.today() + timedelta(days=30)
        end = start + timedelta(days=2)
        status, itinerary, elapsed = self.call(
            "POST",
            "/api/travel/itineraries/",
            {
                "subtitle": "친구와 자동화 여행",
                "start_date": str(start),
                "end_date": str(end),
                "companion_type": "friend",
                "companion_count": 2,
                "style": "activity",
                "status": "draft",
                "is_public": False,
            },
            timeout=300,
        )
        days = itinerary.get("days", []) if isinstance(itinerary, dict) else []
        item_count = sum(len(day.get("items", [])) for day in days)
        passed = status == 201 and len(days) == 3 and item_count > 0
        self.itinerary = itinerary if passed else None
        self.record(
            "TC-ITI-02",
            "조건 기반 AI 일정 생성",
            "gpt-5-mini·RAG 파이프라인으로 2박 3일 일정 생성",
            passed,
            f"HTTP {status}, days={len(days)}, items={item_count}",
            elapsed,
        )
        if not self.itinerary:
            return

        itinerary_id = self.itinerary["id"]
        status, detail, elapsed = self.call(
            "GET", f"/api/travel/itineraries/{itinerary_id}/"
        )
        self.record(
            "TC-ITI-03",
            "생성 일정 저장·상세 조회",
            "생성 결과를 사용자 일정으로 저장하고 동일 ID 조회",
            status == 200 and detail.get("id") == itinerary_id and len(detail.get("days", [])) == 3,
            f"HTTP {status}, id={detail.get('id') if isinstance(detail, dict) else None}",
            elapsed,
        )

        status, route, elapsed = self.call(
            "GET", f"/api/travel/itineraries/{itinerary_id}/route/"
        )
        route_points = sum(len(day.get("points", [])) for day in route) if isinstance(route, list) else 0
        self.record(
            "TC-ITI-04",
            "DAY별 여행 동선 조회",
            "좌표가 포함된 경유지 2개 이상 반환",
            status == 200 and route_points >= 2,
            f"HTTP {status}, route_points={route_points}",
            elapsed,
        )

        status, share, elapsed = self.call(
            "POST", f"/api/travel/itineraries/{itinerary_id}/share/"
        )
        token = share.get("share_token") if isinstance(share, dict) else None
        public_status, public_data, _ = self.call(
            "GET",
            f"/api/travel/itineraries/shared/{token}/",
            authenticated=False,
        ) if token else (0, {}, 0)
        self.record(
            "TC-ITI-05",
            "일정 공유 링크",
            "공유 토큰 생성 후 비로그인 읽기 가능",
            status == 200 and public_status == 200 and public_data.get("id") == itinerary_id,
            f"share=HTTP {status}, public=HTTP {public_status}",
            elapsed,
        )

        status, recommendations, elapsed = self.call(
            "GET",
            f"/api/travel/itineraries/{itinerary_id}/package-recommendations/?top_k=3",
            timeout=120,
        )
        recs = recommendations.get("recommendations", []) if isinstance(recommendations, dict) else []
        self.record(
            "TC-ITI-06",
            "일정 맞춤 패키지 추천",
            "현재 일정 기준 추천 패키지 3건 반환",
            status == 200 and len(recs) == 3,
            f"HTTP {status}, recommendations={len(recs)}",
            elapsed,
        )

        day_one = self.itinerary["days"][0]
        original_titles = [item.get("title") for item in day_one.get("items", [])]
        if len(original_titles) >= 3:
            status, revised, elapsed = self.call(
                "POST",
                f"/api/travel/itineraries/{itinerary_id}/revise/",
                {"message": "DAY 1의 1번 일정과 3번 일정의 순서를 서로 바꿔주세요."},
                timeout=300,
            )
            revised_titles = [
                item.get("title")
                for item in revised.get("days", [{}])[0].get("items", [])
            ] if isinstance(revised, dict) and revised.get("days") else []
            expected = original_titles.copy()
            expected[0], expected[2] = expected[2], expected[0]
            self.record(
                "TC-ITI-07",
                "대화로 슬롯 순서 교체",
                "'1번과 3번 교체' 요청 후 DAY 1 두 슬롯 순서 변경",
                status == 200 and revised_titles[:3] == expected[:3],
                f"HTTP {status}, before={original_titles[:3]}, after={revised_titles[:3]}",
                elapsed,
            )

            latest_days = revised.get("days", []) if status == 200 and isinstance(revised, dict) else self.itinerary["days"]
            patched_days = self.api_days(latest_days)
            patched_days[0]["items"][0], patched_days[0]["items"][2] = (
                patched_days[0]["items"][2],
                patched_days[0]["items"][0],
            )
            for index, item in enumerate(patched_days[0]["items"]):
                item["order"] = index
            status, patched, elapsed = self.call(
                "PATCH",
                f"/api/travel/itineraries/{itinerary_id}/",
                {"days": patched_days},
                timeout=60,
            )
            patched_titles = [
                item.get("title")
                for item in patched.get("days", [{}])[0].get("items", [])
            ] if isinstance(patched, dict) and patched.get("days") else []
            source_titles = [item.get("title") for item in latest_days[0].get("items", [])]
            expected_patch = source_titles.copy()
            expected_patch[0], expected_patch[2] = expected_patch[2], expected_patch[0]
            self.record(
                "TC-ITI-08",
                "일정 데이터 슬롯 순서 저장",
                "PATCH로 DAY 1의 1·3번 항목을 교환해 영구 저장",
                status == 200 and patched_titles[:3] == expected_patch[:3],
                f"HTTP {status}, after={patched_titles[:3]}",
                elapsed,
            )

        status, _, elapsed = self.call(
            "DELETE", f"/api/travel/itineraries/{itinerary_id}/"
        )
        self.record(
            "TC-ITI-09",
            "일정 삭제",
            "본인 일정 삭제 HTTP 204",
            status == 204,
            f"HTTP {status}",
            elapsed,
        )

    def test_history(self) -> None:
        status, created, elapsed = self.call(
            "POST",
            "/api/history/",
            {"action": "chat_start", "detail": "E2E 일정 생성 테스트"},
        )
        list_status, histories, _ = self.call("GET", "/api/history/")
        created_id = created.get("id") if isinstance(created, dict) else None
        exists = any(row.get("id") == created_id for row in histories) if isinstance(histories, list) else False
        self.record(
            "TC-HIS-01",
            "사용자 이용 기록 저장·조회",
            "AI 대화 시작 기록 생성 후 본인 목록에서 조회",
            status == 201 and list_status == 200 and exists,
            f"create=HTTP {status}, list=HTTP {list_status}",
            elapsed,
        )

    def write_report(self) -> None:
        passed = sum(result["status"] == "PASS" for result in self.results)
        failed = len(self.results) - passed
        payload = {
            "executed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "base_url": self.base_url,
            "model": os.environ.get("OPENAI_CHAT_MODEL", "not-loaded-in-runner"),
            "summary": {"total": len(self.results), "passed": passed, "failed": failed},
            "results": self.results,
        }
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(payload["summary"], ensure_ascii=False))
        for result in self.results:
            print(f"{result['status']:4} {result['tc_id']} {result['feature']} - {result['actual']}")
        print(f"REPORT {self.output}")

    def cleanup(self) -> None:
        if self.keep_data:
            return
        User.objects.filter(email=TEST_EMAIL).delete()

    def run(self) -> int:
        try:
            self.prepare_user()
            self.test_auth_guard()
            self.authenticate()
            if not self.token:
                return 1
            self.test_profile()
            self.test_packages()
            self.test_bookmarks()
            self.test_cart_and_reservation()
            self.test_itinerary()
            self.test_history()
        finally:
            self.write_report()
            self.cleanup()
        return 0 if all(result["status"] == "PASS" for result in self.results) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "artifacts" / "test_results" / "live_app_e2e.json",
    )
    parser.add_argument("--keep-data", action="store_true")
    args = parser.parse_args()
    return LiveAppRunner(args.base_url, args.output.resolve(), args.keep_data).run()


if __name__ == "__main__":
    raise SystemExit(main())
