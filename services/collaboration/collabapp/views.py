from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from .models import Collaborator, InviteLink
from .serializers import CollaboratorSerializer, InviteLinkSerializer


class GenerateInviteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, playlist_id):
        invite = InviteLink.objects.create(
            playlist_id=playlist_id, created_by_id=request.user.id
        )
        serializer = InviteLinkSerializer(invite)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class JoinView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, token):
        try:
            invite = InviteLink.objects.get(token=token, is_active=True)
            return Response({"playlist_id": invite.playlist_id, "valid": True})
        except InviteLink.DoesNotExist:
            return Response({"valid": False}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, token):
        try:
            invite = InviteLink.objects.get(token=token, is_active=True)
            collab, created = Collaborator.objects.get_or_create(
                playlist_id=invite.playlist_id,
                user_id=request.user.id,
                defaults={"role": "collaborator"},
            )
            serializer = CollaboratorSerializer(collab)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except InviteLink.DoesNotExist:
            return Response({"error": "Invalid link"}, status=status.HTTP_404_NOT_FOUND)


class CollaboratorListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, playlist_id):
        collabs = Collaborator.objects.filter(playlist_id=playlist_id)
        serializer = CollaboratorSerializer(collabs, many=True)
        return Response(serializer.data)

    def delete(self, request, playlist_id):
        user_id = request.query_params.get("user_id")
        Collaborator.objects.filter(playlist_id=playlist_id, user_id=user_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
