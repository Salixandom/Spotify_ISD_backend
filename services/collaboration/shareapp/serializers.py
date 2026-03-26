from rest_framework import serializers
from .models import ShareLink


class ShareLinkSerializer(serializers.ModelSerializer):
    is_valid = serializers.SerializerMethodField()

    class Meta:
        model            = ShareLink
        fields           = '__all__'
        read_only_fields = ['token', 'created_by_id', 'created_at', 'is_valid']

    def get_is_valid(self, obj):
        return obj.is_valid
