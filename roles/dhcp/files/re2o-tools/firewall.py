#!/usr/bin/python3

"""
Module for IP-MAC set management.

Uses ipset to get active ruleset.

BUGS : requires no spaces in set names (ipset do not manage this properly).
"""

# À voir:
#    https://unix.stackexchange.com/questions/126009/cause-a-script#126146
#

# Dependencies: python3-netaddr, python3-requests, ipset, sudo
#
# Configuration:
#  - create a file in /etc/sudoers.d/ with:
#    "user...   ALL = (root) NOPASSWD: /sbin/ipset"
#  - create a set with :
#    "[sudo] ipset create SET_NAME bitmap:ip,mac range IP_NETWORK/MASK"
#    where:
#     - SET_NAME is CONFIG['Firewall']['DEFAULT_NAME']
#     - IP_NETWORK/MASK is probably 10.69.0.0/16

# import ipaddress
import json
import subprocess

import requests
import netaddr # https://pythonhosted.org/netaddr/index.html

from config import Config

CONFIG = Config()


class CustomMACFormat(netaddr.mac_unix):
    """Class to print MAC in standard dash-separated format."""
    # Forced to create a class just for that => no need for pylint warning...
    # pylint: disable=too-few-public-methods
    word_fmt = '%.2X'

class RuleSet(object):
    '''
    Manage a set of IP-MAC rules.

    Rules are couples ('ip', 'mac'):
      - 'ip' is of type netaddr.IPAddress ;
      - 'mac' is of type netaddr.EUI.
    A set have a name, 2 lists of rules (active_rules with kernel loaded rules,
    target_rules with rules to apply), a range, and a type (ipset type).
    '''

    DEFAULT_NAME = CONFIG['Firewall']['DEFAULT_NAME']
    DEFAULT_TYPE = CONFIG['Firewall']['DEFAULT_TYPE']
    DATA_SOURCE_URL = CONFIG['Source']['DATA_SOURCE_URL']
    LOGIN_URL = CONFIG['Source']['DATA_SOURCE_URL_LOGIN']
    HTTP_AUTHENTICATION_PARAMS = {
        'username': CONFIG['Default']['USERNAME'],
        'password': CONFIG['Default']['PASSWORD'],
    }

    def __init__(self, empty=False, name=DEFAULT_NAME, type_=DEFAULT_TYPE):
        self.name = name
        self.active_rules = []
        self.target_rules = []
        self.range_ = None, None
        self.type_ = type_
        if not empty:
            self.get_new_rules()
            self.populate_rules_from_kernel()

    def populate_rules_from_kernel(self):
        '''Store currently applied rules from kernel in active_rules.'''
        plaintext_rules = self.get_active_rules(self.name)
        self.parse_kernel_rule_set(plaintext_rules)

    @staticmethod
    def get_active_rules(set_name):
        '''Get current rule set from kernel and return plaintext data.'''
        ipset_call = subprocess.Popen(
            [
                "/usr/bin/sudo", "/sbin/ipset", "-output", "save",
                "list", set_name
            ],
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True)
        stdout, stderr = ipset_call.communicate()
        if ipset_call.returncode != 0:
            if ipset_call.returncode == 1 and \
                    "The set with the given name does not exist" in stderr:
                raise OSError(
                    "ipset \"{}\" do not seem to exist, return code {}\n{}"
                    .format(set_name, ipset_call.returncode, stderr))
            raise OSError(
                "Unable to get current ipset, return code: {}\n{}"
                .format(ipset_call.returncode, stderr))
        return stdout.strip()

    def parse_kernel_rule_set(self, plaintext_rules):
        """Parse rule set returned from kernel, check and store it."""
        try:
            ipset_definition, *ipset_data = plaintext_rules.split("\n")
        except ValueError: # "need more than 0 values to unpack"
            raise ValueError("Invalid ruleset to parse:\n{}".format(
                plaintext_rules))
        self._parse_kernel_ipset_definition(ipset_definition)
        self._parse_kernel_ipsets(ipset_data)

    def _parse_kernel_ipset_definition(self, ipset_definition):
        """
        Parse first line of ipset output, check and store data.

        First line should be: "'create' setname type 'range' range"
        """
        words = ipset_definition.split(' ')
        if len(words) < 5 or words[0] != 'create':
            raise ValueError(
                "Unexpected string, got '{}' in stead of 'create ...'" \
                    .format(ipset_definition))
        if self.name is not None:
            self.name = words[1]
        else:
            # Managing spaces in set name (even if use is strongly discouraged)
            try:
                words[1] = ' '.join(words[1 : len(self.name.split(' ')) + 1])
            except IndexError:
                raise ValueError(
                    "Wrong set described, got '{}', expecting '{}'".format(
                        ipset_definition, self.name))
            if words[1] != self.name:
                raise ValueError(
                    "Wrong set described, got '{}', expecting '{}'".format(
                        words[1], self.name))
        if len(words) < 5:
            raise ValueError(
                "Too short string, got '{}' in stead of 'create ...'" \
                    .format(ipset_definition))
        if self.type_ is None:
            self.type_ = words[2]
        elif self.type_ != words[2]:
            raise ValueError(
                "Wrong set described, got '{}', expecting '{}'".format(
                    words[1], self.type_))
        if words[3] == 'range':
            range_ = tuple(map(netaddr.IPAddress, words[4].split('-')))
            if self.range_ == (None, None):
                self.range_ = range_
            elif self.range_ != range_:
                raise ValueError(
                    "Wrong range, got '{}', expecting '{}'".format(
                        words[4], self._range_str()))
        else:
            raise ValueError(
                "ipset definition has no range: '{}'." \
                .format(ipset_definition))

    def _parse_kernel_ipsets(self, ipsets):
        """Parse lines of ipset output from kernel, storing data."""
        for line in ipsets:
            words = line.split(' ')
            if words[0:2] == ['add', self.name]:
                ip, mac = words[2].split(',')
                ip = netaddr.IPAddress(ip)
                mac = netaddr.EUI(mac, dialect=CustomMACFormat)
                if self.in_range(ip):
                    self.active_rules.append((ip, mac))
                else:
                    raise ValueError(
                        'IP {} not in range {}.'.format(ip, self._range_str()))
            else:
                raise ValueError(
                    "Unable to parse current ipset: unexpected output: {}"
                    .format(line))

    def in_range(self, ip):
        """Test if ip is in the set range."""
        inf, sup = self.range_
        return inf.version == ip.version \
            and hex(inf) <= hex(ip) <= hex(sup)

    def _range_str(self):
        """Returns the set range in string format IP_1-IP_2."""
        return "{}-{}".format(*map(str, self.range_))

    def get_new_rules(self):
        '''Get rules to apply from re2o in self.target_rules.'''
        json_rules = self.get_json_rules()
        self.parse_json_rules(json_rules)

    @classmethod
    def get_json_rules(cls, data_source_url=None, login_url=None):
        """Get JSON rules from Re2o and return a JSON string."""
        if data_source_url is None:
            data_source_url = cls.DATA_SOURCE_URL
        if login_url is None:
            login_url = cls.LOGIN_URL
        login_connexion = requests.post(
            login_url, data=cls.HTTP_AUTHENTICATION_PARAMS)
        json_data = requests.post(
            data_source_url, cookies=login_connexion.cookies)
        return json_data.content.decode()

    def parse_json_rules(self, json_rules):
        """
        Parse JSON rules and store them in target_rules.

        Fragile code due to re2o REST export.
        """
        data = json.loads(json_rules.strip())
        ip = None
        mac = None
        for couple in data:
            if 'ipv4' in couple:
                ip = couple['ipv4'].get('ipv4', None)
                if ip is None:
                    raise ValueError(
                        'Missing IP in IP, MAC couple: "{}".'.format(couple))
                if couple['ipv4']['ip_type'] != 'adhérent':
                    continue # Skipping useless IP
                ip = netaddr.IPAddress(ip)
            elif 'ipv6' in couple:
                raise NotImplementedError('No IPv6 support yet.')
                #ip = netaddr.IPAddress(couple['ipv6'])
            else:
                raise ValueError(
                    'Missing IP in IP, MAC couple: "{}".'.format(couple))
            if 'mac_address' in couple:
                mac = netaddr.EUI(couple['mac_address'],
                                  dialect=CustomMACFormat)
            else:
                raise ValueError(
                    'Missing MAC in IP, MAC couple: "{}".'.format(couple))
            if self.in_range(ip):
                self.target_rules.append((ip, mac))
            else:
                raise ValueError(
                    'IP {} not in range {}.'.format(ip, self._range_str()))

    def add_rule_to_kernel(self, rule):
        """Add a rule to kernel set."""
        self._add_del_rule_to_kernel(rule, 'add')

    def del_rule_to_kernel(self, rule):
        """Del a rule from kernel set."""
        self._add_del_rule_to_kernel(rule, 'del')

    def _add_del_rule_to_kernel(self, rule, action):
        """Add or del a rule to/from kernel set."""
        if action not in ['add', 'del']:
            raise ValueError((
                "Action must be either 'add' or 'del', "
                "{} is not a valid action.".format(action)))
        # No check that IP is in right range
        ipset_call = subprocess.Popen(
            [
                "/usr/bin/sudo", "/sbin/ipset",
                action, self.name,
                "{ip},{mac}".format(ip=rule[0], mac=rule[1])
            ],
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True)
        stdout, stderr = ipset_call.communicate()
        if ipset_call.returncode != 0:
            raise OSError(
                "Unable to get current ipset, return code: {}\n{}"
                .format(ipset_call.returncode, stderr))
        return stdout.strip()

    def apply_target_rules(self):
        """Apply changes needed to get target rules applied by firewall."""
        rules_to_add = set(self.target_rules) - set(self.active_rules)
        rules_to_del = set(self.active_rules) - set(self.target_rules)
        for rule in rules_to_del:
            self.del_rule_to_kernel(rule)
        for rule in rules_to_add:
            self.add_rule_to_kernel(rule)


