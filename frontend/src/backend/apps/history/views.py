from django.utils import timezone

from drf_spectacular.utils import extend_schema

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import History
from .serializers import HistorySerializer


class HistoryListCreateAPIView(APIView):
    """GET: 내 이용 기록 조회 / POST: 이용 기록 남기기 (로그인 사용자 기준)."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=HistorySerializer(many=True))
    def get(self, request):
        histories = History.objects.filter(user=request.user)
        return Response(HistorySerializer(histories, many=True).data)

    @extend_schema(request=HistorySerializer, responses={201: HistorySerializer})
    def post(self, request):
        now = timezone.localtime()
        serializer = HistorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(
            user=request.user,
            date=serializer.validated_data.get("date") or now.date(),
            time=serializer.validated_data.get("time") or now.time(),
        )
        return Response(serializer.data, status=201)
