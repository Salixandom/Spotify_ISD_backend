import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Collaborator',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('playlist_id', models.IntegerField()),
                ('user_id', models.IntegerField()),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'unique_together': {('playlist_id', 'user_id')},
            },
        ),
        migrations.CreateModel(
            name='InviteLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('playlist_id', models.IntegerField()),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('created_by_id', models.IntegerField()),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.AddIndex(
            model_name='collaborator',
            index=models.Index(fields=['playlist_id'], name='collab_playlist_idx'),
        ),
        migrations.AddIndex(
            model_name='collaborator',
            index=models.Index(fields=['user_id'], name='collab_user_idx'),
        ),
        migrations.AddIndex(
            model_name='invitelink',
            index=models.Index(fields=['token'], name='invite_token_idx'),
        ),
        migrations.AddIndex(
            model_name='invitelink',
            index=models.Index(fields=['playlist_id', 'is_active'], name='invite_playlist_active_idx'),
        ),
    ]
