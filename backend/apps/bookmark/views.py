from django.shortcuts import get_object_or_404

from drf_spectacular.utils import extend_schema

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Bookmark
from .serializers import BookmarkCreateSerializer, BookmarkSerializer


class BookmarkListCreateAPIView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Bookmark"],
        summary="북마크 목록 조회",
        responses=BookmarkSerializer(many=True),
    )
    def get(self, request):
        bookmarks = Bookmark.objects.filter(user=request.user)
        return Response(BookmarkSerializer(bookmarks, many=True).data)

    @extend_schema(
        tags=["Bookmark"],
        summary="북마크 추가",
        request=BookmarkCreateSerializer,
        responses=BookmarkSerializer,
    )
    def post(self, request):
        serializer = BookmarkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        package_id = serializer.validated_data["package_id"]

        bookmark, created = Bookmark.objects.get_or_create(
            user=request.user,
            package_db_id=package_id,
        )

        return Response(
            BookmarkSerializer(bookmark).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class BookmarkDetailAPIView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Bookmark"],
        summary="북마크 삭제",
        responses={204: None},
    )
    def delete(self, request, pk):
        bookmark = get_object_or_404(
            Bookmark,
            pk=pk,
            user=request.user,
        )
        bookmark.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)