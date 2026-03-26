import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('searchapp', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Play',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('user_id', models.IntegerField()),
                (
                    'song',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='plays',
                        to='searchapp.song',
                    ),
                ),
                ('played_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AddIndex(
            model_name='play',
            index=models.Index(
                fields=['user_id', '-played_at'],
                name='histapp_play_user_played_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='play',
            index=models.Index(
                fields=['song', '-played_at'],
                name='histapp_play_song_played_idx',
            ),
        ),
    ]
