import os

from django.http import FileResponse
from rest_framework.views import APIView
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.db import connection
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from drf_spectacular.types import OpenApiTypes

from utils.responses import SuccessResponse, NotFoundResponse, ValidationErrorResponse
from .models import AudioFile
from .serializers import AudioFileSerializer, AudioFileUploadSerializer


ALLOWED_EXTENSIONS = [".mp3", ".wav", ".ogg", ".m4a"]


class AudioFileUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=['Media'],
        summary='Upload audio file',
        description='Uploads an audio file (MP3, WAV, OGG, M4A) to the server. Maximum file size: 20MB.',
        request=AudioFileUploadSerializer,
        responses={
            201: AudioFileSerializer,
            400: OpenApiTypes.OBJECT,
        }
    )
    def post(self, request):
        serializer = AudioFileUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return ValidationErrorResponse(errors=serializer.errors)

        uploaded_file = serializer.validated_data["file"]

        ext = os.path.splitext(uploaded_file.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return ValidationErrorResponse(
                errors={"file": f"File type {ext} not allowed. Use: {', '.join(ALLOWED_EXTENSIONS)}"}
            )

        audio = AudioFile.objects.create(
            title=serializer.validated_data["title"],
            artist=serializer.validated_data.get("artist", ""),
            file=uploaded_file,
            duration_seconds=serializer.validated_data.get("duration_seconds", 0),
            uploaded_by_id=request.user.id,
        )

        return SuccessResponse(
            data=AudioFileSerializer(audio).data,
            message="Audio file uploaded successfully",
            status_code=201,
        )


class AudioFileListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=['Media'],
        summary='List audio files',
        description='Retrieves a list of all uploaded audio files',
        responses={
            200: AudioFileSerializer(many=True),
        }
    )
    def get(self, request):
        files = AudioFile.objects.all()
        return SuccessResponse(
            data=AudioFileSerializer(files, many=True).data,
            message=f"Retrieved {files.count()} audio files",
        )


class AudioFileStreamView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Playback'],
        summary='Stream audio file',
        description='Streams an audio file by ID. Returns the file with appropriate Content-Type header for browser playback.',
        parameters=[OpenApiParameter(
            name='pk',
            type=int,
            location=OpenApiParameter.PATH,
            description='Audio file ID'
        )],
        responses={
            200: OpenApiTypes.BINARY,
            404: OpenApiTypes.OBJECT,
        }
    )
    def get(self, request, pk):
        try:
            audio = AudioFile.objects.get(pk=pk)
        except AudioFile.DoesNotExist:
            return NotFoundResponse(message="Audio file not found")

        if not audio.file or not os.path.exists(audio.file.path):
            return NotFoundResponse(message="Audio file not found on disk")

        ext = os.path.splitext(audio.file.name)[1].lower()
        content_types = {
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".ogg": "audio/ogg",
            ".m4a": "audio/mp4",
        }
        content_type = content_types.get(ext, "audio/mpeg")

        response = FileResponse(
            open(audio.file.path, "rb"),
            content_type=content_type,
        )
        response["Content-Disposition"] = f'inline; filename="{audio.title}{ext}"'
        return response


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
@extend_schema(
    tags=['Health'],
    summary='Health check',
    description='Checks if the playback service and database are running properly',
    responses={
        200: OpenApiTypes.OBJECT,
        503: OpenApiTypes.OBJECT,
    }
)
def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return Response(
            {
                "status": "healthy",
                "service": "playback",
                "database": "connected",
                "apps": ["playback"],
            }
        )
    except Exception as e:
        return Response(
            {
                "status": "unhealthy",
                "service": "playback",
                "database": "disconnected",
                "error": str(e),
            },
            status=503,
        )
