import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Artist',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True)),
                ('image_url', models.URLField(blank=True, default='', max_length=500)),
                ('bio', models.TextField(default='')),
                ('monthly_listeners', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='Album',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('artist', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='albums', to='searchapp.artist')),
                ('name', models.CharField(max_length=255)),
                ('cover_url', models.URLField(blank=True, default='', max_length=500)),
                ('release_year', models.IntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'unique_together': {('artist', 'name')},
            },
        ),
        migrations.CreateModel(
            name='Song',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('artist', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='songs', to='searchapp.artist')),
                ('album', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='songs', to='searchapp.album')),
                ('title', models.CharField(max_length=255)),
                ('genre', models.CharField(default='', max_length=100)),
                ('release_year', models.IntegerField(blank=True, null=True)),
                ('duration_seconds', models.IntegerField(default=0)),
                ('cover_url', models.URLField(blank=True, default='', max_length=500)),
                ('audio_url', models.URLField(blank=True, default='', max_length=500)),
                ('storage_path', models.CharField(blank=True, default='', max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AddIndex(
            model_name='artist',
            index=models.Index(fields=['name'], name='searchapp_artist_name_idx'),
        ),
        migrations.AddIndex(
            model_name='album',
            index=models.Index(fields=['artist'], name='searchapp_album_artist_idx'),
        ),
        migrations.AddIndex(
            model_name='album',
            index=models.Index(fields=['name'], name='searchapp_album_name_idx'),
        ),
        migrations.AddIndex(
            model_name='song',
            index=models.Index(fields=['artist'], name='searchapp_song_artist_idx'),
        ),
        migrations.AddIndex(
            model_name='song',
            index=models.Index(fields=['album'], name='searchapp_song_album_idx'),
        ),
        migrations.AddIndex(
            model_name='song',
            index=models.Index(fields=['title'], name='searchapp_song_title_idx'),
        ),
        migrations.AddIndex(
            model_name='song',
            index=models.Index(fields=['genre'], name='searchapp_song_genre_idx'),
        ),
        migrations.AddIndex(
            model_name='song',
            index=models.Index(fields=['release_year'], name='searchapp_song_year_idx'),
        ),
    ]
