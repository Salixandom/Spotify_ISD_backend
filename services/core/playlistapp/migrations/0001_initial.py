from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Playlist',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('owner_id', models.IntegerField()),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(default='')),
                ('visibility', models.CharField(choices=[('public', 'Public'), ('private', 'Private')], default='public', max_length=10)),
                ('playlist_type', models.CharField(choices=[('solo', 'Solo'), ('collaborative', 'Collaborative')], default='solo', max_length=15)),
                ('cover_url', models.URLField(blank=True, default='', max_length=500)),
                ('max_songs', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddIndex(
            model_name='playlist',
            index=models.Index(fields=['owner_id'], name='playlist_owner_idx'),
        ),
        migrations.AddIndex(
            model_name='playlist',
            index=models.Index(fields=['name'], name='playlist_name_idx'),
        ),
        migrations.AddIndex(
            model_name='playlist',
            index=models.Index(fields=['created_at'], name='playlist_created_idx'),
        ),
        migrations.AddIndex(
            model_name='playlist',
            index=models.Index(fields=['updated_at'], name='playlist_updated_idx'),
        ),
        migrations.AddIndex(
            model_name='playlist',
            index=models.Index(fields=['playlist_type'], name='playlist_type_idx'),
        ),
    ]
