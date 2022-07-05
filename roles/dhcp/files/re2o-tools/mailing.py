#!/usr/bin/python3
"""
Created on Sun Sep 10 00:00:00 2017

@author: Maël Kervella
"""

import logging
import subprocess
from os import path, makedirs, getcwd
import importlib
import requests

from config import Config

CONFIG = Config()

class mailing:
    """Gère la génération d'un fichier de mailing des adhérents."""
    def __init__(self, session):
        self.session = session
        self.ml_club = {}
        self.ml_club_admin = {}
        self.ml_std = {}
        self.errors = []

    def get_ml_std_list(self):
        """Récupération de la liste des mailings standards."""
        step_name="Récup liste des ml std."
        logging.info("Début de '%s'." % step_name)
        try:
            mls = self.session.get(CONFIG.get_rest_users_url('ml/std'))
            mls.raise_for_status()
            mls_json = mls.json()
        except (requests.ConnectionError,
                requests.HTTPError,
                requests.Timeout) as err:
            logging.error("Erreur lors de '%s' : Problème de requête" % step_name)
            self.errors.append(err)
        except ValueError as err:
            logging.error("Erreur lors de '%s' : La réponse reçue n'est pas au format JSON" % step_name)
            self.errors.append(err)
        else:
            if CONFIG['Mailing'].getboolean('USE_WHITELIST', fallback=False):
                whitelist = CONFIG['Mailing']['WHITELIST'].lower().split(',')
                self.ml_std = {
                    ml['name']:[]
                        for ml in mls_json
                        if ml['name'].lower in whitelist
                }
            else :
                blacklist = CONFIG['Mailing']['BLACKLIST'].lower().split(',')
                self.ml_std = {
                    ml['name']:[]
                        for ml in mls_json
                        if ml['name'].lower not in blacklist
                }
            logging.info("Fin de '%s'." % step_name)

    def get_ml_club_list(self):
        """Récupération de la liste des mailings de club."""
        step_name="Récup liste des ml de club."
        logging.info("Début de '%s'." % step_name)
        try:
            mls = self.session.get(CONFIG.get_rest_users_url('ml/club'))
            mls.raise_for_status()
            mls_json = mls.json()
        except (requests.ConnectionError,
                requests.HTTPError,
                requests.Timeout) as err:
            logging.error("Erreur lors de '%s' : Problème de requête." % step_name)
            self.errors.append(err)
        except ValueError as err:
            logging.error("Erreur lors de '%s' : La réponse reçue n'est pas au format JSON" % step_name)
            self.errors.append(err)
        else:
            if CONFIG['Mailing'].getboolean('USE_WHITELIST', fallback=False):
                whitelist = CONFIG['Mailing']['WHITELIST'].lower().split(',')
                self.ml_club = {
                    ml['name']:[]
                        for ml in mls_json
                        if ml['name'].lower() in whitelist
                }
                self.ml_club_admin = {
                    ml['name']:[]
                        for ml in mls_json
                        if ml['name'].lower() in whitelist
                }
            else :
                blacklist = CONFIG['Mailing']['BLACKLIST'].lower().split(',')
                self.ml_club = {
                    ml['name']:[]
                        for ml in mls_json
                        if ml['name'].lower() not in blacklist
                }
                self.ml_club_admin = {
                    ml['name']:[]
                        for ml in mls_json
                        if ml['name'].lower() not in blacklist
                }
            logging.info("Fin de '%s'." % step_name)

    def get_ml_std_members(self, ml_name):
        """Récupération de la liste des membres d'une mailing de club."""
        step_name="Récup des membres de la ml std %s." % ml_name
        logging.info("Début de '%s'." % step_name)
        try:
            members = self.session.get(CONFIG.get_rest_users_url('ml/std/member/%s' % ml_name))
            members.raise_for_status()
            members_json = members.json()
        except (requests.ConnectionError,
                requests.HTTPError,
                requests.Timeout) as err:
            logging.error("Erreur lors de '%s' : Problème de requête" % step_name)
            self.errors.append(err)
        except ValueError as err:
            logging.error("Erreur lors de '%s' : La réponse reçue n'est pas au format JSON" % step_name)
            self.errors.append(err)
        else:
            self.ml_std[ml_name] = [member['email'] for member in members_json]
            logging.info("Fin de '%s'." % step_name)

    def get_ml_club_members(self, ml_name):
        """Récupération de la liste des membres d'une mailing de club."""
        step_name="Récup des membres du club %s." % ml_name
        logging.info("Début de '%s'." % step_name)
        try:
            members = self.session.get(CONFIG.get_rest_users_url('ml/club/member/%s' % ml_name))
            members.raise_for_status()
            members_json = members.json()
        except (requests.ConnectionError,
                requests.HTTPError,
                requests.Timeout) as err:
            logging.error("Erreur lors de '%s' : Problème de requête" % step_name)
            self.errors.append(err)
        except ValueError as err:
            logging.error("Erreur lors de '%s' : La réponse reçue n'est pas au format JSON" % step_name)
            self.errors.append(err)
        else:
            self.ml_club[ml_name] = [member['email'] for member in members_json]
            logging.info("Fin de '%s'." % step_name)

    def get_ml_club_admins(self, ml_name):
        """Récupération de la liste des admins d'une mailing de club."""
        step_name="Récup des admins du club %s." % ml_name
        logging.info("Début de '%s'." % step_name)
        try:
            members = self.session.get(CONFIG.get_rest_users_url('ml/club/admin/%s' % ml_name))
            members.raise_for_status()
            members_json = members.json()
        except (requests.ConnectionError,
                requests.HTTPError,
                requests.Timeout) as err:
            logging.error("Erreur lors de '%s' : Problème de requête" % step_name)
            self.errors.append(err)
        except ValueError as err:
            logging.error("Erreur lors de '%s' : La réponse reçue n'est pas au format JSON" % step_name)
            self.errors.append(err)
        else:
            self.ml_club_admin[ml_name] = [member['email'] for member in members_json]
            logging.info("Fin de '%s'." % step_name)

    def get_all_members(self):
        """Récupèration de la liste des membres pour toutes les mailings."""
        for ml_name in self.ml_std.keys():
            self.get_ml_std_members(ml_name)
        for ml_name in self.ml_club.keys():
            self.get_ml_club_members(ml_name)
        for ml_name in self.ml_club_admin.keys():
            self.get_ml_club_admins(ml_name)

    def write_data(self):
        """Écriture du fichiers de mails adhérents."""
        logging.info("Écriture des mails.")
        if not path.exists('generated/') :
            makedirs('generated/')
        for ml_name in self.ml_std.keys():
            with open("generated/ml_std_%s.list" % ml_name, "w+") as f:
                f.write('\n'.join(self.ml_std[ml_name]))
                f.write('\n')
        for ml_name in self.ml_club.keys():
            with open("generated/ml_club_%s.list" % ml_name, "w+") as f:
                f.write('\n'.join(self.ml_club[ml_name]))
                f.write('\n')
        for ml_name in self.ml_club_admin.keys():
            with open("generated/ml_club_admin_%s.list" % ml_name, "w+") as f:
                f.write('\n'.join(self.ml_club_admin[ml_name]))
                f.write('\n')
        logging.info("Écriture des mails terminée.")
        
    def check_syntax(self):
        """Vérifie la configuration du service de mailing."""
        # TODO : Faire un truc en fonction de la méthode de mailing utilisée
        return True

    def reload_service(self):
        """Relance le service de mailing."""
        ml_manager_class = CONFIG['Mailing']['MAILING_CLASS']

        try :
            ml_manager = importlib.import_module( ml_manager_class )
        except ImportError as err:
            logging.error('Le module '+ml_class+' pour manager les mailing n\'existe pas.')
            self.errors.append(err)
        else :
            for ml_name in self.ml_std.keys():
                ml_manager.apply_conf(
                    ml_name,
                    path.join( getcwd(), 'generated', 'ml_std_%s.list' % ml_name)
                )
            for ml_name in self.ml_club.keys():
                ml_manager.apply_conf(
                    ml_name,
                    path.join( getcwd(), 'generated', 'ml_club_%s.list' % ml_name)
                )
            for ml_name in self.ml_club_admin.keys():
                ml_manager.apply_conf(
                    ml_name+'-admin',
                    path.join( getcwd(), 'generated', 'ml_club_admin_%s.list' % ml_name)
                )

    def complete_regen(self):
        """Gère le service de mailing et renvoie la liste des erreurs rencontrées."""
        self.get_ml_std_list()
        self.get_ml_club_list()
        self.get_all_members()
        self.write_data()
        if self.check_syntax():
            self.reload_service()
        return self.errors

    @classmethod
    def mailing(cls, session):
        """Gère le service de mailing et renvoie la liste des erreurs rencontrées."""
        return cls(session).complete_regen()
