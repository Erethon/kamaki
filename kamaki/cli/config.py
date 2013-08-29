# Copyright 2011-2013 GRNET S.A. All rights reserved.
#
# Redistribution and use in source and binary forms, with or
# without modification, are permitted provided that the following
# conditions are met:
#
#   1. Redistributions of source code must retain the above
#      copyright notice, this list of conditions and the following
#      disclaimer.
#
#   2. Redistributions in binary form must reproduce the above
#      copyright notice, this list of conditions and the following
#      disclaimer in the documentation and/or other materials
#      provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY GRNET S.A. ``AS IS'' AND ANY EXPRESS
# OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL GRNET S.A OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF
# USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
# AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and
# documentation are those of the authors and should not be
# interpreted as representing official policies, either expressed
# or implied, of GRNET S.A.

import os
from logging import getLogger

from collections import defaultdict
from ConfigParser import RawConfigParser, NoOptionError, NoSectionError, Error
from re import match

from kamaki.cli.errors import CLISyntaxError
from kamaki import __version__

try:
    from collections import OrderedDict
except ImportError:
    from kamaki.clients.utils.ordereddict import OrderedDict


class InvalidCloudNameError(Error):
    """A valid cloud name is accepted by this regex: ([~@#$:-\w]+)"""


log = getLogger(__name__)

# Path to the file that stores the configuration
CONFIG_PATH = os.path.expanduser('~/.kamakirc')
HISTORY_PATH = os.path.expanduser('~/.kamaki.history')
CLOUD_PREFIX = 'cloud'

# Name of a shell variable to bypass the CONFIG_PATH value
CONFIG_ENV = 'KAMAKI_CONFIG'

version = ''
for c in '%s' % __version__:
    if c not in '0.123456789':
        break
    version += c
HEADER = '# Kamaki configuration file v%s\n' % version

DEFAULTS = {
    'global': {
        'default_cloud': '',
        'colors': 'off',
        'log_file': os.path.expanduser('~/.kamaki.log'),
        'log_token': 'off',
        'log_data': 'off',
        'log_pid': 'off',
        'max_threads': 7,
        'history_file': HISTORY_PATH,
        'user_cli': 'astakos',
        'file_cli': 'pithos',
        'server_cli': 'cyclades',
        'flavor_cli': 'cyclades',
        'network_cli': 'cyclades',
        'image_cli': 'image',
        'config_cli': 'config',
        'history_cli': 'history'
        #  Optional command specs:
        #  'livetest_cli': 'livetest',
        #  'astakos_cli': 'snf-astakos'
        #  'floating_cli': 'cyclades'
    },
    CLOUD_PREFIX:
    {
        #'default': {
        #    'url': '',
        #    'token': ''
        #    'pithos_type': 'object-store',
        #    'pithos_version': 'v1',
        #    'cyclades_type': 'compute',
        #    'cyclades_version': 'v2.0',
        #    'plankton_type': 'image',
        #    'plankton_version': '',
        #    'astakos_type': 'identity',
        #    'astakos_version': 'v2.0'
        #}
    }
}


try:
    import astakosclient
    DEFAULTS['global'].update(dict(astakos_cli='snf-astakos'))
except ImportError:
    pass


class Config(RawConfigParser):
    def __init__(self, path=None, with_defaults=True):
        RawConfigParser.__init__(self, dict_type=OrderedDict)
        self.path = path or os.environ.get(CONFIG_ENV, CONFIG_PATH)
        self._overrides = defaultdict(dict)
        if with_defaults:
            self._load_defaults()
        self.read(self.path)

        for section in self.sections():
            r = self._cloud_name(section)
            if r:
                for k, v in self.items(section):
                    self.set_cloud(r, k, v)
                self.remove_section(section)

    @staticmethod
    def _cloud_name(full_section_name):
        if not full_section_name.startswith(CLOUD_PREFIX + ' '):
            return None
        matcher = match(CLOUD_PREFIX + ' "([~@#$:\-\w]+)"', full_section_name)
        if matcher:
            return matcher.groups()[0]
        else:
            icn = full_section_name[len(CLOUD_PREFIX) + 1:]
            raise InvalidCloudNameError('Invalid Cloud Name %s' % icn)

    def rescue_old_file(self):
        lost_terms = []
        global_terms = DEFAULTS['global'].keys()
        translations = dict(
            config=dict(serv='', cmd='config'),
            history=dict(serv='', cmd='history'),
            pithos=dict(serv='pithos', cmd='file'),
            file=dict(serv='pithos', cmd='file'),
            store=dict(serv='pithos', cmd='file'),
            storage=dict(serv='pithos', cmd='file'),
            image=dict(serv='plankton', cmd='image'),
            plankton=dict(serv='plankton', cmd='image'),
            compute=dict(serv='compute', cmd=''),
            cyclades=dict(serv='compute', cmd='server'),
            server=dict(serv='compute', cmd='server'),
            flavor=dict(serv='compute', cmd='flavor'),
            network=dict(serv='compute', cmd='network'),
            astakos=dict(serv='astakos', cmd='user'),
            user=dict(serv='astakos', cmd='user'),
        )

        self.set('global', 'default_' + CLOUD_PREFIX, 'default')
        for s in self.sections():
            if s in ('global'):
                # global.url, global.token -->
                # cloud.default.url, cloud.default.token
                for term in set(self.keys(s)).difference(global_terms):
                    if term not in ('url', 'token'):
                        lost_terms.append('%s.%s = %s' % (
                            s, term, self.get(s, term)))
                        self.remove_option(s, term)
                        continue
                    gval = self.get(s, term)
                    try:
                        cval = self.get_cloud('default', term)
                    except KeyError:
                        cval = ''
                    if gval and cval and (
                        gval.lower().strip('/') != cval.lower().strip('/')):
                            raise CLISyntaxError(
                                'Conflicting values for default %s' % term,
                                importance=2, details=[
                                    ' global.%s:  %s' % (term, gval),
                                    ' %s.default.%s:  %s' % (
                                        CLOUD_PREFIX, term, cval),
                                    'Please remove one of them manually:',
                                    ' /config delete global.%s' % term,
                                    ' or'
                                    ' /config delete %s.default.%s' % (
                                        CLOUD_PREFIX, term),
                                    'and try again'])
                    elif gval:
                        print('... rescue %s.%s => %s.default.%s' % (
                            s, term, CLOUD_PREFIX, term))
                        self.set_cloud('default', term, gval)
                    self.remove_option(s, term)
            # translation for <service> or <command> settings
            # <service> or <command group> settings --> translation --> global
            elif s in translations:

                if s in ('history',):
                    k = 'file'
                    v = self.get(s, k)
                    if v:
                        print('... rescue %s.%s => global.%s_%s' % (
                            s, k, s, k))
                        self.set('global', '%s_%s' % (s, k), v)
                        self.remove_option(s, k)

                trn = translations[s]
                for k, v in self.items(s, False):
                    if v and k in ('cli',):
                        print('... rescue %s.%s => global.%s_cli' % (
                            s, k, trn['cmd']))
                        self.set('global', '%s_cli' % trn['cmd'], v)
                    elif k in ('container',) and trn['serv'] in ('pithos',):
                        print('... rescue %s.%s => %s.default.pithos_%s' % (
                                    s, k, CLOUD_PREFIX, k))
                        self.set_cloud('default', 'pithos_%s' % k, v)
                    else:
                        lost_terms.append('%s.%s = %s' % (s, k, v))
                self.remove_section(s)
        #  self.pretty_print()
        return lost_terms

    def pretty_print(self):
        for s in self.sections():
            print s
            for k, v in self.items(s):
                if isinstance(v, dict):
                    print '\t', k, '=> {'
                    for ki, vi in v.items():
                        print '\t\t', ki, '=>', vi
                    print('\t}')
                else:
                    print '\t', k, '=>', v

    def guess_version(self):
        """
        :returns: (float) version of the config file or 0.0 if unrecognized
        """
        checker = Config(self.path, with_defaults=False)
        sections = checker.sections()
        log.warning('Config file heuristic 1: old global section ?')
        if 'global' in sections:
            if checker.get('global', 'url') or checker.get('global', 'token'):
                log.warning('..... config file has an old global section')
                return 0.8
        log.warning('........ nope')
        log.warning('Config file heuristic 2: Any cloud sections ?')
        if CLOUD_PREFIX in sections:
            for r in self.keys(CLOUD_PREFIX):
                log.warning('... found cloud "%s"' % r)
                return 0.9
        log.warning('........ nope')
        log.warning('All heuristics failed, cannot decide')
        return 0.9

    def get_cloud(self, cloud, option):
        """
        :param cloud: (str) cloud alias

        :param option: (str) option in cloud section

        :returns: (str) the value assigned on this option

        :raises KeyError: if cloud or cloud's option does not exist
        """
        r = self.get(CLOUD_PREFIX, cloud)
        if not r:
            raise KeyError('Cloud "%s" does not exist' % cloud)
        return r[option]

    def get_global(self, option):
        return self.get('global', option)

    def set_cloud(self, cloud, option, value):
        try:
            d = self.get(CLOUD_PREFIX, cloud) or dict()
        except KeyError:
            d = dict()
        d[option] = value
        self.set(CLOUD_PREFIX, cloud, d)

    def set_global(self, option, value):
        self.set('global', option, value)

    def _load_defaults(self):
        for section, options in DEFAULTS.items():
            for option, val in options.items():
                self.set(section, option, val)

    def _get_dict(self, section, include_defaults=True):
        try:
            d = dict(DEFAULTS[section]) if include_defaults else {}
        except KeyError:
            d = {}
        try:
            d.update(RawConfigParser.items(self, section))
        except NoSectionError:
            pass
        return d

    def reload(self):
        self = self.__init__(self.path)

    def get(self, section, option):
        """
        :param section: (str) HINT: for clouds, use cloud.<section>

        :param option: (str)

        :returns: (str) the value stored at section: {option: value}
        """
        value = self._overrides.get(section, {}).get(option)
        if value is not None:
            return value
        prefix = CLOUD_PREFIX + '.'
        if section.startswith(prefix):
            return self.get_cloud(section[len(prefix):], option)
        try:
            return RawConfigParser.get(self, section, option)
        except (NoSectionError, NoOptionError):
            return DEFAULTS.get(section, {}).get(option)

    def set(self, section, option, value):
        """
        :param section: (str) HINT: for remotes use cloud.<section>

        :param option: (str)

        :param value: str
        """
        prefix = CLOUD_PREFIX + '.'
        if section.startswith(prefix):
            cloud = self._cloud_name(
                CLOUD_PREFIX + ' "' + section[len(prefix):] + '"')
            return self.set_cloud(cloud, option, value)
        if section not in RawConfigParser.sections(self):
            self.add_section(section)
        RawConfigParser.set(self, section, option, value)

    def remove_option(self, section, option, also_remove_default=False):
        try:
            if also_remove_default:
                DEFAULTS[section].pop(option)
            RawConfigParser.remove_option(self, section, option)
        except NoSectionError:
            pass

    def remove_from_cloud(self, cloud, option):
        d = self.get(CLOUD_PREFIX, cloud)
        if isinstance(d, dict):
            d.pop(option)

    def keys(self, section, include_defaults=True):
        d = self._get_dict(section, include_defaults)
        return d.keys()

    def items(self, section, include_defaults=True):
        d = self._get_dict(section, include_defaults)
        return d.items()

    def override(self, section, option, value):
        self._overrides[section][option] = value

    def write(self):
        cld_bu = self._get_dict(CLOUD_PREFIX)
        try:
            for r, d in self.items(CLOUD_PREFIX):
                for k, v in d.items():
                    self.set(CLOUD_PREFIX + ' "%s"' % r, k, v)
            self.remove_section(CLOUD_PREFIX)

            with open(self.path, 'w') as f:
                os.chmod(self.path, 0600)
                f.write(HEADER.lstrip())
                f.flush()
                RawConfigParser.write(self, f)
        finally:
            if CLOUD_PREFIX not in self.sections():
                self.add_section(CLOUD_PREFIX)
            for cloud, d in cld_bu.items():
                self.set(CLOUD_PREFIX, cloud, d)
