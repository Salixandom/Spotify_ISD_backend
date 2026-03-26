from rest_framework import serializers
from .models import Playlist

class PlaylistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Playlist
        fields = '__all__'
        read_only_fields = ['owner_id', 'created_at', 'updated_at']
