import os

from django.http import FileResponse
from rest_framework.views import APIView
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.db import connection
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes, OpenApiExample
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
        description='Uploads an audio file to the server for later playback. Supports MP3, WAV, OGG, and M4A formats. The file will be stored and can be streamed later using the stream endpoint. Maximum file size is 20MB. Title is required; artist, duration, and other metadata are optional.',
        request={
            'multipart/form-data': {
                'type': 'object',
                'required': ['file', 'title'],
                'properties': {
                    'file': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'Audio file to upload (MP3, WAV, OGG, M4A)'
                    },
                    'title': {
                        'type': 'string',
                        'description': 'Title of the audio file (max 255 characters)',
                        'maxLength': 255
                    },
                    'artist': {
                        'type': 'string',
                        'description': 'Artist name (optional, max 255 characters)',
                        'maxLength': 255
                    },
                    'duration_seconds': {
                        'type': 'integer',
                        'description': 'Duration in seconds (optional)',
                        'minimum': 0
                    }
                }
            }
        },
        examples=[
            OpenApiExample(
                'Upload MP3 with metadata',
                description='Upload an MP3 file with title and artist',
                value={
                    'file': 'song.mp3',
                    'title': 'Summer Vibes',
                    'artist': 'Cool Artist',
                    'duration_seconds': 210
                },
                media_type='multipart/form-data'
            ),
            OpenApiExample(
                'Upload with minimal info',
                description='Upload with only required fields',
                value={
                    'file': 'track.wav',
                    'title': 'My Recording'
                },
                media_type='multipart/form-data'
            )
        ],
        responses={
            201: {
                'type': 'object',
                'properties': {
                    'success': {
                        'type': 'boolean',
                        'example': True
                    },
                    'message': {
                        'type': 'string',
                        'example': 'Audio file uploaded successfully'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'id': {
                                'type': 'integer',
                                'description': 'Audio file ID',
                                'example': 123
                            },
                            'title': {
                                'type': 'string',
                                'example': 'Summer Vibes'
                            },
                            'artist': {
                                'type': 'string',
                                'example': 'Cool Artist'
                            },
                            'duration_seconds': {
                                'type': 'integer',
                                'example': 210
                            },
                            'file': {
                                'type': 'string',
                                'description': 'Path to stored file',
                                'example': '/media/audio/summer_vibes.mp3'
                            },
                            'uploaded_by_id': {
                                'type': 'integer',
                                'description': 'User ID who uploaded the file',
                                'example': 1
                            },
                            'uploaded_at': {
                                'type': 'string',
                                'format': 'date-time',
                                'example': '2026-04-07T10:00:00Z'
                            }
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'missing_file': {
                        'summary': 'No file provided',
                        'value': {
                            'success': False,
                            'message': 'Validation failed',
                            'errors': {
                                'file': ['This field is required.']
                            }
                        }
                    },
                    'missing_title': {
                        'summary': 'No title provided',
                        'value': {
                            'success': False,
                            'message': 'Validation failed',
                            'errors': {
                                'title': ['This field is required.']
                            }
                        }
                    },
                    'invalid_format': {
                        'summary': 'Unsupported file format',
                        'value': {
                            'success': False,
                            'message': 'Validation failed',
                            'errors': {
                                'file': ['File type .txt not allowed. Use: .mp3, .wav, .ogg, .m4a']
                            }
                        }
                    },
                    'file_too_large': {
                        'summary': 'File exceeds 20MB limit',
                        'value': {
                            'success': False,
                            'message': 'Validation failed',
                            'errors': {
                                'file': ['File size exceeds 20MB limit']
                            }
                        }
                    }
                }
            }
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
        description='Retrieves a list of all uploaded audio files in the system. Returns all files regardless of who uploaded them. Each file includes metadata such as title, artist, duration, file path, uploader information, and upload timestamp.',
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {
                        'type': 'boolean',
                        'example': True
                    },
                    'message': {
                        'type': 'string',
                        'example': 'Retrieved 3 audio files'
                    },
                    'data': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'id': {
                                    'type': 'integer',
                                    'description': 'Audio file ID',
                                    'example': 123
                                },
                                'title': {
                                    'type': 'string',
                                    'description': 'Title of the audio file',
                                    'example': 'Summer Vibes'
                                },
                                'artist': {
                                    'type': 'string',
                                    'description': 'Artist name',
                                    'example': 'Cool Artist'
                                },
                                'duration_seconds': {
                                    'type': 'integer',
                                    'description': 'Duration in seconds',
                                    'example': 210
                                },
                                'file': {
                                    'type': 'string',
                                    'description': 'Path to stored file',
                                    'example': '/media/audio/summer_vibes.mp3'
                                },
                                'uploaded_by_id': {
                                    'type': 'integer',
                                    'description': 'User ID who uploaded the file',
                                    'example': 1
                                },
                                'uploaded_at': {
                                    'type': 'string',
                                    'format': 'date-time',
                                    'description': 'When the file was uploaded',
                                    'example': '2026-04-07T10:00:00Z'
                                }
                            }
                        }
                    }
                }
            }
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
        description='Streams an audio file by its ID for playback in browsers or audio players. The endpoint returns the actual audio binary data with appropriate Content-Type headers based on the file format (audio/mpeg for MP3, audio/wav for WAV, audio/ogg for OGG, audio/mp4 for M4A). The Content-Disposition header is set to inline for direct browser playback. No authentication is required, making it accessible to public clients.',
        parameters=[
            OpenApiParameter(
                name='pk',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Audio file ID to stream',
                required=True,
                example=123
            )
        ],
        responses={
            200: {
                'description': 'Audio file binary data streamed with appropriate Content-Type header',
                'content': {
                    'audio/mpeg': {
                        'schema': {
                            'type': 'string',
                            'format': 'binary'
                        }
                    },
                    'audio/wav': {
                        'schema': {
                            'type': 'string',
                            'format': 'binary'
                        }
                    },
                    'audio/ogg': {
                        'schema': {
                            'type': 'string',
                            'format': 'binary'
                        }
                    },
                    'audio/mp4': {
                        'schema': {
                            'type': 'string',
                            'format': 'binary'
                        }
                    }
                },
                'headers': {
                    'Content-Type': {
                        'description': 'Audio MIME type based on file format',
                        'schema': {
                            'type': 'string',
                            'enum': ['audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/mp4']
                        }
                    },
                    'Content-Disposition': {
                        'description': 'File disposition for inline playback',
                        'schema': {
                            'type': 'string',
                            'example': 'inline; filename="Summer Vibes.mp3"'
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'not_found_in_db': {
                        'summary': 'Audio file ID not found in database',
                        'value': {
                            'success': False,
                            'message': 'Audio file not found'
                        }
                    },
                    'file_missing_on_disk': {
                        'summary': 'File exists in database but not on disk',
                        'value': {
                            'success': False,
                            'message': 'Audio file not found on disk'
                        }
                    }
                }
            }
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
