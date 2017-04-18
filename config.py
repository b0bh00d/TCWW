# pylint: disable=missing-docstring
# pylint: disable=missing-docstring
# pylint: disable=bad-whitespace

import os
import re
import sys
import socket

from optparse import OptionParser
import xml.dom.minidom as minidom

from cache_file import CacheFile

#-------------------------------------------------------------------------#
#     App: TeamCity9 Warning Watcher                                      #
#  Module: config.py                                                      #
#  Author: Bob Hood                                                       #
# License: LGPL-3.0                                                       #
#   PyVer: 2.7.x                                                          #
#  Detail: This module is responsible for reading in the TCWW             #
#          configurations and establishing the environment they directs.  #
#-------------------------------------------------------------------------#

class TeamCity(object):
    MICROSOFT, GCC = range(2)

    def __init__(self):
        self.agent_name = None
        self.project_name = None
        self.config_name = None
        self.branch_name = None
        self.build_number = 0
        self.build_step = 0

        self.build_agent_path = None
        self.build_agent_log_path = None

        self.warning_text = None
        self.warning_regex = None
        self.warning_format = None
        self.warning_format_regex = [".+\\((\\d+)\\) : warning C\\d+:",
                                     ".+:(\\d+):(\\d+): warning: "]
        #self.warning_compress = False

        self.config_keys = []

        # map with key being compound of Project, Config, BuildType, and value
        # is a list of interested parties
        self.interested_parties = {}

        self.cache_ftp = None

    def validate(self):
        result = True
        if not self.agent_name:
            print "An agent name is required",
            result = False
        elif not self.project_name:
            print "A project name is required",
            result = False
        elif not self.config_name:
            print "A config name is required",
            result = False
        elif not self.branch_name:
            print "A branch name is required",
            result = False
        elif self.build_number is 0:
            print "A build number is required",
            result = False
        else:
            if (self.warning_text is None) and \
               (self.warning_regex is None) and \
               (self.warning_format is None):
                print "A warning pattern of some kind if required",
                result = False

        return result

class Config(object):

    # pylint: disable=too-many-instance-attributes
    # This is a data-only class

    # pylint: disable=too-few-public-methods
    # This is a data-only class

    def __init__(self):
        # this is were previous scans are stored
        self.cache_file = None

        parser = OptionParser()
        parser.add_option("-b", "--build-number", type="int", dest="build_number",
                          metavar="<number>",
                          default=0, help="The current build number.")
        parser.add_option("-p", "--project", dest="project_name", default='',
                          metavar="<project_name>",
                          help="The name of the project being built.")
        parser.add_option("-a", "--agent", dest="agent_name", default=socket.gethostname(),
                          metavar="<agent_name>",
                          help="The name of the build agent performing the build.")
        parser.add_option("-S", "--build-step", type="int", dest="build_step",
                          metavar="<build_step>",
                          default=0, help="A specific build step to review for warnings.")
        parser.add_option("-c", "--config-name", dest="config_name", default='',
                          metavar="<config_name>",
                          help="The name of the project configuration being built.")
        parser.add_option("-B", "--branch-name", dest="branch_name", default='',
                          metavar="<branch>",
                          help="The branch being processed.")
        parser.add_option("-e", "--inflations-are-errors", action="store_true",
                          dest="inflations_are_errors", default=False,
                          help="If new warnings (inflations) are detected, " \
                                "the build will fail in TeamCity.")
        parser.add_option("-i", "--report-deflation", action="store_true",
                          dest="report_deflations", default=False,
                          help="Warnings missing from the current builds " \
                                "(deflations) are also reported.")
        parser.add_option("-s", "--silence-inflation", action="store_true",
                          dest="silence_inflations", default=False,
                          help="New warnings detected are not reported " \
                                "('inflations-are-errors' is still enforced).")
        parser.add_option("-f", "--fail-on-fragment", action="append",
                          dest="fail_on_fragment", default=[],
                          metavar="<text_fragment>",
                          help="If the specified text fragment is detected in " \
                                "the build output, automatically fail the build.")
        parser.add_option("-x", "--reset-cache", action="store_true",
                          dest="reset_cache", default=False,
                          help="Clear any previously saved cache before processing.")
        parser.add_option("-D", "--debug", action="store_true",
                          dest="debug_mode", default=False,
                          help="Print extra processing information (will add to log output)")

        (options, _) = parser.parse_args()

        self.teamcity = TeamCity()
        self.teamcity.agent_name = options.agent_name
        self.teamcity.project_name = options.project_name
        self.teamcity.config_name = options.config_name
        self.teamcity.branch_name = options.branch_name
        self.teamcity.build_number = int(options.build_number)
        self.teamcity.build_step = int(options.build_step)

        self.inflations_are_errors = options.inflations_are_errors
        self.report_deflations = options.report_deflations
        self.silence_inflations = options.silence_inflations
        self.fail_on_fragment = options.fail_on_fragment

        self.reset_cache = options.reset_cache

        self.debug_mode = options.debug_mode

        self.teamcity.config_keys.append(options.project_name)
        self.teamcity.config_keys.append('%s_%s' % (options.project_name, options.config_name))

        self._read_config()

        if not self.teamcity.validate():
            print '; disabling WarningWatcher'
            self.config_file = None

        self.working_prefix = os.getcwd().lower()
        if 'build_system' in self.working_prefix:
            ndx = self.working_prefix.index('build_system')
            self.working_prefix = self.working_prefix[:ndx - 1]
        else:
            self.working_prefix = None

    def _dump_dir(self, path, indent=0):
        for file_name in os.listdir(path):
            file_path = os.path.join(path, file_name)
            print '%s%s' % (' ' * indent, file_path)
            if os.path.isdir(file_path):
                self._dump_dir(file_path, indent + 2)

    def _read_config(self):
        self.config_file = os.path.join(os.path.split(os.path.realpath(__file__))[0],
                                        'builders_conf', '%s.xml' % self.teamcity.agent_name)
        if not os.path.exists(self.config_file):
            # see if we can access them using the environment
            if 'WWBLDRCFG' in os.environ:
                self.config_file = os.path.join(os.environ['WWBLDRCFG'], '%s.xml' % \
                    self.teamcity.agent_name)
            if not os.path.exists(self.config_file):
                self.config_file = None
                return

        dom = minidom.parse(self.config_file)
        settings_node = dom.getElementsByTagName("Settings")[0]
        counter = 0
        while counter < len(settings_node.childNodes):
            child1 = settings_node.childNodes[counter]
            if child1.nodeType == child1.ELEMENT_NODE:
                if child1.tagName == 'Cache':
                    self.cache_file = CacheFile(self, child1.getAttribute('value').strip())
                elif child1.tagName == 'AgentPath':
                    self.teamcity.build_agent_path = \
                        os.path.normpath(child1.getAttribute('value').strip())
                    if not os.path.exists(self.teamcity.build_agent_path):
                        print 'Error: TeamCity BuildAgent path cannot be accessed: "%s"' % \
                            self.teamcity.build_agent_path
                        sys.exit(1)
                    self.teamcity.build_agent_log_path = \
                        os.path.join(self.teamcity.build_agent_path, 'logs')
                    if not os.path.exists(self.teamcity.build_agent_log_path):
                        print 'Error: TeamCity BuildAgent log path cannot be accessed: "%s"' % \
                            self.teamcity.build_agent_log_path
                        sys.exit(1)
                elif child1.tagName == 'WarningText':
                    self.teamcity.warning_text = child1.getAttribute('value')
                elif child1.tagName == 'WarningRegex':
                    try:
                        self.teamcity.warning_regex = re.compile('(%s)' % \
                            child1.getAttribute('value'))
                    except:
                        print 'Error: TeamCity BuildAgent warning pattern ' \
                              'cannot be compiled: "%s"' % \
                            child1.getAttribute('value')
                        sys.exit(1)
                elif child1.tagName == 'WarningFormat':
                    compiler_type = child1.getAttribute('value').lower()
                    if compiler_type not in ['microsoft', 'visualstudio', 'gcc']:
                        print 'Error: TeamCity BuildAgent warning type unrecognized: "%s"' % \
                            child1.getAttribute('value')
                        sys.exit(1)
                    if compiler_type in ['microsoft', 'visualstudio']:
                        self.teamcity.warning_format = TeamCity.MICROSOFT
                    else:
                        self.teamcity.warning_format = TeamCity.GCC
            counter += 1

        if self.teamcity.warning_text and self.teamcity.warning_regex:
            print 'Error: Only one of "WarningText" or "WarningRegex" ' \
                  'can be defined for Agent "%s"' % \
                        self.teamcity.agent_name
            sys.exit(1)

        if self.cache_file is None:
            # put them in the system temp folder
            self.cache_file = CacheFile(self)

        ip_key = self.teamcity.project_name
        self.teamcity.interested_parties[ip_key] = []

        project_config_file = os.path.join(os.path.split(os.path.realpath(__file__))[0],
                                           'builders_conf', '%s_%s.xml' % \
                                               (self.teamcity.agent_name,
                                                self.teamcity.project_name))
        if os.path.exists(project_config_file):
            dom = minidom.parse(project_config_file)
            settings_node = dom.getElementsByTagName("Settings")[0]
            counter = 0
            while counter < len(settings_node.childNodes):
                child1 = settings_node.childNodes[counter]
                if child1.nodeType == child1.ELEMENT_NODE:
                    if child1.tagName == 'InterestedParties':
                        self.teamcity.interested_parties[ip_key] += [
                            t.strip().encode('ascii') for t in \
                                child1.firstChild.data.split(',')]
                counter += 1

        ip_key = '%s_%s' % (self.teamcity.project_name, self.teamcity.config_name)
        self.teamcity.interested_parties[ip_key] = []

        project_config_file = os.path.join(os.path.split(os.path.realpath(__file__))[0], \
            'builders_conf', '%s_%s_%s.xml' % \
                (self.teamcity.agent_name,
                 self.teamcity.project_name,
                 self.teamcity.config_name))
        if os.path.exists(project_config_file):
            dom = minidom.parse(project_config_file)
            settings_node = dom.getElementsByTagName("Settings")[0]
            counter = 0
            while counter < len(settings_node.childNodes):
                child1 = settings_node.childNodes[counter]
                if child1.nodeType == child1.ELEMENT_NODE:
                    if child1.tagName == 'InterestedParties':
                        self.teamcity.interested_parties[ip_key] += [
                            t.strip().encode('ascii') for t in \
                                child1.firstChild.data.split(',')]
                counter += 1
