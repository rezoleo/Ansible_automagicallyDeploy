#!/usr/bin/python3
"""
Created on Thu Oct  6 01:11:54 2016

Suite d'affichage

@author: Pierre-Elliott Bécue, Gabriel Détraz
"""

import sys
import os
import fcntl
import termios
import struct
import time
import re

OCT_NAMES = ["Pio", "Tio", "Gio", "Mio", "Kio"]
OCT_SIZES = [1024**(len(OCT_NAMES) - i) for i in range(0, len(OCT_NAMES))]
TERM_FORMAT = '\x1b\[[0-1];([0-9]|[0-9][0-9])m'
DIALOG_FORMAT = '\\\Z.'
SEP_COL = "|"


import functools

def static_var(*couples):
    """Decorator setting static variable
    to a function.

    """
    # Using setattr magic, we set static
    # variable on function. This avoid
    # computing stuff again.
    def decorate(fun):
        functools.wraps(fun)
        for (name, val) in couples:
            setattr(fun, name, val)
        return fun
    return decorate

@static_var(("styles", {}))
def style(texte, what=None, dialog=False):
    """Pretty text is pretty
    On peut appliquer plusieurs styles d'affilée, ils seront alors traités
    de gauche à droite (les plus à droite sont donc ceux appliqués en dernier,
    et les plus à gauche en premier, ce qui veut dire que les plus à droite
    viennent après, et non avant, de fait, comme ils arrivent après, ils
    n'arrivent pas avant, et du coup, ceux qui arrivent avant peuvent être
    écrasés par ceux qui arrivent après…

    Tout ça pour dire que style(texte, ['vert', 'blanc', 'bleu', 'kaki']) est
    équivalent à style(texte, ['kaki']) qui équivaut à
    KeyError                                  Traceback (most recent call last)
    <ipython-input-2-d9c32f2123f0> in <module>()
    ----> 1 styles['kaki']

    KeyError: 'kaki'
    Sinon, il est possible de changer la couleur de fond grace aux couleur
    f_<couleur>, et de mettre du GRAS (je songe encore à un module qui fasse du
    UPPER, parce que c'est inutile, donc kewl.

    """
    if what is None:
        what = []

    if dialog:
        return dialogStyle(texte, what)

    if what:
        what = [what]

    if not what:
        return texte
    # Si la variable statique styles n'est pas peuplée…
    if style.styles == {}:
        zeros = {
            'noir'      : 30,
            'rougefonce': 31,
            'vertfonce' : 32,
            'orange'    : 33,
            'bleufonce' : 34,
            'violet'    : 35,
            'cyanfonce' : 36,
            'grisclair' : 37,
        }

        # Méthode "automatisée" pour remplir la version "background" des codes
        # couleur du shell.
        f_zeros = { "f_"+coul : val+10 for (coul, val) in zeros.items() }
        zeros.update(f_zeros)
        zeros = { coul: "0;%s" % (val,) for (coul, val) in zeros.items() }

        # Plus de couleurs (les codes sont de la forme \033[0;blah ou \033[1;blah, donc
        # ici on remplit la partie 1;.
        ones = {
            'gris': 30,
            'rouge': 31,
            'vert': 32,
            'jaune': 33,
            'bleu': 34,
            'magenta': 35,
            'cyan': 36,
            'blanc': 37,
            'gras': 50,
        }

        f_ones = { "f_"+coul : val+10 for (coul, val) in ones.items() }
        ones.update(f_ones)
        ones = { coul: "1;%s" % (val,) for (coul, val) in ones.items() }
        style.styles.update(zeros)
        style.styles.update(ones)
        style.styles["none"] = "1;0"

    for element in what:
        texte = "\033[%sm%s\033[1;0m" % (style.styles[element], texte)
    return texte

OK = style('Ok', 'vert')
WARNING = style('Warning', 'jaune')
ERREUR = style('Erreur', 'rouge')

def prettyDoin(what, status):
    """Affiche une opération en cours et met son statut à jour

    """
    if status == "...":
        sys.stdout.write("\r[%s] %s" % (style(status, "jaune"), what))
    elif status == "Ok":
        sys.stdout.write("\r[%s] %s\n" % (OK, what))
    elif status == "Warning":
        sys.stdout.write("\r[%s] %s\n" % (WARNING, what))
    else:
        sys.stdout.write("\r[%s] %s\n" % (ERREUR, what))
    sys.stdout.flush()

def cap_text(data, length, dialog=False):
    """Tronque une chaîne à une certaine longueur en excluant
    les commandes de style.

    """
    # découpage d'une chaine trop longue
    regexp = re.compile(DIALOG_FORMAT if dialog else TERM_FORMAT)
    new_data = ''
    new_len = 0

    # On laisse la mise en forme et on coupe les caratères affichés
    while True :
        s = regexp.search(data)
        if s:
            if s.start() + new_len > length:
                new_data += data[:length - new_len - 1] + nostyle() + '*'
                break
            else:
                new_data += data[:s.end()]
                data = data[s.end():]
                new_len += s.start()
        else:
            if new_len + len(data) > length:
                new_data += data[:length - new_len - 1] + '*'
                data = ""
            else:
                new_data += data
                data = ""

        if not data:
            break
    return new_data

def format_percent(percent):
    """Formatte les pourcentages en ajoutant des espaces si
    nécessaire.

    """

    if percent < 10:
        return "  %s" % (percent,)
    elif percent < 100:
        return " %s" % (percent,)
    else:
        return str(percent)

def rojv(percent, seuils=(100, 75, 50, 25), couls=("cyan", "vert", "jaune", "orange", "rouge")):
    """Retourne la couleur qui va bien avec le pourcentage

    Les pourcentages seuil, et les couleurs associées, doivent être
    rangés en ordre décroissant.

    """
    lens = len(seuils)
    lenc = len(couls)
    if lens + 1 == lenc:
        coul = couls[0]
        for i in range(lens):
            if percent < seuils[i]:
                coul = couls[i + 1]
    else:
        raise EnvironmentError("Seuils doit contenir une variable de moins par rapport à couls")
    return coul

def getTerminalSize():
    """Dummy function to get term dimensions.
    Thanks to http://stackoverflow.com/questions/566746/how-to-get-console-window-width-in-python

    Could be done using only env variables or thing like stty size, but would be less
    portable.

    """

    def ioctl_GWINSZ(fd):
        try:
            # unpack C structure, the first argument says that we will get two short
            # integers (h).
            # ioctl is a C function which do an operation on a file descriptor, the operation
            # here is termios.TIOCGWINSZ which will get the return to be term size. The third
            # argument is a buffer passed to ioctl. Its size is used to define the size of the
            # the return
            cr = struct.unpack(b'hh', fcntl.ioctl(fd, termios.TIOCGWINSZ, b'1234'))
        except:
            return
        return cr

    # First, we use this magic function on stdin/stdout/stderr.
    cr = ioctl_GWINSZ(0) or ioctl_GWINSZ(1) or ioctl_GWINSZ(2)

    # If that didn't work, we try to do this on a custom file descriptor.
    if not cr:
        try:
            fd = os.open(os.ctermid(), os.O_RDONLY)
            cr = ioctl_GWINSZ(fd)
            os.close(fd)
        except:
            pass

    # If that failed, we use os.environ, and if that fails, we set default values.
    if not cr:
        cr = (os.environ.get('LINES', 25), os.environ.get('COLUMNS', 80))
    return int(cr[1]), int(cr[0])

class Animation(object):
    """Propose une animation lors de la mise à jour ou de
    l'évolution d'une tâche.

    Si le nombre de cycles est défini, affiche un pourcentage
    d'évolution.

    Si l'option kikoo est définit, met une jauge en plus.

    Sinon, affiche un truc qui tourne.

    """

    def __init__(self, texte, nb_cycles=0, couleur=True, kikoo=True, timer=True):
        """__init__

        """
        self.texte = texte
        self.nb_cycles = nb_cycles
        self._kikoo = kikoo
        self.step = 0
        self.couleur = couleur
        self.timer = timer
        self.beginTime = 0

    def kikoo(self, kikoo):
        """Switch pour la valeur kikoo"""
        self._kikoo = kikoo

    def new_step(self):
        """Effectue une étape dans l'affichage

        """
        if self.step == 0 and self.timer:
            self.beginTime = time.time()
        cols, _ = getTerminalSize()

        # La seule façon efficace de faire de l'affichage de barres de chargement ou autres dynamiquement
        # est d'utiliser sys.stdout. C'est pas super propre, mais de toute façon, les trucs kikoo c'est
        # rarement propre, d'abord.

        # Si le nombre de cycles est indéfini, on affiche une "barre de chargement" non bornée.
        if not self.nb_cycles > 0:
            proceeding = "\r%s ..... %s" % (cap_text(self.texte, cols - 10), "\|/-"[self.step % 4])
            sys.stdout.write(proceeding)
        # Sinon, on affiche un truc avec une progression/un pourcentage
        else:
            percent = int((self.step + 1.0)/self.nb_cycles * 100)

            # Quand on manque de colonnes, on évite les trucs trop verbeux, idem si la kikooness
            # n'est pas demandée.
            if not self._kikoo or cols <= 55:
                if self.couleur:
                    # Avec de la couleur.
                    percent = style("%s %%" % (format_percent(percent),), rojv(percent))
                else:
                    # Sans couleur (so sad)
                    percent = "%s %%" % (format_percent(percent),)
                proceeding = "\r%s : %s" % (cap_text(self.texte, cols - 10), percent)
                sys.stdout.write(proceeding)

            # Du kikoo¬! Du kikoo¬!
            else:
                # La kikoo bar est une barre de la forme [======>                   ]
                # Nombre de =
                amount = percent/4

                if self.couleur:
                    # kikoo_print contient la barre et le pourcentage, colorés en fonction du pourcentage
                    kikoo_print = style("[%s%s%s] %s %%" % (int(amount) * '=',
                                                           ">",
                                                           (25-int(amount)) * ' ',
                                                           format_percent(percent)),
                                        rojv(percent))

                else:
                    kikoo_print = "[%s%s%s] %s %%" % (int(amount) * '=',
                                                     ">",
                                                     (25-int(amount)) * ' ',
                                                     format_percent(percent))
                proceeding = "\r%s %s" % (cap_text(self.texte, cols - 45), kikoo_print)
                sys.stdout.write(proceeding)

        # What if we add more kikoo?
        if self.timer:
            self.elapsedTime = time.time() - self.beginTime
            proceeding = " (temps écoulé : %ds)" % (self.elapsedTime)
            sys.stdout.write(proceeding)
        sys.stdout.flush()
        self.step += 1

    def end(self):
        """Prints a line return"""
        sys.stdout.write("\n")
        sys.stdout.flush()

if __name__ == "__main__":
    import time
    a = Animation(texte="Test de l'animation", nb_cycles=10000, couleur=True, kikoo=True)
    for i in range(0, a.nb_cycles):
        time.sleep(0.0001)
        a.new_step()
    a.end()
    prettyDoin("Je cuis des carottes.", "...")
    time.sleep(1)
    prettyDoin("Les carottes sont cuites." , "Ok")
