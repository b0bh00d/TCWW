# pylint: disable=missing-docstring
# pylint: disable=bad-whitespace

import sys

from config import Config
from delta_generator import DeltaGenerator
from log_manager import LogManager

#-------------------------------------------------------------------------#
#     App: TeamCity9 Warning Watcher                                      #
#  Module: warning_watcher.py                                             #
#  Author: Bob Hood                                                       #
#   PyVer: 2.7.x                                                          #
# License: LGPL-3.0                                                       #
#  Detail: This module implements the entry point for the TeamCity        #
#          Warning Watcher.                                               #
#                                                                         #
# Example TC "Command Line" step script:                                  #
#                                                                         #
#     cd build_system/warning_watcher                                     #
#     python warning_watcher.py \                                         #
#        -b %system.build.number% \                                       #
#        -p "%system.teamcity.projectName%" \                             #
#        -a "%teamcity.agent.name%" \                                     #
#        -c "%system.teamcity.buildConfName%" \                           #
#        -B "%BranchName%" \                                              #
#        --report-deflation \                                             #
#        --inflations-are-errors                                          #
#                                                                         #
# Note that the first 5 arguments are required.                           #
#                                                                         #
# The TC step should IMMEDIATELY follow the build step that the Warning   #
# Watcher should evaluate (see screen shots).                             #
#-------------------------------------------------------------------------#

def main():
    # load in our configuration settings

    config = Config()
    if config.config_file is None:
        print 'BuildAgent config file not found; skipping step.'
        return

    generator = DeltaGenerator(config, LogManager(config))
    result = generator.run()
    if result and len(generator.error_message):
        print generator.error_message
    return 0

if __name__ == '__main__':
    sys.exit(main())
