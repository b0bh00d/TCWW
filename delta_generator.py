# pylint: disable=missing-docstring
# pylint: disable=bad-whitespace
# pylint: disable=too-many-instance-attributes
# Classes may contain as many instance attributes required to perform their function

import re
import sys
import difflib

from constants import FileModes
from build_data import BuildData

#-------------------------------------------------------------------------#
#     App: TeamCity9 Warning Watcher                                      #
#  Module: delta_generator.py                                             #
#  Author: Bob Hood                                                       #
# License: LGPL-3.0                                                       #
#   PyVer: 2.7.x                                                          #
#  Detail: Contains the code to monitor the logs of a specific TeamCity   #
#          Build Agent and generate warning message differentials.        #
#-------------------------------------------------------------------------#

def _strip_number_runs(line):
    new_line = line
    while True:
        result = re.search('(\\d+)', new_line)
        if not result:
            break
        new_line = new_line[:result.start(1)] + new_line[result.end(1):]
    return new_line

class DeltaGenerator(object):
    def __init__(self, config, log_manager):
        super(DeltaGenerator, self).__init__()
        self.config = config
        self.log_manager = log_manager

        self.error_message = ''

        # set up our markers
        self.build_start = '--------- [ '           # this indicates the start of a build
        self.build_end = 'Process exited with code' # this indicates the end of a build

        self.latest_build = None
        self.latest_build_step = 0
        self.latest_warning_compression = set()
        self.latest_failure_fragments = set()

        self.cached_build = None
        self.current_step = None

        self._restore_state()

    def _generate_delta(self):
        """
        This method is used when the user specifies their own detection data
        with either WarningText or WatningRegex.  It doesn't 'normalize' the
        lines (e.g., remove line numbers) which will often lead to false
        positives.
        """
        result_code = 0

        cached_set = set()
        for warning in self.cached_build.warnings:
            cached_set.add(warning)
        latest_set = set()
        for warning in self.latest_build.warnings:
            latest_set.add(warning)

        # subtract the current Set from the previous to see what is new
        inflations = latest_set - cached_set

        if self.config.debug_mode:
            print 'Inflations:'
            if len(inflations):
                for line in inflations:
                    print '    ::', line
            else:
                print '    (none)'

        # subtract the previous Set from the current to see what is now missing
        deflations = cached_set - latest_set

        if self.config.debug_mode:
            print 'Deflations:'
            if len(deflations):
                for line in deflations:
                    print '    ::', line
            else:
                print '    (none)'

        if len(deflations) and self.config.report_deflations:
            info_tuple = None
            if self.config.teamcity.warning_regex:
                # calculate the actual number of warnings
                deflation_set = set()
                for line in deflations:
                    if line.endswith('\n'):
                        line = line.rstrip()
                    result = re.search(self.config.teamcity.warning_regex, line)
                    if result and result.lastindex:
                        if result.group(1) not in deflation_set:
                            deflation_set.add(result.group(1))
                info_tuple = (len(deflation_set),
                              's' if len(deflation_set) > 1 else '',
                              'were' if len(deflation_set) > 1 else 'was')
            else:
                info_tuple = (len(deflations),
                              's' if len(deflations) > 1 else '',
                              'were' if len(deflations) > 1 else 'was')

            print '%d previous warning%s %s no longer detected in the build:' % info_tuple

            for line in deflations:
                if line.endswith('\n'):
                    line = line.rstrip()
                print '   -', line
            print ''

        if len(inflations):
            if self.config.inflations_are_errors:
                self.error_message = "##teamcity[buildProblem description='%d new " \
                                      "warning%s discovered' identity='WarningWatcher']" % \
                    (len(inflations), 's' if len(inflations) > 1 else '')
                result_code = 1

            if not self.config.silence_inflations:
                info_tuple = None
                if self.config.teamcity.warning_regex:
                    # calculate the actual number of warnings
                    inflation_set = set()
                    for line in inflations:
                        if line.endswith('\n'):
                            line = line.rstrip()
                        result = re.search(self.config.teamcity.warning_regex, line)
                        if result and result.lastindex:
                            if result.group(1) not in inflation_set:
                                inflation_set.add(result.group(1))
                    info_tuple = (len(inflation_set),
                                  's' if len(inflation_set) > 1 else '',
                                  'were' if len(inflation_set) > 1 else 'was')
                else:
                    info_tuple = (len(inflations),
                                  's' if len(inflations) > 1 else '',
                                  'were' if len(inflations) > 1 else 'was')

                print '%d new warning%s %s detected in this build:' % info_tuple

                for line in inflations:
                    if line.endswith('\n'):
                        line = line.rstrip()
                    print '   +', line

                if False: """
                # various Skype notification attempts (none of which I've been able
                # to actually get to work with Skype so far)

                #Use Windows Script Host to inject text into a Skype window

                shell = win32com.client.Dispatch("WScript.Shell")
                shell.AppActivate("Alerts.%s" % self.config.teamcity.project_name)
                win32api.Sleep(500)
                shell.SendKeys(msg)
                shell.SendKeys("{ENTER}")
                win32api.Sleep(2500)
                # --------------------------
                msg2skype_path = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'MsgToSkype.exe')
                ip_group = {}
                for key in self.config.teamcity.config_keys:
                    if key in self.config.teamcity.interested_parties:
                        for ip in self.config.teamcity.interested_parties[key]:
                            ip_group[ip] = key.replace('_', '.')

                if len(ip_group) and os.path.exists(msg2skype_path):
                    # send out notifications
                    for ip in ip_group:
                        msg = 'TCWW: Build %d of project "%s" encountered %d new warning%s.' % \
                            (self.latest_build.number,
                             ip_group[ip],
                             len(inflations),
                             's' if len(inflations) > 1 else '')

                        command = [msg2skype_path, '-U', ip, msg]
                        try:
                            output = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).communicate()[0]
                            if 'Unable to attach' in output:
                                # try it again
                                output = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).communicate()[0]
                        except:
                            pass
                """

    def _generate_delta_format(self):
        """
        This method is used with the WarningFormat option.  It takes many more
        liberties with the lines of text, most notably 'normalizing' them based
        on the format indicated to (hopefully) reduce the number of false
        positives.
        """
        result_code = 0

        format_regex = self.config.teamcity.warning_format_regex[
            self.config.teamcity.warning_format ]

        # logic: Create 'normalized' lists that strip out the line numbers
        # so that movement of warnings do not produce false-positives.  then
        # use difflib to generate a unified diff between the two 'normalized'
        # lists. line numbers in the unified diff will correspond to the lines
        # in the 'raw' lists, which will be used for display (because a
        # warning message without a line number is pretty useless).

        # sanitize each warning down to it's essence for best matching
        def _sanitize(line, expression):
            # first, remove the 'warning' chunk from the string (which will
            # include line numbers)
            while True:
                result = re.search(expression, line)
                if result is None:
                    break
                line = line[:result.start(0)] + line[result.end(0):]

            # next, any runs of multiple spaces probably means
            # something that doesn't add to the warning detection
            result = re.search(' {2,}', line)
            if result:
                line = line[:result.start(0)]

            # next, tabs are bad
            try:
                index = line.index('\t')
            except:
                pass
            else:
                line = line[:index]

            # next, if a single warning line has multiple lines,
            # probably doesn't add to the warning detection
            try:
                index = line.index('\n')
            except:
                pass
            else:
                line = line[:index]

            # last, remove any explanatory text because, as above,
            # it probably doesn't add to the warning detection
            try:
                index = line.index(',')
            except:
                pass
            else:
                line = line[:index]

            return line

        cached_list = []
        line_no = 0
        for warning in self.cached_build.warnings:
            cached_list.append((_sanitize(warning, format_regex), line_no))
            line_no += 1

        # sort
        cached_list.sort(key=lambda x: x[0])
        cached_strings = [s[0] for s in cached_list]

        if self.config.debug_mode:
            with open('cached_list.txt', 'w') as output:
                for warning_str, _ in cached_list:
                    output.write('%s\n' % warning_str)
            open('cached_strings.txt', 'w').write('\n'.join(cached_strings))

        latest_list = []
        line_no = 0
        for warning in self.latest_build.warnings:
            latest_list.append((_sanitize(warning, format_regex), line_no))
            line_no += 1

        # sort
        latest_list.sort(key=lambda x: x[0])
        latest_strings = [s[0] for s in latest_list]

        if self.config.debug_mode:
            with open('latest_list.txt', 'w') as output:
                for warning_str, _ in latest_list:
                    output.write('%s\n' % warning_str)
            open('latest_strings.txt', 'w').write('\n'.join(latest_strings))

        unified = []
        for line in difflib.unified_diff(cached_strings, \
                                         latest_strings, \
                                         fromfile="cached_list", \
                                         tofile="latest_list"):
            unified.append(line)

        if self.config.debug_mode:
            open('unified.txt', 'w').write('\n'.join(unified))

        # walk the unified diff and determine what messages are new,
        # and what messages have gone away, if any

        inflations = []
        deflations = []

        before_line = 0
        #before_count = 0
        after_line = 0
        #after_count = 0

        for line in unified:
            if line.startswith('--- '):
                # 'before file' (i.e., cached list)
                pass

            elif line.startswith('+++ '):
                # 'after file' (i.e., latest list)
                pass

            elif line.startswith('@@ '):
                # hunk

                #before_count = 0
                #after_count = 0

                result = re.search(
                    r'@@\s*([+,-])(\d+)(\s*,\s*(\d+))?(\s*([+,-])(\d+)(\s*,\s*(\d+))?)?\s*@@',
                    line)

                # the above expression will produce a 9-tuple value.
                # some examples:
                #      input: @@ -1 +1 @@
                #     result: ('-', '1', None, None, ' +1', '+', '1', None, None)
                #
                #      input: @@ -1,4 +1,4 @@
                #     result: ('-', '1', ',4', '4', ' +1,4', '+', '1', ',4', '4')
                #
                #      input: @@ -103,6 +103,8 @@
                #     result: ('-', '103', ',6', '6', ' +103,8', '+', '103', ',8', '8')

                before_line = int(result.group(2))
                #if result.group(4) is not None:
                #    before_count = int(result.group(4))

                after_line = int(result.group(7))
                #if result.group(9) is not None:
                #    after_count = int(result.group(9))

            else:
                # we're processing a hunk
                if line.startswith('-'):
                    # this is a warning that no longer exists in the 'before
                    # file' (deflation)
                    deflations.append(self.cached_build.warnings[cached_list[before_line-1][1]])
                    before_line += 1

                elif line.startswith('+'):
                    # this is a new warning in the 'after file' (inflation)
                    inflations.append(self.latest_build.warnings[latest_list[after_line-1][1]])
                    after_line += 1

                else:
                    # this line is common to both lists
                    before_line += 1
                    after_line += 1

        if self.config.debug_mode:
            print 'Inflations:'
            if len(inflations):
                for line in inflations:
                    print '    ::', line
            else:
                print '    (none)'

            print 'Deflations:'
            if len(deflations):
                for line in deflations:
                    print '    ::', line
            else:
                print '    (none)'

        if len(deflations) and self.config.report_deflations:
            info_tuple = (len(deflations),
                          's' if len(deflations) > 1 else '',
                          'were' if len(deflations) > 1 else 'was')

            print '%d previous warning%s %s no longer detected in the build:' % info_tuple

            for line in deflations:
                if line.endswith('\n'):
                    line = line.rstrip()
                print '   -', line
            print ''

        if len(inflations):
            if self.config.inflations_are_errors:
                self.error_message = "##teamcity[buildProblem description='%d " \
                    "new warning%s discovered' identity='WarningWatcher']" % \
                    (len(inflations), 's' if len(inflations) > 1 else '')
                result_code = 1

            if not self.config.silence_inflations:
                info_tuple = (len(inflations),
                              's' if len(inflations) > 1 else '',
                              'were' if len(inflations) > 1 else 'was')

                print '%d new warning%s %s detected in this build:' % info_tuple

                for line in inflations:
                    if line.endswith('\n'):
                        line = line.rstrip()
                    print '   +', line

        if (len(deflations) == 0) and (len(inflations) == 0):
            print 'No warning differences detected within build #%d.' \
                % self.config.teamcity.build_number

        if self.config.debug_mode:
            sys.exit(0)     # prevent modification of the current cache

        return result_code

    def run(self):
        result_code = 0

        warning_compression = set()
        fragments_triggering_failure = set()

        build_step_count = 0    # which step of the build are we currently examining?
        done = False

        # walk all logs, oldest first, to find the current build
        current_log = self.log_manager.get_oldest()
        if not current_log:
            print 'Warning: Failed to locate TeamCity logs'
            print '    - Is the Builder running?'
            print '    - Is the configured path correct? (%s)' \
                % self.config.teamcity.build_agent_log_path
            return 1

        log_file = open(current_log.file_name, 'r')

        log_line = log_file.readline()
        while len(log_line) and (not done):
            if log_line.endswith('\n'):
                log_line = log_line.rstrip()
            if self.build_start in log_line:
                if self.config.teamcity.build_step != 0:
                    assert self.current_step is None, \
                        'Build start detected in current build'

                # extract the build id
                result = re.search(r'\-\-\- \[ (.+) \] \-\-\-', log_line)
                if result:
                    build_name = result.group(1)
                    if build_name.startswith('%s::%s' % \
                        (self.config.teamcity.project_name,
                         self.config.teamcity.config_name)):
                        result = re.search(r'(.+) \#(\d+)', build_name)
                        if result:
                            build_prefix, build_number = result.groups()
                            build_number = int(build_number)
                            if build_number == self.config.teamcity.build_number:
                                build_step_count += 1
                                if (self.config.teamcity.build_step == 0) or \
                                   (build_step_count == self.config.teamcity.build_step):
                                    self.current_step = BuildData()
                                    self.current_step.id = build_name
                                    self.current_step.prefix = build_prefix
                                    self.current_step.number = build_number

                                    warning_compression = set()
                                    fragments_triggering_failure = set()

            elif (self.build_end in log_line) and (self.current_step is not None):
                # the build must end successfully to be a valid differential candidate
                result = re.search(r'exited with code (\d+)', log_line)
                if result.group(1) != '0':
                    self.current_step = None

                elif self.config.teamcity.build_step != 0:
                    # if enough builds have been cached, perform a differential
                    # on their warnings
                    if self.cached_build and self.current_step:
                        if self.config.teamcity.warning_format is not None:
                            result_code = self._generate_delta_format()
                        else:
                            result_code = self._generate_delta()
                    else:
                        print 'First run; current warnings signature has been " \
                            "cached to "%s".' % str(self.config.cache_file)

                    self.cached_build = self.current_step
                    self._save_state()
                    done = True

                else:   # we are only going to process the latest step with warnings
                    self.latest_build_step = build_step_count
                    if len(self.current_step.warnings):
                        self.latest_build = self.current_step
                        self.latest_warning_compression = warning_compression
                        self.latest_failure_fragments = fragments_triggering_failure

            else:
                if (self.current_step is not None) and (' out - ' in log_line):
                    # normalize the line (i.e., strip off the TeamCity prefix)
                    index = log_line.index(' out - ') + 7
                    log_line = log_line[index:]

                    if self.config.working_prefix is not None:
                        log_line_lower = log_line.lower()
                        if log_line_lower.startswith(self.config.working_prefix):
                            log_line = '...%s' % log_line[len(self.config.working_prefix):]

                    log_lines = [log_line]
                    if '[-W' in log_line:     # OS X warning line; fix it up a bit
                        log_lines = []
                        while '[-W' in log_line:
                            ndx = log_line.index(' [-W')
                            log_lines.append(log_line[:ndx])
                            while log_line[ndx] != ']':
                                ndx += 1
                            log_line = log_line[ndx + 1:]

                    for line in log_lines:
                        result = None
                        if self.config.teamcity.warning_regex:
                            result = re.search(self.config.teamcity.warning_regex, line)
                            if result and result.lastindex:
                                if result.group(1) not in warning_compression:
                                    warning_compression.add(result.group(1))
                        elif self.config.teamcity.warning_format is not None:
                            result = re.search(
                                self.config.teamcity.warning_format_regex[
                                    self.config.teamcity.warning_format],
                                line)
                            if result:
                                if result.group(0) not in warning_compression:
                                    warning_compression.add(result.group(0))
                        else:
                            result = (self.config.teamcity.warning_text in line)

                        if result:
                            #self.current_step.warnings.add(_strip_number_runs(line))
                            self.current_step.warnings.append(line)

                        if len(self.config.fail_on_fragment):
                            for fragment in self.config.fail_on_fragment:
                                if fragment in line:
                                    fragments_triggering_failure.add(fragment)

            log_line = log_file.readline()
            if len(log_line) == 0:
                # a build's output can span logs, so here
                # we roll the log, if necessary
                log_file.close()
                current_log = self.log_manager.get_newer(current_log.key)
                if current_log is not None:
                    log_file = open(current_log.file_name, 'r')
                    log_line = log_file.readline()

        if self.config.teamcity.build_step == 0:
            if self.cached_build and self.latest_build:
                if self.config.teamcity.warning_format is not None:
                    result_code = self._generate_delta_format()
                else:
                    result_code = self._generate_delta()
            else:
                print 'First run; current warnings signature has been ' \
                      'cached to "%s".' % str(self.config.cache_file)

            self.cached_build = self.latest_build
            self._save_state()

        if len(self.latest_failure_fragments):
            print 'The following text fragments triggered a build failure:'
            for fragment in self.latest_failure_fragments:
                print '   -', fragment
            self.error_message = "##teamcity[buildProblem description='Failure " \
                "text fragments detected in build output' identity='WarningWatcher']"
            return 1

        if (self.config.teamcity.build_step != 0) and \
           (build_step_count != self.config.teamcity.build_step):
            print 'Warning: Failed to locate build #%d step %d in the TeamCity logs' \
                % (self.config.teamcity.build_number, self.config.teamcity.build_step)
            print '    - Are the logs too short?'
            print '    - Is the correct build step (%d) being processed?' \
                % self.config.teamcity.build_step
        else:
            print '%d total warnings matched the pattern in build #%d step %d' \
                % (len(self.latest_warning_compression),
                   self.config.teamcity.build_number,
                   self.latest_build_step)
            if len(self.latest_warning_compression) == 0:
                print '    - Did you switch to incremental building?'
                print '    - Are the logs too short?'
                print '    - Have warnings been turned off?'
                print '    - Did the step complete successfully?'
                if self.config.teamcity.build_step != 0:
                    print '    - Is the correct build step (%d) being processed?' \
                        % self.config.teamcity.build_step

        return result_code

    def _save_state(self):
        #print 'Writing the following warnings to the pickle file:'
        #for warning in self.cached_build.warnings:
        #    print '  -', warning

        pickle_file = self.config.cache_file.open(FileModes.WRITE_ONLY)
        assert pickle_file, 'Error: Could not access cache file: "%s"' % str(self.config.cache_file)
        self.cached_build.store(pickle_file)
        self.config.cache_file.close()

        if self.config.debug_mode:
            print 'Stored state to cache file "%s":' % str(self.config.cache_file)
            for line in self.cached_build.warnings:
                print '    ::', line

    def _restore_state(self):
        if self.config.reset_cache:
            print 'Resetting cache file "%s".' % str(self.config.cache_file)
            self.config.cache_file.reset()
            return

        pickle_file = self.config.cache_file.open(FileModes.READ_ONLY)
        if not pickle_file:
            print 'Previous cache file "%s" not found.' % str(self.config.cache_file)
            return

        self.cached_build = BuildData()
        self.cached_build.retrieve(pickle_file)
        self.config.cache_file.close()

        if self.config.debug_mode:
            print 'Restored state from cache file "%s":' % str(self.config.cache_file)
            for line in self.cached_build.warnings:
                print '    ::', line
