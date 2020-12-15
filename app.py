#!/usr/bin/env python3

from aws_cdk import core

from maxmind_geolite2.maxmind_geolite2_stack import MaxmindGeolite2Stack


app = core.App()
MaxmindGeolite2Stack(app, 'maxmind-geolite2')
core.Tags.of(app).add('maxmind-geolite2', 'maxmind-geolite2')

app.synth()
