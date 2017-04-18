# TeamCity Warning Watcher
The TeamCity Warning Watcher (TCWW) is a build log miner, written in Python v2,
that attempts to track warning message differentials across builds.  It does
this in order to be able to detect when new warning messages are generated by
the code.

It understands log output formats for both Microsoft's Visual Studio compiler
and GCC variants.

## TeamCity Step
TCWW is intended to be an actual build step in your TeamCity project.  It should
be situated immediately following the build step which is to be evaluated.  For
example, a build step that generates warning messages (e.g., a Visual Studio
project build) should be followed by a "Command Line" build step that triggers
the Warning Watcher into action using a command line similar to the following:

  ```
  cd build_system/warning_watcher
  python warning_watcher.py -b %system.build.number% -p "%system.teamcity.projectName%" -a "%teamcity.agent.name%" -c "%system.teamcity.buildConfName%" -B "%BranchName%" --report-deflation
  ```

The values enclosed in percent signs ('%') are provided directly by TeamCity
to the step, and are required by TCWW in order to correctly identify the
section of the log containing the data to be examined.

Each TeamCity Build Agent must have a configuration file, contained in the
'builders_conf/' folder.  Please see the README.md file in the 'builders_conf/'
folder of this project for a deeper description of the contents of these
configuration files.

## Cache
On the initial run of TCWW, a new cache file will be created containing all of
the warning messages it could detect in the current build.  Subsequent runs will
reload this cached data and use it as the basis for detecting differences in
the current build.

Cache files can be stored in a number of different locations (including Dropbox),
and this is set per Build Agent.  If you have a multiple-builder configuration
where any Build Agent could build the same code base, you will likely want to
store this cache file in a common location where all Build Agents can access
it, and update all Build Agent configurations to point at the same location.

Please see the README.md file in the 'builders_conf/' folder of this project for
more detail on where cache file can be stored, and how to select these locations.

## Current status
The system is currently functional, but should be considered a work-in-progress
while I continue to tinker with it.  Determining warning message differentials
is actually harder than it might seem at first glance, and currently, the system
is not always accurate.

As such, I would recommend not using the "inflations-are-errors" option, as this
may abort your TeamCity build due to a false positive.

## Documentation
You're reading it now.
