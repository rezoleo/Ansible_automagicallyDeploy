#!/usr/bin/python3
"""
Created on Sun Sep 14 21:30:00 2017

@author: Maël Kervella
"""

import subprocess
from os import path
import importlib

from config import Config



CONFIG = Config()

mailman_home = CONFIG['Mailing']['MAILMAN_HOME']


def apply_conf(list_name, file_users):
    """Apply the conf given through a listname and a file listing
    all users for mailman service"""

    if not mailing_exist(list_name):
        create_mailing(list_name)
    sync_members(list_name, file_users)


def mailing_exist(list_name):
    """Check if the mailing exists in mailman database"""

    cmd = []
    cmd.append(path.join(mailman_home, 'bin', 'list_lists'))
    cmd.append('--bare') # Display only mailing names (no descriptions)

    lists = subprocess.check_output( cmd )
    return list_name.lower() in lists.decode('utf-8').splitlines()


def create_mailing(list_name):
    """Create the mailing in mailman database"""

    cmd = []
    cmd.append(path.join(mailman_home, 'bin', 'newlist'))
    cmd.append('--automate') # Make the command non-interactive
    cmd.append('--quiet')    # Don't send notification to the admin
    cmd.append(list_name)
    cmd.append(CONFIG['Mailing']['MAILING_ADMIN'])
    cmd.append(CONFIG['Mailing']['MAILING_PASSWORD'])

    subprocess.call( cmd )


def sync_members(list_name, file_users):
    """Sync the members of the given files with the given file"""

    cmd = []
    cmd.append(path.join(mailman_home, 'bin', 'sync_members'))
    cmd.append('--welcome-msg=no') # Don't send welcome message for subscription
    cmd.append('--goodbye-msg=no') # Don't send goodbye message for unsubscription
    cmd.append('--digest=no')      # Don't subscribe with digest option (groupped mails)
    cmd.append('--notifyadmin=no') # Don't send a notification to the admin
    cmd.append('--file'); cmd.append(file_users)
    cmd.append(list_name)

    subprocess.call( cmd )


