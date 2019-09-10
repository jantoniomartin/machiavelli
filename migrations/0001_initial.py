# -*- coding: utf-8 -*-


from django.db import models, migrations
from django.conf import settings
import machiavelli.models


class Migration(migrations.Migration):

    dependencies = [
        ('condottieri_scenarios', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Assassin',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
            ],
        ),
        migrations.CreateModel(
            name='Assassination',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('ducats', models.PositiveIntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name='Configuration',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('finances', models.BooleanField(default=False, verbose_name='finances')),
                ('assassinations', models.BooleanField(default=False, help_text='will enable Finances', verbose_name='assassinations')),
                ('excommunication', models.BooleanField(default=False, verbose_name='excommunication')),
                ('special_units', models.BooleanField(default=False, help_text='will enable Finances', verbose_name='special units')),
                ('lenders', models.BooleanField(default=False, help_text='will enable Finances', verbose_name='money lenders')),
                ('unbalanced_loans', models.BooleanField(default=False, help_text='the credit for all players will be 25d', verbose_name='unbalanced loans')),
                ('conquering', models.BooleanField(default=False, verbose_name='conquering')),
                ('famine', models.BooleanField(default=False, verbose_name='famine')),
                ('plague', models.BooleanField(default=False, verbose_name='plague')),
                ('storms', models.BooleanField(default=False, verbose_name='storms')),
                ('strategic', models.BooleanField(default=False, verbose_name='strategic movement')),
                ('variable_home', models.BooleanField(default=False, help_text='conquering will be disabled', verbose_name='variable home country')),
                ('taxation', models.BooleanField(default=False, help_text='will enable Finances and Famine', verbose_name='taxation')),
                ('fow', models.BooleanField(default=False, help_text='each player sees only what happens near his borders', verbose_name='fog of war')),
                ('press', models.PositiveIntegerField(default=0, verbose_name='press', choices=[(0, 'Normal (private letters, anonymous gossip)'), (1, 'Gunboat diplomacy (no letters, no gossip)')])),
            ],
        ),
        migrations.CreateModel(
            name='Credit',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('principal', models.PositiveIntegerField(default=0)),
                ('debt', models.PositiveIntegerField(default=0)),
                ('season', models.PositiveIntegerField(choices=[(1, 'Spring'), (2, 'Summer'), (3, 'Fall')])),
                ('year', models.PositiveIntegerField(default=0)),
                ('repaid', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='Diplomat',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
            ],
            options={
                'verbose_name': 'diplomat',
                'verbose_name_plural': 'diplomats',
            },
        ),
        migrations.CreateModel(
            name='ErrorReport',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('description', models.TextField()),
                ('created_on', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'error report',
                'verbose_name_plural': 'error reports',
            },
        ),
        migrations.CreateModel(
            name='Expense',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('ducats', models.PositiveIntegerField(default=0)),
                ('type', models.PositiveIntegerField(choices=[(0, 'Famine relief'), (1, 'Pacify rebellion'), (2, 'Conquered province to rebel'), (3, 'Home province to rebel'), (4, 'Counter bribe'), (5, 'Disband autonomous garrison'), (6, 'Buy autonomous garrison'), (7, 'Convert garrison unit'), (8, 'Disband enemy unit'), (9, 'Buy enemy unit'), (10, 'Hire a diplomat in own area'), (11, 'Hire a diplomat in foreign area')])),
                ('confirmed', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='Game',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('title', models.CharField(help_text='max. 128 characters', unique=True, max_length=128, verbose_name='title')),
                ('slug', models.SlugField(help_text='4-20 characters, only letters, numbers, hyphens and underscores', unique=True, max_length=20, verbose_name='slug')),
                ('year', models.PositiveIntegerField(null=True, verbose_name='year', blank=True)),
                ('season', models.PositiveIntegerField(blank=True, null=True, verbose_name='season', choices=[(1, 'Spring'), (2, 'Summer'), (3, 'Fall')])),
                ('phase', models.PositiveIntegerField(default=0, null=True, verbose_name='phase', blank=True, choices=[(0, 'Inactive game'), (1, 'Military adjustments'), (2, 'Order writing'), (3, 'Retreats'), (4, 'Strategic movement')])),
                ('slots', models.SmallIntegerField(default=0, verbose_name='slots')),
                ('visible', models.BooleanField(default=False, help_text='if checked, it will be known who controls each country', verbose_name='visible')),
                ('map_outdated', models.BooleanField(default=False, verbose_name='map outdated')),
                ('time_limit', models.PositiveIntegerField(help_text='time available to play a turn', verbose_name='time limit', choices=[(43200, '1/2 day'), (86400, '1 day'), (172800, '2 days'), (259200, '3 days'), (604800, '7 days'), (900, 'Real time, 15 min')])),
                ('last_phase_change', models.DateTimeField(null=True, verbose_name='last phase change', blank=True)),
                ('created', models.DateTimeField(auto_now_add=True, verbose_name='creation date', null=True)),
                ('started', models.DateTimeField(null=True, verbose_name='starting date', blank=True)),
                ('finished', models.DateTimeField(null=True, verbose_name='ending date', blank=True)),
                ('autostart', models.BooleanField(default=True, verbose_name='autostart')),
                ('cities_to_win', models.PositiveIntegerField(default=15, help_text='cities that must be controlled to win a game', verbose_name='cities to win')),
                ('require_home_cities', models.BooleanField(default=False, verbose_name='require home cities')),
                ('extra_conquered_cities', models.PositiveIntegerField(default=0, verbose_name='extra conquered cities')),
                ('years_limit', models.PositiveIntegerField(default=0, verbose_name='years limit')),
                ('fast', models.BooleanField(default=False, verbose_name='fast')),
                ('uses_karma', models.BooleanField(default=True, verbose_name='uses karma')),
                ('paused', models.BooleanField(default=False, verbose_name='paused')),
                ('private', models.BooleanField(default=False, help_text='only invited users can join the game', verbose_name='private')),
                ('comment', models.TextField(help_text='optional comment for joining users', max_length=255, null=True, verbose_name='comment', blank=True)),
                ('version', models.PositiveIntegerField(default=machiavelli.models.get_default_version, verbose_name='rules version')),
                ('extended_deadline', models.BooleanField(default=False, verbose_name='extended deadline')),
                ('teams', models.PositiveIntegerField(default=0, verbose_name='teams')),
                ('created_by', models.ForeignKey(editable=False, to=settings.AUTH_USER_MODEL, verbose_name='created by', on_delete=models.CASCADE)),
                ('scenario', models.ForeignKey(verbose_name='scenario', to='condottieri_scenarios.Scenario', on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name': 'game',
                'verbose_name_plural': 'games',
            },
        ),
        migrations.CreateModel(
            name='GameArea',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('years', models.PositiveIntegerField(default=0)),
                ('standoff', models.BooleanField(default=False)),
                ('famine', models.BooleanField(default=False)),
                ('storm', models.BooleanField(default=False)),
                ('taxed', models.BooleanField(default=False)),
                ('board_area', models.ForeignKey(to='condottieri_scenarios.Area', on_delete=models.CASCADE)),
                ('game', models.ForeignKey(to='machiavelli.Game', on_delete=models.CASCADE)),
            ],
            options={
                'ordering': ['game', 'board_area'],
            },
        ),
        migrations.CreateModel(
            name='GameComment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('comment', models.TextField(verbose_name='comment')),
                ('after_game', models.BooleanField(default=False, verbose_name='sent after the game', editable=False)),
                ('submit_date', models.DateTimeField(auto_now_add=True, verbose_name='submission date')),
                ('is_public', models.BooleanField(default=True, verbose_name='is public')),
                ('game', models.ForeignKey(editable=False, to='machiavelli.Game', on_delete=models.CASCADE)),
                ('user', models.ForeignKey(editable=False, to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),
            ],
            options={
                'ordering': ['submit_date'],
                'verbose_name': 'Game comment',
                'verbose_name_plural': 'Game comments',
            },
        ),
        migrations.CreateModel(
            name='GameRoute',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('safe', models.BooleanField(default=True)),
                ('game', models.ForeignKey(to='machiavelli.Game', on_delete=models.CASCADE)),
                ('trade_route', models.ForeignKey(to='condottieri_scenarios.TradeRoute', on_delete=models.CASCADE)),
            ],
        ),
        migrations.CreateModel(
            name='Invitation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('message', models.TextField(default=b'', blank=True)),
                ('game', models.ForeignKey(to='machiavelli.Game', on_delete=models.CASCADE)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),
            ],
        ),
        migrations.CreateModel(
            name='Journal',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('content', models.TextField(default=b'', blank=True)),
                ('game', models.ForeignKey(to='machiavelli.Game', on_delete=models.CASCADE)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),
            ],
        ),
        migrations.CreateModel(
            name='Loan',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('debt', models.PositiveIntegerField(default=0)),
                ('season', models.PositiveIntegerField(choices=[(1, 'Spring'), (2, 'Summer'), (3, 'Fall')])),
                ('year', models.PositiveIntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('code', models.CharField(max_length=1, choices=[(b'H', 'Hold'), (b'B', 'Besiege'), (b'-', 'Advance'), (b'=', 'Conversion'), (b'C', 'Convoy'), (b'S', 'Support')])),
                ('type', models.CharField(blank=True, max_length=1, null=True, choices=[(b'A', 'Army'), (b'F', 'Fleet'), (b'G', 'Garrison')])),
                ('suborder', models.CharField(max_length=15, null=True, blank=True)),
                ('subcode', models.CharField(blank=True, max_length=1, null=True, choices=[(b'H', 'Hold'), (b'-', 'Advance'), (b'=', 'Conversion')])),
                ('subtype', models.CharField(blank=True, max_length=1, null=True, choices=[(b'A', 'Army'), (b'F', 'Fleet'), (b'G', 'Garrison')])),
                ('confirmed', models.BooleanField(default=False)),
                ('destination', models.ForeignKey(blank=True, to='machiavelli.GameArea', null=True, on_delete=models.CASCADE)),
            ],
        ),
        migrations.CreateModel(
            name='Player',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('done', models.BooleanField(default=False)),
                ('eliminated', models.BooleanField(default=False)),
                ('excommunicated', models.PositiveIntegerField(null=True, blank=True)),
                ('assassinated', models.BooleanField(default=False)),
                ('defaulted', models.BooleanField(default=False)),
                ('surrendered', models.BooleanField(default=False)),
                ('ducats', models.PositiveIntegerField(default=0)),
                ('double_income', models.BooleanField(default=False)),
                ('may_excommunicate', models.BooleanField(default=False)),
                ('static_name', models.CharField(default=b'', max_length=20)),
                ('step', models.PositiveIntegerField(default=0)),
                ('has_sentenced', models.BooleanField(default=False)),
                ('is_excommunicated', models.BooleanField(default=False)),
                ('pope_excommunicated', models.BooleanField(default=False)),
                ('secret_key', models.CharField(default=b'', verbose_name='secret key', max_length=20, editable=False)),
                ('conqueror', models.ForeignKey(related_name='conquered', blank=True, to='machiavelli.Player', null=True, on_delete=models.CASCADE)),
                ('contender', models.ForeignKey(blank=True, to='condottieri_scenarios.Contender', null=True, on_delete=models.CASCADE)),
                ('country', models.ForeignKey(blank=True, to='condottieri_scenarios.Country', null=True, on_delete=models.CASCADE)),
                ('game', models.ForeignKey(to='machiavelli.Game', on_delete=models.CASCADE)),
            ],
        ),
        migrations.CreateModel(
            name='Rebellion',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('garrisoned', models.BooleanField(default=False)),
                ('repressed', models.BooleanField(default=False)),
                ('area', models.OneToOneField(to='machiavelli.GameArea', on_delete=models.CASCADE)),
                ('player', models.ForeignKey(to='machiavelli.Player', on_delete=models.CASCADE)),
            ],
        ),
        migrations.CreateModel(
            name='RetreatOrder',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('area', models.ForeignKey(blank=True, to='machiavelli.GameArea', null=True, on_delete=models.CASCADE)),
            ],
        ),
        migrations.CreateModel(
            name='Revolution',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('active', models.DateTimeField(null=True, blank=True)),
                ('overthrow', models.BooleanField(default=False)),
                ('voluntary', models.BooleanField(default=False)),
                ('country', models.ForeignKey(to='condottieri_scenarios.Country', on_delete=models.CASCADE)),
                ('game', models.ForeignKey(to='machiavelli.Game', on_delete=models.CASCADE)),
                ('government', models.ForeignKey(related_name='revolutions', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),
                ('opposition', models.ForeignKey(related_name='overthrows', blank=True, to=settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name': 'Revolution',
                'verbose_name_plural': 'Revolutions',
            },
        ),
        migrations.CreateModel(
            name='Score',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('points', models.IntegerField(default=0)),
                ('cities', models.PositiveIntegerField(default=0)),
                ('position', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('ignore_avg', models.BooleanField(default=False)),
                ('country', models.ForeignKey(to='condottieri_scenarios.Country', on_delete=models.CASCADE)),
                ('game', models.ForeignKey(to='machiavelli.Game', on_delete=models.CASCADE)),
            ],
            options={
                'ordering': ['-game', 'position'],
                'verbose_name': 'score',
                'verbose_name_plural': 'scores',
            },
        ),
        migrations.CreateModel(
            name='StrategicOrder',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('area', models.ForeignKey(to='machiavelli.GameArea', on_delete=models.CASCADE)),
            ],
        ),
        migrations.CreateModel(
            name='Team',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('game', models.ForeignKey(verbose_name='game', to='machiavelli.Game', on_delete=models.CASCADE)),
            ],
            options={
                'ordering': ['-game'],
                'verbose_name': 'team',
                'verbose_name_plural': 'teams',
            },
        ),
        migrations.CreateModel(
            name='TeamMessage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('text', models.TextField(verbose_name='text')),
                ('player', models.ForeignKey(verbose_name='player', to='machiavelli.Player', on_delete=models.CASCADE)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='TurnLog',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('year', models.PositiveIntegerField()),
                ('season', models.PositiveIntegerField(choices=[(1, 'Spring'), (2, 'Summer'), (3, 'Fall')])),
                ('phase', models.PositiveIntegerField(choices=[(0, 'Inactive game'), (1, 'Military adjustments'), (2, 'Order writing'), (3, 'Retreats'), (4, 'Strategic movement')])),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('log', models.TextField()),
                ('game', models.ForeignKey(to='machiavelli.Game', on_delete=models.CASCADE)),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='Unit',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('type', models.CharField(max_length=1, choices=[(b'A', 'Army'), (b'F', 'Fleet'), (b'G', 'Garrison')])),
                ('besieging', models.BooleanField(default=False)),
                ('must_retreat', models.CharField(default=b'', max_length=5, blank=True)),
                ('placed', models.BooleanField(default=True)),
                ('paid', models.BooleanField(default=True)),
                ('cost', models.PositiveIntegerField(default=3)),
                ('power', models.PositiveIntegerField(default=1)),
                ('loyalty', models.PositiveIntegerField(default=1)),
                ('area', models.ForeignKey(to='machiavelli.GameArea', on_delete=models.CASCADE)),
                ('player', models.ForeignKey(to='machiavelli.Player', on_delete=models.CASCADE)),
            ],
        ),
        migrations.CreateModel(
            name='Whisper',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('as_admin', models.BooleanField(default=False)),
                ('text', models.CharField(help_text='limit of 140 characters', max_length=140)),
                ('order', models.PositiveIntegerField(default=0, editable=False)),
                ('game', models.ForeignKey(to='machiavelli.Game', on_delete=models.CASCADE)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='strategicorder',
            name='unit',
            field=models.ForeignKey(to='machiavelli.Unit', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='score',
            name='team',
            field=models.ForeignKey(verbose_name='team', blank=True, to='machiavelli.Team', null=True, on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='score',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='retreatorder',
            name='unit',
            field=models.ForeignKey(to='machiavelli.Unit', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='player',
            name='team',
            field=models.ForeignKey(verbose_name='team', blank=True, to='machiavelli.Team', null=True, on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='player',
            name='user',
            field=models.ForeignKey(blank=True, to=settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='order',
            name='player',
            field=models.ForeignKey(to='machiavelli.Player', null=True, on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='order',
            name='subdestination',
            field=models.ForeignKey(related_name='affecting_orders', blank=True, to='machiavelli.GameArea', null=True, on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='order',
            name='subunit',
            field=models.ForeignKey(related_name='affecting_orders', blank=True, to='machiavelli.Unit', null=True, on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='order',
            name='unit',
            field=models.ForeignKey(to='machiavelli.Unit', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='loan',
            name='player',
            field=models.OneToOneField(to='machiavelli.Player', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='gamearea',
            name='home_of',
            field=models.ForeignKey(related_name='homes', blank=True, to='machiavelli.Player', null=True, on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='gamearea',
            name='player',
            field=models.ForeignKey(blank=True, to='machiavelli.Player', null=True, on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='expense',
            name='area',
            field=models.ForeignKey(blank=True, to='machiavelli.GameArea', null=True, on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='expense',
            name='player',
            field=models.ForeignKey(to='machiavelli.Player', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='expense',
            name='unit',
            field=models.ForeignKey(blank=True, to='machiavelli.Unit', null=True, on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='errorreport',
            name='game',
            field=models.ForeignKey(to='machiavelli.Game', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='errorreport',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='diplomat',
            name='area',
            field=models.ForeignKey(to='machiavelli.GameArea', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='diplomat',
            name='player',
            field=models.ForeignKey(to='machiavelli.Player', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='credit',
            name='player',
            field=models.ForeignKey(to='machiavelli.Player', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='configuration',
            name='game',
            field=models.OneToOneField(editable=False, to='machiavelli.Game', verbose_name='game', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='assassination',
            name='killer',
            field=models.ForeignKey(related_name='assassination_attempts', to='machiavelli.Player', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='assassination',
            name='target',
            field=models.ForeignKey(related_name='assassination_targets', to='machiavelli.Player', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='assassin',
            name='owner',
            field=models.ForeignKey(to='machiavelli.Player', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='assassin',
            name='target',
            field=models.ForeignKey(to='condottieri_scenarios.Country', on_delete=models.CASCADE),
        ),
        migrations.CreateModel(
            name='LiveGame',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('machiavelli.game',),
        ),
        migrations.AlterUniqueTogether(
            name='whisper',
            unique_together=set([('game', 'order')]),
        ),
        migrations.AlterUniqueTogether(
            name='revolution',
            unique_together=set([('game', 'government'), ('game', 'opposition')]),
        ),
        migrations.AlterUniqueTogether(
            name='order',
            unique_together=set([('unit', 'player')]),
        ),
        migrations.AlterUniqueTogether(
            name='journal',
            unique_together=set([('user', 'game')]),
        ),
        migrations.AlterUniqueTogether(
            name='invitation',
            unique_together=set([('game', 'user')]),
        ),
        migrations.AlterUniqueTogether(
            name='gameroute',
            unique_together=set([('game', 'trade_route')]),
        ),
        migrations.AlterUniqueTogether(
            name='diplomat',
            unique_together=set([('player', 'area')]),
        ),
    ]
