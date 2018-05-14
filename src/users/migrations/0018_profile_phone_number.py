# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2018-02-01 04:20
from __future__ import unicode_literals

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0017_merge_20180112_2237'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='phone_number',
            field=models.CharField(blank=True, max_length=13, validators=[django.core.validators.RegexValidator(message='Phone number must be entered in the format: (012)345-6789', regex='^\\(([0-9]{3})\\)([0-9]{3})[-]([0-9]{4})$')]),
        ),
    ]