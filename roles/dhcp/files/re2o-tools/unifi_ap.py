#!/usr/bin/python3
"""
Created on Sun Sep 10 00:00:00 2017

@author: Gabriel Detraz
"""

import logging
import subprocess
import importlib
import requests
from pymongo import MongoClient


from config import Config

CONFIG = Config()

class unifi_ap:
    """Génère les noms dans le """
    def __init__(self, session):
        self.session = session
        self.data = []
        self.errors = []
        self.connexion = None

    def get_data(self):
        """Récupération des données."""
        logging.info("Récupération des bornes.")
        try:
            ap_list = self.session.get(CONFIG.get_url_api('unifi','ap_names'))
            ap_list.raise_for_status()
        except (requests.ConnectionError,
                requests.HTTPError,
                requests.Timeout) as err:
            logging.error("Erreur lors de la récupération des bornes.")
            self.errors.append(err)
        else:
            self.data = ap_list.json() 
            logging.info("Récupération des bornes terminée.")

    def connect_mongo(self):
        ## Connexion mongodb    
        try:
            client = MongoClient("mongodb://localhost:27117")
            db = client.ace
            device = db['device']
            self.connexion = device
        except:
            self.errors.append("Mongo connexion error")

    def write_names(self):
        for ap in self.data['data']:
            self.connexion.find_one_and_update({'ip': str(ap['ipv4']['ipv4'])}, {'$set': {'name': str(ap['domain']) + str(ap['extension'])}})
        return

    def complete_regen(self):
        """Gère le service de mailing et renvoie la liste des erreurs rencontrées."""
        self.get_data()
        self.connect_mongo()
        if not self.errors:
            self.write_names()
        return self.errors

    @classmethod
    def unifi_ap(cls, session):
        """Gère le service de nom et renvoie la liste des erreurs rencontrées."""
        return cls(session).complete_regen()
