#!/usr/bin/python3
"""
Created on Thu Oct  6 01:11:54 2016

@author: Augustin Lemesle, Gabriel Détraz
"""

import requests
import sys
import subprocess
import logging

from config import Config

CONFIG = Config()




class mac_ip_list:
    """ Génère un bulk fichier listing mac-ip autorisées """
    def __init__(self, session):
        self.session = session
        self.list_mac_ip = []
        self.data = []
        self.errors = []

    def get_data(self):
        """Recupération des données over https"""
        logging.info("Récupération des données mac-ip.")
        try:
            mac_ip_dns = self.session.post(CONFIG.get_rest_url('mac-ip-dns'))
            mac_ip_dns.raise_for_status()
        except (requests.ConnectionError,
                requests.HTTPError,
                requests.Timeout) as err:
            logging.error("Erreur lors de la récupération des données MAC-IP.")
            self.errors.append(err)
        else:
            self.data = mac_ip_dns.json()
            logging.info("Récupération des données MAC-IP terminée.")

    def format_data(self):
        """ Génération du fichier mac-ip"""
        logging.info("Génération du fichier mac-ip")
        if not self.data:
            logging.warning("Liste IP-MAC reçue vide, annulation.")
            self.list_mac_ip = None
            return
        for data in self.data:
            if(data['ipv4']['ip_type']):
                self.list_mac_ip.append(data['ipv4']['ipv4'] + " "  + data['mac_address'])
        self.list_mac_ip = '\n'.join(self.list_mac_ip)
        self.list_mac_ip += '\n'
        logging.info("Génération de la liste mac_ip terminée")

    def write_list(self):
        """Ecriture du fichier mac-ip"""
        if self.list_mac_ip is not None:
            logging.info("Écriture de la configuration ")
            with open("generated/mac-ip.list", "w") as file:
                file.write(self.list_mac_ip)
            logging.info("Ecriture")
        else:
            logging.info("Config invalide")

    def complete_regen(self):
        """ Regen complet du fichier mac_ip_list"""
        self.get_data()
        self.format_data()
        self.write_list()
        subprocess.check_output(
                ['/usr/local/firewall/refreshmac.sh'],
                stderr=subprocess.STDOUT)

    @classmethod
    def mac_ip_list(cls, session):
        """Regen complet du fichier mac-ip"""
        return cls(session).complete_regen()
