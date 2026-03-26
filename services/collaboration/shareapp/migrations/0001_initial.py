import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='ShareLink',
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
            model_name='sharelink',
            index=models.Index(fields=['token'], name='shareapp_sharelink_token_idx'),
        ),
        migrations.AddIndex(
            model_name='sharelink',
            index=models.Index(fields=['playlist_id', 'is_active'], name='shareapp_share_pl_active_idx'),
        ),
    ]
