# -*- coding: utf-8 -*-

""" License

    Copyright (C) 2013 YunoHost

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program; if not, see http://www.gnu.org/licenses

"""

import sys
import os
import json
import cracklib
import string

SMALL_PWD_LIST = ["yunohost", "olinuxino", "olinux", "raspberry", "admin",
                  "root", "test", "rpi"]

MOST_USED_PASSWORDS = '/usr/local/share/dict/cracklib/100000-most-used'

# Length, digits, lowers, uppers, others
STRENGTH_LEVELS = [
    (6, 0, 0, 0, 0),
    (8, 1, 1, 1, 0),
    (8, 1, 1, 1, 1),
    (12, 1, 1, 1, 1),
]

def assert_password_is_strong_enough(profile, password):
    PasswordValidator(profile).validate(password)

class PasswordValidator(object):

    def __init__(self, profile):
        """
        Initialize a password validator.

        The profile shall be either "user" or "admin"
        and will correspond to a validation strength
        defined via the setting "security.password.<profile>.strength"
        """

        self.profile = profile
        try:
            # We do this "manually" instead of using settings_get()
            # from settings.py because this file is also meant to be
            # use as a script by ssowat.
            # (or at least that's my understanding -- Alex)
            settings = json.load(open('/etc/yunohost/settings.json', "r"))
            setting_key = "security.password." + profile + ".strength"
            self.validation_strength = int(settings[setting_key])
        except Exception as e:
            # Fallback to default value if we can't fetch settings for some reason
            self.validation_strength = 2 if profile == 'admin' else 1

    def validate(self, password):
        """
        Check the validation_summary and trigger the corresponding
        exception or info message

        This method is meant to be used from inside YunoHost's code
        (compared to validation_summary which is meant to be called
        by ssowat)
        """
        if self.validation_strength == -1:
            return

        # Note that those imports are made here and can't be put
        # on top (at least not the moulinette ones)
        # because the moulinette needs to be correctly initialized
        # as well as modules available in python's path.
        import errno
        import logging
        from moulinette import m18n
        from moulinette.core import MoulinetteError
        from moulinette.utils.log import getActionLogger

        logger = logging.getLogger('yunohost.utils.password')

        status, msg = validation_summary(password)
        if status == "error":
            raise MoulinetteError(1, m18n.n(msg))
        elif status == "warning":
            logger.info(m18n.n(msg))

    def validation_summary(self, password):
        """
        Check if a password is listed in the list of most used password
        and if the overall strength is good enough compared to the
        validation_strength defined in the constructor.

        Produces a summary-tuple comprised of a level (success, error, warning)
        and a message key describing the issues found.
        """
        if self.validation_strength < 0:
            return ("success", "")

        listed = password in SMALL_PWD_LIST or self.is_in_cracklib_list(password)
        strength_level = self.strength_level(password)
        if listed:
            return ("error", "password_listed")
        if strength_level < self.validation_strength:
            return ("error", "password_too_simple_%s" % self.validation_strength)

        if strength_level < 3:
            return ("warning", 'password_advice')
        return ("success", "")

    def strength(self, password):
        """
        Returns the strength of a password, defined as a tuple
        containing the length of the password, the number of digits,
        lowercase letters, uppercase letters, and other characters.

        For instance, "PikachuDu67" is (11, 2, 7, 2, 0)
        """

        length = len(password)
        digits = 0
        uppers = 0
        lowers = 0
        others = 0

        for character in password:
            if character in string.digits:
                digits = digits + 1
            elif character in string.ascii_uppercase:
                uppers = uppers + 1
            elif character in string.ascii_lowercase:
                lowers = lowers + 1
            else:
                others = others + 1

        return (length, digits, lowers, uppers, others)

    def strength_level(self, password):
        """
        Computes the strength of a password and compares
        it to the STRENGTH_LEVELS.

        Returns an int corresponding to the highest STRENGTH_LEVEL
        satisfied by the password.
        """

        strength = self.strength(password)

        strength_level = 0
        # Iterate over each level and its criterias
        for level, level_criterias in enumerate(STRENGTH_LEVELS):
            # Iterate simulatenously over the level criterias (e.g. [8, 1, 1, 1, 0])
            # and the strength of the password (e.g. [11, 2, 7, 2, 0])
            # and compare the values 1-by-1.
            # If one False is found, the password does not satisfy the level
            if False in [s>=c for s, c in zip(strength, level_criterias)]:
                break
            # Otherwise, the strength of the password is at least of the current level.
            strength_level = level + 1

        return strength_level

    def is_in_cracklib_list(self, password):
        try:
            cracklib.VeryFascistCheck(password, None, MOST_USED_PASSWORDS)
        except ValueError as e:
            # We only want the dictionnary check of cracklib, not the is_simple
            # test.
            if str(e) not in ["is too simple", "is a palindrome"]:
                return True
        return False


# This file is also meant to be used as an executable by
# SSOwat to validate password from the portal when an user
# change its password.
if __name__ == '__main__':
    if len(sys.argv) < 2:
        import getpass
        pwd = getpass.getpass("")
        #print("usage: password.py PASSWORD")
    else:
        pwd = sys.argv[1]
    status, msg = PasswordValidator('user').validation_summary(pwd)
    print(msg)
    sys.exit(0)
