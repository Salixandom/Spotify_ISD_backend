from rest_framework import serializers
from .models import Play
from searchapp.serializers import SongSerializer


class PlaySerializer(serializers.ModelSerializer):
    song = SongSerializer(read_only=True)

    class Meta:
        model = Play
        fields = ["id", "user_id", "song", "played_at"]
        read_only_fields = ["user_id", "played_at"]
