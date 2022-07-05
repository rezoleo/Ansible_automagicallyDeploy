#!/usr/bin/python3
"""
Created on Thu Oct  6 01:11:54 2016

@author: Augustin Lemesle, Gabriel Détraz, David Sinquin
"""

import logging
import subprocess
from os import path, makedirs

import requests
import unicodedata

from config import Config

CONFIG = Config()

class dhcp:
    """Gère le service DHCP (pour isc-dhcp-server)."""
    def __init__(self, session):
        self.session = session
        self.data = []
        self.liste_types = {}
        self.dhcp_config = {}
        self.errors = []

    def get_data(self):
        """Récupération des données."""
        logging.info("Récupération des données MAC-IP.")
        try:
            mac_ip_dns = self.session.post(CONFIG.get_rest_url('mac-ip-dns'))
            mac_ip_dns.raise_for_status()
            extension_list = self.session.post(CONFIG.get_rest_url('corresp'))
            extension_list.raise_for_status()
        except (requests.ConnectionError,
                requests.HTTPError,
                requests.Timeout) as err:
            logging.error("Erreur lors de la récupération des données MAC-IP.")
            self.errors.append(err)
        else:
            self.data = mac_ip_dns.json()
            self.liste_types = {ext['type'] for ext in extension_list.json()}
            logging.info("Récupération des données MAC-IP terminée.")

    def gen_dhcp_list(self):
        """Génération des leases DHCP."""
        logging.info("Génération de la configuration DHCP.")
        dhcp_configs = {}
        if not self.data:
            logging.warning("Liste IP-MAC reçue vide, annulation.")
            self.dhcp_config = None
            return
        for type_ in self.liste_types:
            dhcp_configs[type_] = []
            for data in self.data:
                if data['ipv4']['ip_type'] == type_:
                    dhcp_configs[type_].append(
                        "host {hostname} {{\n"
                        "    hardware ethernet {mac};\n"
                        "    fixed-address {ipv4};\n"
                        "}}".format(
                            hostname=data['domain'] + data['extension'],
                            ipv4=data['ipv4']['ipv4'],
                            mac=data['mac_address'],
                        ))
            self.dhcp_config[type_] = '\n\n'.join(dhcp_configs[type_])
        logging.info("Génération de la configuration DHCP terminée.")

    def write_leases(self):
        """Écriture des leases DHCP complets."""
        if self.dhcp_config is not None:
            logging.info("Écriture de la configuration DHCP.")
            if not path.exists('generated/') :
                makedirs('generated/')
            for type_ in self.liste_types:
                with open("generated/dhcp-%s.list" % (unicodedata.normalize('NFKD', type_).encode('ASCII', 'ignore').decode('ascii').replace(' ', '_')), "w+") as file:
                    file.write(self.dhcp_config[type_])
            logging.info("Écriture de la configuration DHCP terminée.")
        else:
            logging.info("Pas de configuration DHCP à écrire.")

    def check_syntax(self):
        """Vérifie la configuration du serveur DHCP."""
        logging.info("Vérification de la configuration DHCP.")
        try:
            subprocess.check_output(
                ['/usr/sbin/dhcpd', '-t', '-cf', '/etc/dhcp/dhcpd.conf'],
                stderr=subprocess.STDOUT)
            logging.info("Configuration DHCP valide.")
        except subprocess.CalledProcessError as err:
            logging.error(
                "Erreur lors de la vérification de la configuration DHCP.\n"
                "Code de retour: %s, Sortie:\n%s",
                err.returncode, err.output.decode())
            logging.error(err)
            self.errors.append(err)
            return False
        return True

    def reload_server(self):
        """Relance le serveur DHCP."""
        logging.info("Redémarrage de isc-dhcp-server.")
        try:
            subprocess.check_output(
                ['/bin/systemctl', 'restart', 'isc-dhcp-server'],
                stderr=subprocess.STDOUT)
            logging.info("Redémarrage de isc-dhcp-server terminé.")
        except subprocess.CalledProcessError as err:
            logging.critical(
                "Erreur lors du redémarrage de isc-dhcp-server.\n"
                "Code de retour: %s, Sortie:\n%s",
                err.returncode, err.output.decode())
            logging.error(err)
            self.errors.append(err)

    def complete_regen(self):
        """Gère le service DHCP et renvoie la liste des erreurs rencontrées."""
        self.get_data()
        self.gen_dhcp_list()
        self.write_leases()
        if self.check_syntax():
            self.reload_server()
        return self.errors

    @classmethod
    def dhcp(cls, session):
        """Gère le service DHCP et renvoie la liste des erreurs rencontrées."""
        return cls(session).complete_regen()
