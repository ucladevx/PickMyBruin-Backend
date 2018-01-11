# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2017-12-06 17:28
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0010_auto_20171206_0608'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='year',
            field=models.CharField(choices=[('1', '1st'), ('2', '2nd'), ('3', '3rd'), ('4', '4th')], default='1', max_length=2),
        ),
    ]