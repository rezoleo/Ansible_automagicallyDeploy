"""
connexion_manager.py

@author: Hugo Levy-Falk
"""
import pickle

import requests
import requests.utils

from affichage import prettyDoin
from config import Config

CONFIG = Config()


class ConnectionManager:
    """Manage connection to re2o, e.g. reconnects to the site if it's needed.

    Please, use this class in a `with` statement to ensure cookies are saved
    ine a `.cookies` file when it's destroyed.
    """

    def __init__(self, anim=True):
        self.anim = anim
        self.session = requests.Session()
        self.csrftoken = None
        self.errors = []

    def __enter__(self):
        self.load_cookies()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.save_cookies()

    def load_cookies(self):
        """Try to load the cookies from a .cookies file.
        If the file is empty, the cookies are initilized empty.
        """
        try:
            with open('.cookies', 'rb') as f:
                cookies = requests.utils.cookiejar_from_dict(pickle.load(f))
                self.session.cookies = cookies
        except FileNotFoundError:
            prettyDoin("Le fichier de sauvegarde des cookies n'existe pas.", "Warning")
        except EOFError:
            prettyDoin("Le fichier de sauvegarde des cookies est vide.", "Warning")

    def save_cookies(self):
        """Save the cookies to a .cookies file"""
        with open('.cookies', 'wb') as f:
            cookies = requests.utils.dict_from_cookiejar(self.session.cookies)
            cookies.pop('csrftoken', None)
            pickle.dump(cookies, f)

    def get_csrf_token(self, url):
        self.session.get(url)
        self.csrftoken = self.session.cookies['csrftoken']

    def connect(self):
        """Connect to re2o."""
        if self.anim:
            prettyDoin("Initialisation de la connexion", "...")
        try:
            login_url = CONFIG.get_url('login')
            self.get_csrf_token(login_url)
            self.login_data = {
                'username': CONFIG['Default']['USERNAME'],
                'password': CONFIG['Default']['PASSWORD'],
                'csrfmiddlewaretoken': self.csrftoken
            }
            self.session.post(
                login_url,
                data=self.login_data,
                headers=dict(referer=login_url)
            )
            if self.anim:
                prettyDoin("Initialisation de la connexion", "Ok")
        except Exception as err:
            if self.anim:
                prettyDoin("Initialisation de la connexion", "Error")
            print(err)
            self.errors.append(err)

    def get(self, *args, **kwargs):
        """This is a wrapper around requests.get to use authentification
        cookies. Be carefull not to set the `allow_redirects` flag as it is
        used to determine whether we need to authenticate or not.
        """
        r = self.session.get(
            allow_redirects=False,
            *args,
            **kwargs
        )
        if r.is_redirect:
            self.connect()
            return self.get(*args, **kwargs)
        return r

    def post(self, *args, **kwargs):
        """This is a wrapper around requests.post to use authentification
        cookies. Be carefull not to set the `allow_redirects` flag as it is
        used to determine whether we need to authenticate or not.
        """
        r = self.session.post(
            allow_redirects=False,
            *args,
            **kwargs
        )
        if r.is_redirect:
            self.connect()
            return self.post(*args, **kwargs)
        return r
