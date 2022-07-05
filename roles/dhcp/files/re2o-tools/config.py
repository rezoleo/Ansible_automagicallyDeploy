#!/usr/bin/python3

"""Wrapper around configparser to manage config."""

import configparser

class Config(configparser.ConfigParser):
    """Manage project configuration."""
    
    _CONFIG_FILES = [
        #'/usr/local/etc/re2o/config.ini',
        '/etc/re2o/config.ini',
        './config.ini',
    ]

    def __init__(self):
        super().__init__()
        self.parsed_files = self.read(self._CONFIG_FILES)

    def getcfg(self, rule):
        return self['RuleSet'][rule]

    def get_url(self, url):
        return self['Default']['URL'] + url +'/'

    def get_url_api(self, app, url):
        return self['Default']['URL'] + 'api/' + app + '/' + url + '/'

    def get_rest_url(self, url):
        return self['Default']['URL'] + 'machines/rest/' + url + '/'

    def get_rest_users_url(self, url):
        return self['Default']['URL'] + 'users/rest/' + url + '/'

    def get_dns_server(self):
        return self['Dns']['SERVER']
