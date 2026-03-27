import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('playlistapp', '0001_initial'),
        ('searchapp', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Track',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('playlist', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tracks', to='playlistapp.playlist')),
                ('song', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='playlist_entries', to='searchapp.song')),
                ('added_by_id', models.IntegerField()),
                ('position', models.IntegerField(default=0)),
                ('added_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['position'],
                'unique_together': {('playlist', 'song')},
            },
        ),
        migrations.AddIndex(
            model_name='track',
            index=models.Index(fields=['playlist', 'position'], name='track_playlist_pos_idx'),
        ),
        migrations.AddIndex(
            model_name='track',
            index=models.Index(fields=['playlist', 'added_at'], name='track_playlist_added_idx'),
        ),
        migrations.AddIndex(
            model_name='track',
            index=models.Index(fields=['added_by_id'], name='track_added_by_idx'),
        ),
    ]
