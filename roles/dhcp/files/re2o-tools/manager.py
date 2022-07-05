#!/usr/bin/python3
"""
Created on Thu Oct  6 01:11:54 2017

@author: Augustin Lemesle, Gabriel Détraz
"""

import logging
import socket
import sys

import requests

from config import Config
from affichage import prettyDoin, Animation
from dhcp import dhcp
from dns import dns
from unifi_ap import unifi_ap
from mac_ip_list import mac_ip_list
from mailing import mailing
from connexion_manager import ConnectionManager


CONFIG = Config()

username = CONFIG['Default']['USERNAME']
password = CONFIG['Default']['PASSWORD']


class Services:
    def __init__(self, connection, anim=True):
        self.hostname = socket.gethostname().split('.')[0]
        self.services_to_regen = []
        self.anim = anim
        self.errors = []
        self.connection = connection

    def get_services_to_regen(self):
        if self.anim:
            prettyDoin("Services à régénérer", "...")
        try:
            to_regen = self.connection.post(CONFIG.get_rest_url('service_servers')).json()
            services = [service['service'] for service in to_regen if service['need_regen'] and service['server'] == self.hostname]
            self.services_to_regen = services
            if self.anim:
                prettyDoin("Services à régénérer", "Ok")
                print("Liste des services à régénérer : %s" % services)
        except Exception as e:
            if self.anim:
                prettyDoin("Services à régénérer", "Error")
            self.errors.append(e)

    def add_service_to_regen(self, service):
        if not service in self.services_to_regen:
            self.services_to_regen.append(service)

    def post_regen_notify(self, service):
        if self.anim:
            prettyDoin("Notification pour %s" % service, "...")
        try:
            regen_data = {'service': service, 'server': self.hostname}
            self.connection.post(CONFIG.get_rest_url('regen-achieved'), data=regen_data)
            if self.anim:
                prettyDoin("Notification pour %s" % service, "Ok")
        except Exception as e:
            if self.anim:
                prettyDoin("Notification pour %s" % service, "Error")

    def regen_services(self):
        for service in self.services_to_regen:
            if self.anim:
                prettyDoin("Régénération du service %s" % service, "...")
            service_instance = getattr(self, "service_" + service, None)
            if service_instance:
                errors = service_instance().errors
            else:
                errors = ["Service %s introuvable" % service]
            if errors:
                self.errors.extend(errors)
                prettyDoin("Régénération du service %s" % service, "Error")
            else:
                prettyDoin("Régénération du service %s" % service, "Ok")
                self.post_regen_notify(service)

    def service_dhcp(self):
        return ErrorContainer(dhcp.dhcp(self.connection))

    def service_mac_ip_list(self):
        return ErrorContainer(mac_ip_list.mac_ip_list(self.connection))

    def service_dns(self):
        class_dns = dns(self.connection, anim=self.anim)
        class_dns.dns()
        return class_dns

    def service_mailing(self):
        return ErrorContainer(mailing.mailing(self.connection))

    def service_unifi_ap(self):
        return ErrorContainer(unifi_ap.unifi_ap(self.connection))

class ErrorContainer(object):
    """Dummy class to store errors in an "errors" attribute."""
    def __init__(self, errors):
        self.errors = errors


if __name__ == '__main__':
    if "--help" in sys.argv or "-h" in sys.argv:
        print(
            "Régénération des services\n"
            "Usage : Sans arguments, récupère la liste des services à régénérer\n"
            "Ajouter les services dont on veut forcer le redémarage en plus"
            "Exemple : ./manage.py dhcp dns force la régénération de dhcp et dns"
            )
        sys.exit(0)
    with ConnectionManager() as connection:
        service = Services(connection)
        service.get_services_to_regen()
        for extra_service in sys.argv[1:]:
            service.add_service_to_regen(extra_service)
        service.regen_services()
        for err in service.errors:
            logging.error(err)
