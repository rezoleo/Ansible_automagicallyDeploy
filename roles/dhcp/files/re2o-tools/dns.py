#!/usr/bin/python3
"""
Created on Thu Oct  6 01:17:34 2016

@author: Augustin Lemesle, Gabriel Detraz, Simon Brélivet
"""
import subprocess
import sys
import textwrap
import netaddr
from os import path, makedirs

from datetime import datetime

import traceback
import requests

from affichage import prettyDoin, Animation
from config import Config

CONFIG = Config()


class dns:
    def __init__(self, session, anim=True):
        self.anim = anim
        self.data = None
        self.extension_list = None
        self.liste_extensions = None
        self.correspondings = None
        self.zones_list = None
        self.mx_list = None
        self.ns_list = None
        self.txt_list = None
        self.srv_list = None
        self.alias = None
        self.strings = None
        self.strings_reverse = {}
        self.errors = []
        self.set_serial()
        self.session = session
        self.server = CONFIG.get_dns_server()

    def set_serial(self):
        self.serial, hour, minute = datetime.now().strftime("%Y%m%d %H %M").split()
        self.serial += str(4*int(hour)+(int(minute) // 15))
        return

    def get_data(self):
        if self.anim:
            prettyDoin("Récupération des données DNS", "...")
        try:
            self.data = self.session.post(CONFIG.get_rest_url(
                'mac-ip-dns')).json()
            self.extension_list = self.session.post(CONFIG.get_rest_url(
                'corresp')).json()
            self.zones_list = self.session.post(CONFIG.get_rest_url(
                'zones')).json()
            self.mx_list = self.session.post(CONFIG.get_rest_url(
                'mx')).json()
            self.ns_list = self.session.post(CONFIG.get_rest_url(
                'ns')).json()
            self.txt_list = self.session.post(CONFIG.get_rest_url(
                'txt')).json()
            self.srv_list = self.session.post(CONFIG.get_rest_url(
                'srv')).json()
            self.alias = self.session.post(CONFIG.get_rest_url(
                'alias')).json()
            if self.anim:
                prettyDoin("Récupération des données DNS", "Ok")
        except requests.exceptions.RequestException as e:
            if self.anim:
                prettyDoin("Récupération des données DNS", "Error")
            self.errors.append(e)

    def sort_and_init(self):
        """on sort un set des extensions"""
        self.liste_extensions = set([i['extension']
                                     for i in self.extension_list])
        self.strings = {extension: "" for extension in self.liste_extensions}
        self.range_limits = {i['type']: {'start': i['domaine_ip_start'],
                                         'stop': i['domaine_ip_stop']} for i in self.extension_list}

    def gen_all_direct_zones(self):
        if self.anim:
            a = Animation(
                texte="Generation des resolutions directes",
                nb_cycles=len(self.liste_extensions),
                couleur=True,
                kikoo=True
            )
        for extension in self.liste_extensions:
            self.gen_direct_zone(extension)
            if self.anim:
                a.new_step()
        if self.anim:
            a.end()

    def gen_direct_zone(self, extension):
        self.write_direct_header(extension)
        self.set_space(extension)
        self.write_a_origin(extension)
        self.set_space(extension)
        self.write_ns_origin(extension)
        self.set_space(extension)
        self.write_mx(extension)
        self.set_space(extension)
        self.write_txt(extension)
        self.set_space(extension)
        self.write_srv(extension)
        self.set_space(extension)
        self.write_a_records(extension)
        self.set_space(extension)
        self.write_alias_records(extension)

    def set_space(self, extension):
        self.strings[extension] += "\n"

    def write_direct_header(self, extension):
        # On génère les résolutions directes
        # SOA : http://www.zytrax.com/books/dns/ch8/soa.html
        # refresh: Intervall between slave updates when they do not receive notices.
        # retry: Intervall between slave updates retries in case of failure to update.
        # expiry: Slaves serve zone after contacting master for that duration.
        # minimum: Caches must not stroe NXDOMAIN for more than this duration.
        for zone in self.zones_list:
            if zone['name'] == extension:
                self.strings[extension] = (
                    '$TTL 2D\n'
                    '@ IN SOA {main_name_server} {mail} (\n'
                    '    {serial}; serial, todays date + todays serial\n'
                    '{param}\n'
                    ')\n'
                ).format(
                    main_name_server='ns'+extension+'.',
                    mail=zone['soa']['mail'],
                    serial=str(self.serial).ljust(12),
                    param=zone['soa']['param']
                )
                return

    def write_a_origin(self, extension):
        # Ecriture de l'origin A
        for zone in self.zones_list:
            if zone['name'] == extension:
                self.strings[extension] += zone['zone_entry'] + "\n"
        return

    def write_ns_origin(self, extension):
        # Ecriture des NS de l'origin
        for domain in self.ns_list:
            if domain['zone'] == extension:
                self.strings[extension] += domain['ns_entry'] + ".\n"
        return

    def write_txt(self, extension):
        for domain in self.txt_list:
            if domain['zone'] == extension:
                self.strings[extension] += domain['txt_entry'] + "\n"
        return

    def write_srv(self, extension):
        for domain in self.srv_list:
            if domain['extension'] == extension:
                self.strings[extension] += domain['srv_entry'] + "\n"
        return

    def write_mx(self, extension):
        # generation des mx
        for mx in self.mx_list:
            if mx['zone'] == extension:
                self.strings[extension] += mx['mx_entry'] + ".\n"
        return

    def write_a_records(self, extension):
        """Génération des dns directs 'IN A'"""
        for a_record in self.data:
            if a_record['extension'] == extension:
                self.strings[extension] += \
                    a_record['domain'].ljust(
                        15) + " IN  A       " + a_record['ipv4']['ipv4'] + "\n"
                if a_record['ipv6']:
                    for ipv6 in a_record['ipv6']:
                        self.strings[extension] += \
                            a_record['domain'].ljust(
                                15) + " IN  AAAA    " + ipv6['ipv6'] + "\n"
        return

    def write_alias_records(self, extension):
        """Génération des dns directs 'IN CNAME'"""
        for alias in self.alias:
            if extension == alias['extension']:
                self.strings[extension] += alias['cname_entry'] + "\n"
        return

    def get_network(self, domain_ip_start, domain_ip_stop):
        a = domain_ip_start
        b = domain_ip_stop

        if a == b:
            return netaddr.IPNetwork(a+"/32")

        a = '.'.join(a.split('.')[:-1])
        b = '.'.join(b.split('.')[:-1])
        if a == b:
            return netaddr.IPNetwork(a+".0/24")

        a = '.'.join(a.split('.')[:-1])
        b = '.'.join(b.split('.')[:-1])
        if a == b:
            return netaddr.IPNetwork(a+".0.0/16")

        a = '.'.join(a.split('.')[:-1])
        b = '.'.join(b.split('.')[:-1])
        if a == b:
            return netaddr.IPNetwork(a+".0.0.0/8")

        return netaddr.IPNetwork("0.0.0.0/0")

    def get_interlap(self, subnet1, subnet2):
        if subnet1 == subnet2 or subnet1 in subnet2:
            return 0
        if subnet2 in subnet1:
            return 1

        return -1

    def get_correspondings(self):
        correspondings = []
        for extension in self.extension_list:

            network_to_add = self.get_network(
                extension['domaine_ip_start'], extension['domaine_ip_stop'])

            new_corresp = {'network': network_to_add, 'ip_types': [extension]}

            for k in range(len(correspondings)-1, -1, -1):
                interlap = self.get_interlap(
                    correspondings[k]['network'], network_to_add)

                if interlap == 0:
                    new_corresp['ip_types'] += correspondings.pop(k)[
                        'ip_types']

                elif interlap == 1:
                    new_corresp['network'] = correspondings[k]['network']
                    new_corresp['ip_types'] += correspondings.pop(k)[
                        'ip_types']

            correspondings.append(new_corresp)

        return correspondings

    def gen_all_reverse_zones(self):
        if self.anim:
            a = Animation(
                texte="Generation des resolutions reverses",
                nb_cycles=len(self.extension_list),
                couleur=True,
                kikoo=True
            )
        self.correspondings = self.get_correspondings()
        for corresp in self.correspondings:
            self.gen_reverse_zone(corresp)
            if self.anim:
                a.new_step()
        if self.anim:
            a.end()

    def reverse_prefix(self, corresp):
        """ Génère la suite de chiffres indexant la zone reverse"""
        if corresp['network'].prefixlen == 32:
            return '.'.join(
                [str(i) for i in corresp['network'].network.words]
            )
        if corresp['network'].prefixlen >= 24:
            return '.'.join(
                [str(i) for i in corresp['network'].network.words[:-1][::-1]]
            )
        elif corresp['network'].prefixlen >= 16:
            return '.'.join(
                [str(i) for i in corresp['network'].network.words[:-2][::-1]]
            )
        elif corresp['network'].prefixlen >= 8:
            return '.'.join(
                [str(i) for i in corresp['network'].network.words[:-3][::-1]]
            )
        else:
            return '.'.join(
                [str(i) for i in corresp['network'].network.words[:-3][::-1]]
            )

    def gen_reverse_zone(self, corresp):
        self.write_reverse_header(corresp)
        self.write_reverse_records(corresp)

    def write_reverse_header(self, corresp):
        # On génère les résolutions inverses
        network = '.'.join([str(i) for i in corresp['network'].network.words])
        extension = corresp['ip_types'][0]['extension']
        for zone in self.zones_list:
            if zone['name'] == extension:
                self.strings_reverse[network] = (
                    '$TTL 2D\n'
                    '@ IN SOA {main_name_server} {mail} (\n'
                    '    {serial}; serial, todays date + todays serial\n'
                    '{param}\n'
                    ')\n'
                    '\n'
                    '@       IN  NS      {main_name_server}\n'
                    '\n'
                ).format(
                    main_name_server="ns"+extension+".",
                    mail=zone['soa']['mail'],
                    serial=str(self.serial).ljust(12),
                    param=zone['soa']['param']
                )

    def write_reverse_records(self, corresp):
        for d in self.data:

            is_correct_type = False
            for ip_type in corresp['ip_types']:
                if d['ipv4']['ip_type'] == ip_type['type']:
                    is_correct_type = True
                    break
            if not(is_correct_type):
                continue

            if corresp['network'].prefixlen == 32:
                reverse_ip = ""
            elif corresp['network'].prefixlen >= 24:
                reverse_ip = '.'.join(
                    [str(i) for i in d['ipv4']['ipv4'].split('.')[::-1]][:1]
                )
            elif corresp['network'].prefixlen >= 16:
                reverse_ip = '.'.join(
                    [str(i) for i in d['ipv4']['ipv4'].split('.')[::-1]][:2]
                )
            elif corresp['network'].prefixlen >= 8:
                reverse_ip = '.'.join(
                    [str(i) for i in d['ipv4']['ipv4'].split('.')[::-1]][:3]
                )
            else:
                reverse_ip = '.'.join(
                    [str(i) for i in d['ipv4']['ipv4'].split('.')[::-1]]
                )
            self.strings_reverse[
                '.'.join([str(i) for i in corresp['network'].network.words])
            ] += \
                reverse_ip.ljust(7) + " IN  PTR     " + d['domain'] + \
                d['extension'] + ".\n"

    def write_zones(self):
        """ Ecriture des lease files"""
        if self.anim:
            prettyDoin("Ecriture des zones", "...")
        try:
            if not path.exists('generated/'):
                makedirs('generated/')
            for extension in self.strings.keys():
                with open("generated/db%s" % extension, "w+") as file:
                    file.write(self.strings[extension])
                    file.close()
            for extension in self.strings_reverse.keys():
                with open("generated/db_%s" % extension, "w+") as file:
                    file.write(self.strings_reverse[extension])
                    file.close()
        except OSError as e:
            if self.anim:
                prettyDoin("Ecriture des zones", "Error")
            self.errors.append(e)

    def check_zones_direct(self):
        """Vérification des zones avant de relancer bind"""
        if self.anim:
            prettyDoin("Vérification de la configuration DNS directe", "...")
        for extension in self.strings.keys():
            try:
                # direct:
                if self.server == "knot":
                    result = subprocess.check_output(
                        ["kzonecheck", 'generated/db%s' % extension]
                    )
                else:
                    result = subprocess.check_output(
                        ["named-checkzone", extension[1:],
                            'generated/db%s' % extension]
                    )
                if self.anim:
                    prettyDoin(
                        "Vérification de la configuration DNS %s" % extension[1:], "Ok")
            except subprocess.CalledProcessError as e:
                self.errors.append(e)
                if self.anim:
                    prettyDoin(
                        "Vérification de la configuration DNS %s" % extension[1:], "Error")

    def check_zones_reverse(self):
        if self.anim:
            prettyDoin("Vérification de la configuration DNS reverse", "...")
        for corresp in self.correspondings:
            try:
                if self.server == "knot":
                    result = subprocess.check_output([
                        'kzonecheck',
                        "generated/db_%s" % '.'.join([str(i)
                                                      for i in corresp['network'].network.words]),
                    ])
                else:
                    result = subprocess.check_output([
                        'named-checkzone',
                        "%s.in-addr.arpa" % self.reverse_prefix(corresp),
                        "generated/db_%s" % '.'.join([str(i)
                                                      for i in corresp['network'].network.words]),
                    ])
                if self.anim:
                    prettyDoin(
                        "Vérification de la configuration DNS reverse %s.in-addr.arpa" %
                        self.reverse_prefix(corresp), "Ok")
            except subprocess.CalledProcessError as e:
                self.errors.append(e)
                if self.anim:
                    prettyDoin(
                        "Vérification de la configuration DNS reverse %s.in-addr.arpa" %
                        self.reverse_prefix(corresp), "Error")

    def reload_server(self):
        # Rechargement du serveur
        if self.errors:
            # Pas de rechargement
            return
        if self.anim:
            prettyDoin("Rechargement %s" % self.server, "...")
        try:
            subprocess.check_output(['systemctl', 'reload', self.server])
            if self.anim:
                prettyDoin("Rechargement %s" % self.server, "Ok")
        except subprocess.CalledProcessError as e:
            if self.anim:
                prettyDoin("Rechargement %s" % self.server, "Error")
            self.errors.append(e)

    def reconfigure_dns(self):
        """ Reconfiguration totale de bind"""
        self.get_data()
        self.sort_and_init()
        self.gen_all_direct_zones()
        self.gen_all_reverse_zones()
        self.write_zones()
        self.check_zones_direct()
        self.check_zones_reverse()
        self.reload_server()

    def dns(self):
        self.reconfigure_dns()
