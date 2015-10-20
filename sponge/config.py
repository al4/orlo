from __future__ import print_function
import ConfigParser
__author__ = 'alforbes'

config = ConfigParser.ConfigParser()

config.add_section('main')
config.set('main', 'propagate_exceptions', 'true')
config.set('main', 'time_format', '%Y-%m-%d %H:%M:%S')
config.set('main', 'time_zone', 'UTC')

config.add_section('db')
config.set('db', 'uri', 'sqlite://')

config.add_section('logging')
config.set('logging', 'debug', 'true')
config.set('logging', 'file', 'disabled')

config.read('/etc/sponge.ini')
